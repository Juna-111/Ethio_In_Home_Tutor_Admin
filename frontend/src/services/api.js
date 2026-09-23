const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function submitParentRequest(data) {
  const response = await fetch(`${API_BASE_URL}/api/v1/parents/request`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = "Failed to submit request. Please check your inputs.";
    if (errorData.detail) {
      if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}`).join('\n');
      } else {
        errorMessage = errorData.detail;
      }
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function submitTutorRegistration(data) {
  const response = await fetch(`${API_BASE_URL}/api/v1/tutors/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = "Failed to register tutor profile.";
    if (errorData.detail) {
      if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}`).join('\n');
      } else {
        errorMessage = errorData.detail;
      }
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function uploadTutorDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/v1/tutors/upload-document`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = "Failed to upload document.";
    if (errorData.detail) {
      errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  // Return absolute or relative URL
  const fullUrl = result.file_url.startsWith('http') 
    ? result.file_url 
    : `${API_BASE_URL}${result.file_url}`;
  return { ...result, full_url: fullUrl };
}
