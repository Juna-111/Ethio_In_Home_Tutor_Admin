/**
 * MentorLink Mini App API Client
 * Features:
 *  - Strict base URL verification in production builds
 *  - Native Telegram WebApp initData HMAC authentication header (Authorization: tma <initData>)
 *  - 15-second AbortController timeout on all HTTP requests
 *  - Unified error translation and extraction
 */

function getBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (!configured || !configured.trim()) {
    if (import.meta.env.PROD) {
      throw new Error(
        "Critical configuration error: VITE_API_BASE_URL is not defined in this production build. Please set it in your environment settings."
      );
    }
    return "http://localhost:8000";
  }
  return configured.replace(/\/+$/, "");
}

export function getTelegramInitData() {
  if (typeof window === "undefined") return "";

  // 1. Direct window.Telegram.WebApp.initData
  try {
    const webAppInitData = window.Telegram?.WebApp?.initData;
    if (webAppInitData && typeof webAppInitData === "string" && webAppInitData.trim()) {
      try {
        sessionStorage.setItem("tma_init_data", webAppInitData.trim());
      } catch (_) {}
      return webAppInitData.trim();
    }
  } catch (_) {}

  // 2. Hash parameter fallback: #tgWebAppData=...
  try {
    if (window.location.hash) {
      const hashStr = window.location.hash.startsWith("#")
        ? window.location.hash.slice(1)
        : window.location.hash;
      const hashParams = new URLSearchParams(hashStr);
      const hashInitData = hashParams.get("tgWebAppData");
      if (hashInitData && hashInitData.trim()) {
        try {
          sessionStorage.setItem("tma_init_data", hashInitData.trim());
        } catch (_) {}
        return hashInitData.trim();
      }
    }
  } catch (_) {}

  // 3. Search query parameter fallback: ?tgWebAppData=...
  try {
    if (window.location.search) {
      const searchParams = new URLSearchParams(window.location.search);
      const queryInitData = searchParams.get("tgWebAppData");
      if (queryInitData && queryInitData.trim()) {
        try {
          sessionStorage.setItem("tma_init_data", queryInitData.trim());
        } catch (_) {}
        return queryInitData.trim();
      }
    }
  } catch (_) {}

  // 4. SessionStorage cached initData
  try {
    const cached = sessionStorage.getItem("tma_init_data");
    if (cached && cached.trim()) {
      return cached.trim();
    }
  } catch (_) {}

  return "";
}

export function getAuthHeaders() {
  const headers = {};
  const initData = getTelegramInitData();
  if (initData) {
    headers["Authorization"] = `tma ${initData}`;
  }
  return headers;
}

function describeApiHost(baseUrl) {
  try {
    return new URL(baseUrl).host;
  } catch (_) {
    return baseUrl;
  }
}

