const API_URL = '';

async function get(path) {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Error HTTP: ${res.status}`);
  }
  return res.json();
}

async function post(path, data = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
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
  inventoryCurrent: (includeSynthetic = false, region = '', productId = '') => {
    const params = new URLSearchParams({ include_synthetic: includeSynthetic });
    if (region && region !== 'ALL') params.append('region', region);
    if (productId && productId !== 'ALL') params.append('product_id', productId);
    return get(`/api/inventory/current?${params.toString()}`);
  },
  inventoryRisks: (includeSynthetic = false, region = '', productId = '') => {
    const params = new URLSearchParams({ include_synthetic: includeSynthetic });
    if (region && region !== 'ALL') params.append('region', region);
    if (productId && productId !== 'ALL') params.append('product_id', productId);
    return get(`/api/inventory/risks?${params.toString()}`);
  },
  inventoryMetadata: (includeSynthetic = false) => get(`/api/inventory/metadata?include_synthetic=${includeSynthetic}`),
  inventoryUciSummary: (country = '', stockCode = '', abcClass = '') => {
    const params = new URLSearchParams();
    if (country && country !== 'ALL') params.append('country', country);
    if (stockCode && stockCode !== 'ALL') params.append('stock_code', stockCode);
    if (abcClass && abcClass !== 'ALL') params.append('abc_class', abcClass);
    return get(`/api/inventory/uci/summary?${params.toString()}`);
  },
  inventoryUciCatalog: (limit = 100, stockCode = '', abcClass = '', country = '') => {
    const params = new URLSearchParams({ limit });
    if (stockCode && stockCode !== 'ALL') params.append('stock_code', stockCode);
    if (abcClass && abcClass !== 'ALL') params.append('abc_class', abcClass);
    if (country && country !== 'ALL') params.append('country', country);
    return get(`/api/inventory/uci/catalog?${params.toString()}`);
  },
  inventoryUciCountry: (country = '', stockCode = '') => {
    const params = new URLSearchParams();
    if (country && country !== 'ALL') params.append('country', country);
    if (stockCode && stockCode !== 'ALL') params.append('stock_code', stockCode);
    return get(`/api/inventory/uci/country?${params.toString()}`);
  },
  inventoryUciMonthly: (country = '', stockCode = '') => {
    const params = new URLSearchParams();
    if (country && country !== 'ALL') params.append('country', country);
    if (stockCode && stockCode !== 'ALL') params.append('stock_code', stockCode);
    return get(`/api/inventory/uci/monthly?${params.toString()}`);
  },
  predictiveMetrics: () => get('/api/predictive/metrics'),
  predictivePredictions: (categoria = '') => {
    const params = new URLSearchParams();
    if (categoria && categoria !== 'ALL') params.append('categoria', categoria);
    return get(`/api/predictive/predictions?${params.toString()}`);
  },
  predictiveMetadata: () => get('/api/predictive/metadata'),
  predictiveForecast: ({ source = 'olist', category = '', sellerId = '', productId = '', country = '', horizon = 12 } = {}) => {
    const params = new URLSearchParams({ source, horizon });
    if (category && category !== 'ALL') params.append('category', category);
    if (sellerId && sellerId !== 'ALL') params.append('seller_id', sellerId);
    if (productId && productId !== 'ALL') params.append('product_id', productId);
    if (country && country !== 'ALL') params.append('country', country);
    return get(`/api/predictive/forecast?${params.toString()}`);
  },
  storePerformance: () => get('/api/store/performance'),
  countries: () => get('/api/commercial/countries'),
  customersSummary: () => get('/api/commercial/customers_summary'),
  cancellations: () => get('/api/commercial/cancellations'),
  // Centro de Simulación Cyber Days y Ciclo de Pedidos
  simulationModalities: () => get('/api/simulation/modalities'),
  simulationInfrastructureStatus: () => get('/api/simulation/infrastructure_status'),
  simulationValidateConfig: (config) => post('/api/simulation/validate_config', config),
  simulationRun: (config) => post('/api/simulation/run', config),
  simulationStatus: (runId) => get(`/api/simulation/status/${runId}`),
  simulationEvents: (runId, limit = 100, eventType = '') => {
    const params = new URLSearchParams({ limit });
    if (eventType && eventType !== 'ALL') params.append('event_type', eventType);
    return get(`/api/simulation/events/${runId}?${params.toString()}`);
  },
  simulationHistory: () => get('/api/simulation/history'),
  simulationCancel: (runId) => post(`/api/simulation/cancel/${runId}`)
};
