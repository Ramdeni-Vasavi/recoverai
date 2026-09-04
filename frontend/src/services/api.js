const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}/api/v1${path}`, options);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export const getHealth = () => request("/health");
export const getPayments = () => request("/payments");
export const getSummary = () => request("/dashboard/summary");
export const getPrediction = (id) => request(`/payments/${id}/prediction`);
export const getDecision = (id) => request(`/payments/${id}/decision`);
export const getOptimization = (id) => request(`/payments/${id}/optimization`);
export const getExecution = (id) => request(`/payments/${id}/execution`);
export const executeRecovery = (id) => request(`/payments/${id}/execute-recovery`, { method: "POST" });
