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

function getAuthHeaders() {
  const headers = {};
  try {
    const initData = window.Telegram?.WebApp?.initData;
    if (initData && typeof initData === "string" && initData.trim()) {
      headers["Authorization"] = `tma ${initData.trim()}`;
    }
  } catch (err) {
    // Ignore in standard web preview
  }
  return headers;
}

async function request(path, options = {}) {
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
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error("Request timed out (15s). Please check your internet connection and try again.");
    }
    if (err.message && err.message.includes("Failed to fetch")) {
      throw new Error("Network connection error. Could not connect to the MentorLink server.");
    }
    throw err;
  }
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