function currentOrigin() {
  try {
    return window.location.origin;
  } catch (_) {
    return "";
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Public request helper. Idempotent reads (GET) get one automatic retry on a
 * network-level failure, which smooths over cold starts and brief connection drops.
 * Writes are never retried automatically, to avoid double-submitting an action.
 */
async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  try {
    return await requestOnce(path, options);
  } catch (err) {
    const retryable = method === "GET" && (err.code === "NETWORK" || err.code === "TIMEOUT");
    if (!retryable) throw err;
    await sleep(1500);
    return requestOnce(path, options);
  }
}

async function requestOnce(path, options = {}) {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${path}`;

  const timeoutMs = options.timeoutMs || 15000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const authHeaders = getAuthHeaders();
  const isFormData = options.body instanceof FormData;

  const headers = {
    ...authHeaders,
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!response.ok) {
      const requestId = response.headers.get("X-Request-ID") || "";
      const errorData = await response.json().catch(() => ({}));
      let errorMessage = "An unexpected error occurred while communicating with the server.";
      if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail
            .map((d) => `${d.loc ? d.loc.slice(1).join(".") + ": " : ""}${d.msg}`)
            .join("\n");
        } else if (typeof errorData.detail === "string") {
          errorMessage = errorData.detail;
        } else {
          errorMessage = JSON.stringify(errorData.detail);
        }
      }
      const error = new Error(
        response.status >= 500 && requestId
          ? `${errorMessage} Reference: ${requestId}`
          : errorMessage
      );
      error.status = response.status;
      error.requestId = requestId || null;
      throw error;
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      const timeoutError = new Error(
        "The MentorLink server took too long to respond (15s). It may be waking up - please try again in a moment."
      );
      timeoutError.code = "TIMEOUT";
      throw timeoutError;
    }
    // fetch() rejects with a TypeError for every network-level failure, but the message
    // differs per browser ("Failed to fetch" / "Load failed" / "NetworkError ..."), so
    // match on the error type rather than its wording. A CORS rejection looks identical.
    if (err instanceof TypeError) {
      const networkError = new Error(
        `Could not reach the MentorLink server (${describeApiHost(baseUrl)}). ` +
        "It may be starting up - try again in a few seconds. If this keeps happening, " +
        `the server may be down or not allowing this app's address (${currentOrigin() || "unknown origin"}).`
      );
      networkError.code = "NETWORK";
      networkError.apiHost = describeApiHost(baseUrl);
      throw networkError;
    }
    throw err;
  }
}

export async function getParentChildren() {
  return request("/api/v1/parents/me/children");
}

export async function createParentChild(name) {
  return request("/api/v1/parents/me/children", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function submitParentRequest(data) {
  return request("/api/v1/parents/request", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function submitTutorRegistration(data) {
  return request("/api/v1/tutors/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadTutorDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const result = await request("/api/v1/tutors/upload-document", {
    method: "POST",
    body: formData,
    timeoutMs: 30000, // 30s for file uploads
  });

  const baseUrl = getBaseUrl();
  const fullUrl = result.file_url.startsWith("http")
    ? result.file_url
    : `${baseUrl}${result.file_url}`;

  return { ...result, full_url: fullUrl };
}

export async function getAdminControlCenter() {
  return request('/api/v1/admin/control-center');
}

export async function getAdminDashboard() {
  return request("/api/v1/admin/dashboard");
}

export async function getAdminRequests(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : '';
  return request(`/api/v1/admin/requests${suffix}`);
}

export async function getAdminRequest(requestId) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}`);
}

export async function getAdminCandidates(requestId) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}/candidates`);
}

export async function pingAdminCandidates(requestId, tutorIds) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}/ping`, {
    method: 'POST',
    body: JSON.stringify({ tutor_ids: tutorIds }),
  });
}

export async function assignAdminTutor(requestId, tutorId) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}/assign`, {
    method: 'POST',
    body: JSON.stringify({ tutor_id: tutorId }),
  });
}

