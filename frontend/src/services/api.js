const API_URL = '';

async function get(path) {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Error HTTP: ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => get('/api/health'),
  commercial: () => get('/api/commercial/summary'),
  monthly: () => get('/api/commercial/monthly'),
  categories: () => get('/api/commercial/categories'),
  products: () => get('/api/commercial/products'),
  logistics: () => get('/api/logistics/summary'),
  logisticsMonthly: () => get('/api/logistics/monthly'),
  inventoryCurrent: () => get('/api/inventory/current'),
  inventoryRisks: () => get('/api/inventory/risks'),
  predictiveMetrics: () => get('/api/predictive/metrics'),
  predictivePredictions: () => get('/api/predictive/predictions'),
  storePerformance: () => get('/api/store/performance')
};
