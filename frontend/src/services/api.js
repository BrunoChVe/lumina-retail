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
  inventoryCurrent: (includeSynthetic = false) => get(`/api/inventory/current?include_synthetic=${includeSynthetic}`),
  inventoryRisks: (includeSynthetic = false) => get(`/api/inventory/risks?include_synthetic=${includeSynthetic}`),
  inventoryUciCatalog: () => get('/api/inventory/uci/catalog'),
  inventoryUciCountry: () => get('/api/inventory/uci/country'),
  inventoryUciMonthly: () => get('/api/inventory/uci/monthly'),
  predictiveMetrics: () => get('/api/predictive/metrics'),
  predictivePredictions: () => get('/api/predictive/predictions'),
  storePerformance: () => get('/api/store/performance'),
  countries: () => get('/api/commercial/countries'),
  customersSummary: () => get('/api/commercial/customers_summary'),
  cancellations: () => get('/api/commercial/cancellations')
};