export async function closeAdminRequest(requestId) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}/close`, { method: 'POST' });
}

export async function waitlistAdminRequest(requestId) {
  return request(`/api/v1/admin/requests/${encodeURIComponent(requestId)}/waitlist`, { method: 'POST' });
}

export async function getAdminCoverageGaps() {
  return request('/api/v1/admin/analytics/coverage-gaps');
}

export async function getAdminIdleTutors(days = 14) {
  return request(`/api/v1/admin/tutors/idle?days=${encodeURIComponent(days)}`);
}

export async function nudgeAdminTutor(tutorId) {
  return request(`/api/v1/admin/tutors/${encodeURIComponent(tutorId)}/reactivate-nudge`, { method: 'POST' });
}

export async function pingFunnelStart(sessionId) {
  return request("/api/v1/tutors/funnel/start", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getAdminTutors(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : '';
  return request(`/api/v1/admin/tutors${suffix}`);
}

export async function getAdminTutorDetail(tutorId) {
  return request(`/api/v1/admin/tutors/${encodeURIComponent(tutorId)}`);
}

export async function updateAdminTutorVerification(tutorId, patch) {
  return request(`/api/v1/admin/tutors/${encodeURIComponent(tutorId)}/verification`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function rejectAdminTutor(tutorId, reason) {
  return request(`/api/v1/admin/tutors/${encodeURIComponent(tutorId)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

export async function getAdminTutorScorecard(tutorId) {
  return request(`/api/v1/admin/tutors/${encodeURIComponent(tutorId)}/scorecard`);
}

export async function getAdminFlags() {
  return request('/api/v1/admin/flags');
}

export async function getAdminIncidents(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : '';
  return request(`/api/v1/admin/incidents${suffix}`);
}

export async function createAdminIncident(data) {
  return request('/api/v1/admin/incidents', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAdminIncident(incidentId, patch) {
  return request(`/api/v1/admin/incidents/${encodeURIComponent(incidentId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function getAdminUsers() {
  return request('/api/v1/admin/admins');
}

export async function createAdminUser(data) {
  return request('/api/v1/admin/admins', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteAdminUser(telegramId) {
  return request(`/api/v1/admin/admins/${encodeURIComponent(telegramId)}`, {
    method: 'DELETE',
  });
}

export async function getAdminAuditLog(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : '';
  return request(`/api/v1/admin/audit${suffix}`);
}

export async function getAdminFunnelAnalytics() {
  return request('/api/v1/admin/analytics/funnel');
}

export async function getAdminAvailabilityMismatch() {
  return request('/api/v1/admin/analytics/availability-mismatch');
}

export async function runAdminCron() {
  return request('/api/v1/admin/cron/run', { method: 'POST' });
}

export function getExportUrl(type = 'tutors') {
  const baseUrl = getBaseUrl();
  return `${baseUrl}/api/v1/admin/export?type=${encodeURIComponent(type)}`;
}

export async function getAdminParents(search = '') {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  return request(`/api/v1/admin/parents${query}`);
}

export async function getAdminAssignmentPipeline() {
  return request('/api/v1/admin/assignments/pipeline');
}

export async function getTutorProfile() {
  return request("/api/v1/tutors/me/profile");
}

export async function updateTutorAvailability(availability_schedule) {
  return request("/api/v1/tutors/me/availability", {
    method: "PATCH",
    body: JSON.stringify({ availability_schedule }),
  });
}

export async function getTutorOpportunities() {
  return request("/api/v1/tutors/me/opportunities");
}

export async function respondToTutorOpportunity(inviteId, decision) {
  return request(`/api/v1/tutors/me/opportunities/${inviteId}/respond?decision=${encodeURIComponent(decision)}`, {
    method: "POST",
  });
}

export async function getTutorMyAssignments() {
  return request('/api/v1/tutors/me/assignments');
}

export async function cancelParentRequest(requestId) {
  return request(`/api/v1/parents/me/requests/${encodeURIComponent(requestId)}/cancel`, {
    method: 'POST',
  });
}

export async function getParentMyRequests() {
  return request('/api/v1/parents/me/requests');
}

export async function submitParentFeedback(data) {
  return request('/api/v1/parents/me/feedback', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function submitParentContactAdmin(data) {
  return request('/api/v1/parents/me/contact-admin', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}


export async function getMarketplaceTutors(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : '';
  return request(`/api/v1/parents/tutors${suffix}`);
}

export async function getMarketplaceTutor(tutorId) {
  return request(`/api/v1/parents/tutors/${encodeURIComponent(tutorId)}`);
}

export async function applyToMarketplaceTutor(tutorId, requestId) {
  return request(`/api/v1/parents/tutors/${encodeURIComponent(tutorId)}/apply`, {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId }),
  });
}

export async function favoriteMarketplaceTutor(tutorId) {
  return request(`/api/v1/parents/tutors/${encodeURIComponent(tutorId)}/favorite`, { method: 'POST' });
}

export async function unfavoriteMarketplaceTutor(tutorId) {
  return request(`/api/v1/parents/tutors/${encodeURIComponent(tutorId)}/favorite`, { method: 'DELETE' });
}
