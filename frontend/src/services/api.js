const API = import.meta.env.VITE_API_URL || '';

async function get(endpoint) {
  const response = await fetch(`${API}${endpoint}`);

  if (!response.ok) {
    throw new Error(`Error API ${response.status}: ${endpoint}`);
  }

  return response.json();
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
  predictivePredictions: () => get('/api/predictive/predictions')
};
