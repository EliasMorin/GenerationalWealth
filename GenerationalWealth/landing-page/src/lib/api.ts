const API_BASE_URL = "http://localhost:5000/api";

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`[API Fetch Error] ${endpoint}:`, error);
    throw error;
  }
}

// Example API wrappers based on backend.py
export const api = {
  market: {
    getAll: () => fetchApi("/market/all"),
    getCorrelations: () => fetchApi("/market/correlations"),
  },
  portfolio: {
    getChart: () => fetchApi("/portfolio-chart"),
    getPerformance: () => fetchApi("/performance/market"),
  },
  analysis: {
    getTechnicals: () => fetchApi("/analysis/technicals"),
    get360: () => fetchApi("/analysis/360"),
  },
  cash: {
    getAnalysis: () => fetchApi("/cash/analysis"),
  }
};
