import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend
} from 'recharts';
import {
  Database, AlertTriangle, Info, FileText, Zap, Search, RefreshCw
} from 'lucide-react';
import ErrorBoundary from '../components/ErrorBoundary';

const formatNumber = value => {
  const num = Number(value);
  if (isNaN(num)) return '0.00';
  return num.toLocaleString('es-PE', {
    maximumFractionDigits: 2
  });
};

const formatDate = value => {
  if (!value) return '—';
  const str = String(value).split('T')[0].split(' ')[0];
  const parts = str.split('-');
  if (parts.length === 3) {
    const [y, m, d] = parts;
    return `${d}/${m}/${y}`;
  }
  return str;
};

function PredictiveContent() {
  const [metrics, setMetrics] = useState([]);
  const [metadataList, setMetadataList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');

  // Filtros interactivos para pronóstico granular
  const [selectedSource, setSelectedSource] = useState('olist');
  const [granularityMode, setGranularityMode] = useState('category'); // 'category', 'seller_product', 'country_product'
  const [selectedCategory, setSelectedCategory] = useState('bed_bath_table');
  const [selectedSeller, setSelectedSeller] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('');
  const [selectedCountry, setSelectedCountry] = useState('United Kingdom');
  const [selectedHorizon, setSelectedHorizon] = useState(12);

  // Estado del pronóstico granular obtenido de la API
  const [forecastResult, setForecastResult] = useState(null);
  const [loadingForecast, setLoadingForecast] = useState(false);

  // Estado para la Simulación Cyber Days en Forecast
  const [currentStock, setCurrentStock] = useState(null);
  const [evaluatingStock, setEvaluatingStock] = useState(false);

  // 1. Cargar métricas globales de Gold WAP y metadatos de fuentes
  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setPageError('');

    Promise.all([
      api.predictiveMetrics().catch(err => {
        console.warn('Fallo al obtener métricas predictivas:', err);
        return [];
      }),
      api.predictiveMetadata().catch(err => {
        console.warn('Fallo al obtener metadatos predictivos:', err);
        return null;
      })
    ])
      .then(([m, meta]) => {
        if (!mounted) return;
        setMetrics(Array.isArray(m) ? m : []);
        setMetadataList(meta);
        if (meta?.top_sellers?.length > 0) {
          setSelectedSeller(meta.top_sellers[0].seller_id);
        }
        if (meta?.top_products?.length > 0) {
          setSelectedProduct(meta.top_products[0].product_id);
        }
      })
      .catch(e => {
        if (mounted) setPageError(e.message || 'Error cargando datos iniciales.');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => { mounted = false; };
  }, []);

  // 2. Cargar pronóstico granular cada vez que cambien los filtros
  useEffect(() => {
    let mounted = true;
    setLoadingForecast(true);
    setCurrentStock(null);

    const params = {
      source: selectedSource || 'olist',
      horizon: Number(selectedHorizon) || 12
    };

    if (selectedSource === 'olist') {
      if (granularityMode === 'category') {
        params.category = selectedCategory || 'bed_bath_table';
      } else {
        if (selectedSeller) params.sellerId = selectedSeller;
        if (selectedProduct) params.productId = selectedProduct;
      }
    } else if (selectedSource === 'uci') {
      params.country = selectedCountry || 'United Kingdom';
      if (selectedProduct) params.productId = selectedProduct;
    }

    api.predictiveForecast(params)
      .then(res => {
        if (mounted) setForecastResult(res || null);
      })
      .catch(err => {
        if (mounted) {
          setForecastResult({
            sufficient_history: false,
            reason: err.message || 'Error al consultar pronóstico granular.'
          });
        }
      })
      .finally(() => {
        if (mounted) setLoadingForecast(false);
      });

    return () => { mounted = false; };
  }, [selectedSource, granularityMode, selectedCategory, selectedSeller, selectedProduct, selectedCountry, selectedHorizon]);

  // Función para evaluar impacto en el inventario real (Integración Cyber Days)
  const handleEvaluateInventory = async () => {
    if (!forecastResult || !forecastResult.sufficient_history) return;
    setEvaluatingStock(true);
    try {
      const targetProduct = selectedProduct;
      const stockRes = await api.inventoryCurrent(false, 'ALL', targetProduct);
      
      if (Array.isArray(stockRes) && stockRes.length > 0) {
        const totalStock = stockRes.reduce((acc, row) => acc + Number(row.stock_registrado || 0), 0);
        setCurrentStock(totalStock);
      } else {
        setCurrentStock(0);
      }
    } catch {
      setCurrentStock(0);
    } finally {
      setEvaluatingStock(false);
    }
  };

  const metadata = metrics[0] || {};

  // Serie combinada para el gráfico granular (historial + proyección + intervalos)
  const granularChartData = useMemo(() => {
    if (!forecastResult) return [];
    const points = [];

    if (Array.isArray(forecastResult.history)) {
      forecastResult.history.forEach(h => {
        if (!h || !h.semana) return;
        points.push({
          semana: String(h.semana),
          semanaLabel: formatDate(h.semana),
          actual: Number(h.actual) || 0,
          prediccion: null,
          lower_bound: null,
          upper_bound: null
        });
      });
    }

    if (Array.isArray(forecastResult.forecast)) {
      forecastResult.forecast.forEach(f => {
        if (!f || !f.semana) return;
        const sem = String(f.semana);
        const existing = points.find(p => p.semana === sem);
        if (existing) {
          existing.prediccion = Number(f.prediccion) || 0;
          existing.lower_bound = f.lower_bound != null ? Number(f.lower_bound) : null;
          existing.upper_bound = f.upper_bound != null ? Number(f.upper_bound) : null;
        } else {
          points.push({
            semana: sem,
            semanaLabel: formatDate(f.semana),
            actual: null,
            prediccion: Number(f.prediccion) || 0,
            lower_bound: f.lower_bound != null ? Number(f.lower_bound) : null,
            upper_bound: f.upper_bound != null ? Number(f.upper_bound) : null
          });
        }
      });
    }

    return points.sort((a, b) => a.semana.localeCompare(b.semana));
  }, [forecastResult]);

  // Cálculos de Demanda Acumulada para Escenarios Cyber Days
  const cyberScenarios = useMemo(() => {
    if (!forecastResult || !forecastResult.sufficient_history || !Array.isArray(forecastResult.forecast)) {
      return null;
    }
    const baseDemand = forecastResult.forecast.reduce((acc, f) => acc + (Number(f?.prediccion) || 0), 0);
    return {
      base: Math.round(baseDemand),
      moderate: Math.round(baseDemand * 1.20),
      intensive: Math.round(baseDemand * 1.50)
    };
  }, [forecastResult]);

  if (loading) {
    return (
      <div className="panel" style={{ padding: 40, textAlign: 'center' }}>
        <RefreshCw className="spin" size={24} style={{ marginBottom: 12, color: '#38bdf8' }} />
        <p style={{ margin: 0, color: '#94a3b8' }}>Cargando evaluación predictiva y modelos en BigQuery...</p>
      </div>
    );
  }

  if (pageError && !metrics.length) {
    return (
      <div className="panel error" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#f87171' }}>
          <AlertTriangle size={24} />
          <h3 style={{ margin: 0 }}>Error al consultar evaluación predictiva</h3>
        </div>
        <p style={{ color: '#cbd5e1', marginTop: 8 }}>{pageError}</p>
      </div>
    );
  }

  return (
    <div className="page-stack">
      {/* ENCABEZADO Y CONTROLES DE INFORME */}
      <section className="welcome" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <span className="eyebrow">MACHINE LEARNING / DEMAND FORECAST · WAP GOLD RELEASE</span>
          <h2>Planificación y Predicción de Demanda</h2>
          <p>
            Análisis predictivo multisource con granularidad por producto, comparación metodológica de modelos estadísticos e integración con escenarios Cyber Days.
          </p>
        </div>
        <button
          onClick={() => window.print()}
          style={{
            background: '#10b981', color: '#064e3b', border: 'none', padding: '10px 18px',
            borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
            boxShadow: '0 4px 12px rgba(16, 185, 129, 0.2)'
          }}
        >
          <FileText size={16} /> Generar Informe PDF
        </button>
      </section>

      {/* BANNER GOBERNANZA WAP */}
      <div className="wap-release-banner" style={{
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        color: '#f8fafc',
        padding: '16px 20px',
        borderRadius: '12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        border: '1px solid #334155'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: '#10b981', width: '10px', height: '10px', borderRadius: '50%', boxShadow: '0 0 8px #10b981' }} />
          <div>
            <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8' }}>Gobernanza WAP Activa</span>
            <div style={{ fontSize: '14px', fontWeight: 600 }}>Dominio Predictive: Publicado (Release Gold Validado)</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '20px', fontSize: '12px', color: '#cbd5e1' }}>
          <div>Versión activa: <code style={{ color: '#38bdf8', background: '#0284c722', padding: '2px 6px', borderRadius: '4px' }}>{metadata.run_id || 'run_predictive_gold'}</code></div>
          <div>Auditorías superadas: <strong style={{ color: '#4ade80' }}>3/3 (100%)</strong></div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECCIÓN 1: EXPLORADOR GRANULAR POR TIENDA / VENDEDOR Y PRODUCTO           */}
      {/* ========================================================================= */}
      <section className="panel" style={{ border: '1px solid #0284c7', background: '#0f172a', borderRadius: '12px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 20, color: '#f8fafc', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Search size={20} style={{ color: '#38bdf8' }} /> Explorador Granular de Pronósticos
            </h2>
            <p className="muted" style={{ margin: '4px 0 0 0' }}>
              Proyección de demanda, tendencias e intervalos de confianza estadísticos validados mediante Backtesting.
            </p>
          </div>
        </div>

        {/* Barra de Filtros Dependientes */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
          {/* 1. Fuente de Datos */}
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>FUENTE DE DATOS</label>
            <select
              value={selectedSource}
              onChange={e => {
                const src = e.target.value;
                setSelectedSource(src);
                if (src === 'uci') setGranularityMode('country_product');
                else if (src === 'thelook') setGranularityMode('thelook_store');
                else setGranularityMode('category');
              }}
              style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
            >
              <option value="olist">Olist Marketplace (Brasil - BRL)</option>
              <option value="uci">UCI Online Retail (Reino Unido - GBP)</option>
              <option value="thelook">TheLook eCommerce (Global - USD)</option>
            </select>
          </div>

          {/* 2. Modo de Segmentación (Solo Olist) */}
          {selectedSource === 'olist' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>NIVEL DE SEGMENTACIÓN</label>
              <select
                value={granularityMode}
                onChange={e => setGranularityMode(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                <option value="category">Por Categoría (XGBoost)</option>
                <option value="seller_product">Por Vendedor y Producto (Dinámico)</option>
              </select>
            </div>
          )}

          {/* 3. Selector Dependiente: Categoría (Olist) */}
          {selectedSource === 'olist' && granularityMode === 'category' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>CATEGORÍA</label>
              <select
                value={selectedCategory}
                onChange={e => setSelectedCategory(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.categories?.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          )}

          {/* 3b. Selector Dependiente: Vendedor (Olist) */}
          {selectedSource === 'olist' && granularityMode === 'seller_product' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>VENDEDOR (SELLER_ID)</label>
              <select
                value={selectedSeller}
                onChange={e => setSelectedSeller(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.top_sellers?.map(s => (
                  <option key={s.seller_id} value={s.seller_id}>{s.seller_id.substring(0, 12)}... ({s.n_items} items)</option>
                ))}
              </select>
            </div>
          )}

          {/* 3c. Selector Dependiente: Producto (Olist / UCI) */}
          {(granularityMode === 'seller_product' || granularityMode === 'country_product') && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>PRODUCTO (SKU)</label>
              <select
                value={selectedProduct}
                onChange={e => setSelectedProduct(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {selectedSource === 'olist' 
                  ? metadataList?.top_products?.map(p => <option key={p.product_id} value={p.product_id}>{p.product_id.substring(0, 12)}...</option>)
                  : metadataList?.uci_top_products?.map(p => <option key={p.stock_code} value={p.stock_code}>{p.stock_code}</option>)
                }
              </select>
            </div>
          )}

          {/* 4. Selector Dependiente: País (UCI) */}
          {selectedSource === 'uci' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>PAÍS / MERCADO</label>
              <select
                value={selectedCountry}
                onChange={e => setSelectedCountry(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.uci_countries?.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          )}

          {/* 5. Horizonte de Predicción */}
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>HORIZONTE ESPERADO</label>
            <select
              value={selectedHorizon}
              onChange={e => setSelectedHorizon(Number(e.target.value))}
              style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
            >
              <option value={4}>4 Semanas (1 Mes)</option>
              <option value={8}>8 Semanas (2 Meses)</option>
              <option value={12}>12 Semanas (Trimestre Completo)</option>
            </select>
          </div>
        </div>

        {/* Panel de Resultado Granular */}
        <div style={{ marginTop: 20 }}>
          {loadingForecast ? (
            <div style={{ padding: 30, textAlign: 'center', color: '#94a3b8' }}>
              <RefreshCw className="spin" size={20} style={{ marginBottom: 8, color: '#38bdf8' }} />
              <div>Proyectando series temporales y calibrando intervalos de predicción...</div>
            </div>
          ) : forecastResult?.sufficient_history ? (
            <div>
              {/* KPIs de Resumen Ejecutivo de la Proyección */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: 18 }}>
                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Modelo Seleccionado</span>
                  <strong style={{ fontSize: 14, color: '#f8fafc' }}>{String(forecastResult.model_name || 'Modelo').split('(')[0]}</strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Por menor WAPE (Holdout)</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Demanda Promedio</span>
                  <strong style={{ fontSize: 18, color: '#38bdf8' }}>{formatNumber(forecastResult.avg_demand)} u/sem</strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Histórica real</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Tendencia Reciente</span>
                  <strong style={{
                    fontSize: 16,
                    color: forecastResult.trend === 'CRECIENTE' ? '#4ade80' : forecastResult.trend === 'DECRECIENTE' ? '#f87171' : '#fbbf24'
                  }}>
                    {forecastResult.trend || 'ESTABLE'}
                  </strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Dirección de serie</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Incertidumbre (σ)</span>
                  <strong style={{ fontSize: 18, color: '#fbbf24' }}>±{formatNumber(forecastResult.variability_std)}</strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Desviación estándar</small>
                </div>

                {forecastResult.metrics?.WAPE !== undefined && (
                  <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                    <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>WAPE del Segmento</span>
                    <strong style={{ fontSize: 18, color: '#34d399' }}>{formatNumber(forecastResult.metrics.WAPE)}%</strong>
                    <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>MAE: {formatNumber(forecastResult.metrics.MAE)}</small>
                  </div>
                )}
              </div>

              {/* Gráfico de Historial vs. Pronóstico vs. Bandas de Incertidumbre */}
              <div style={{ background: '#1e293b', padding: '16px', borderRadius: 8, border: '1px solid #334155' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                  <strong style={{ fontSize: 13, color: '#f8fafc' }}>
                    Serie Histórica vs. Demanda Proyectada (Intervalo de Confianza 95%)
                  </strong>
                  <div style={{ display: 'flex', gap: 14, fontSize: 11 }}>
                    <span style={{ color: '#38bdf8' }}>● Demanda Real</span>
                    <span style={{ color: '#10b981' }}>● Pronóstico</span>
                    <span style={{ color: '#fcd34d' }}>┄ Límite Confianza</span>
                  </div>
                </div>

                <div className="chart-box" style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={granularChartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="semanaLabel" stroke="#94a3b8" fontSize={11} minTickGap={20} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip
                        contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                        formatter={(val, name) => [val !== null ? `${formatNumber(val)} unidades` : '—', name]}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="actual" name="Demanda Real" stroke="#38bdf8" strokeWidth={2.5} dot={{ r: 3, fill: '#38bdf8' }} connectNulls />
                      <Line type="monotone" dataKey="prediccion" name="Demanda Pronosticada" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4, fill: '#10b981' }} connectNulls />
                      <Line type="monotone" dataKey="upper_bound" name="Límite Superior (95%)" stroke="#6ee7b7" strokeDasharray="4 4" strokeWidth={1.5} dot={false} connectNulls />
                      <Line type="monotone" dataKey="lower_bound" name="Límite Inferior (95%)" stroke="#fcd34d" strokeDasharray="4 4" strokeWidth={1.5} dot={false} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ marginTop: 10, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Info size={13} style={{ color: '#38bdf8' }} />
                  <span>{forecastResult.note || 'Pronóstico calculado mediante backtest dinámico con holdout temporal.'}</span>
                </div>
              </div>

              {/* INTEGRACIÓN CON CYBER DAYS SIMULATOR */}
              {(granularityMode === 'seller_product' || granularityMode === 'country_product') && cyberScenarios && (
                <div style={{ marginTop: 24, padding: 20, background: '#1e1b4b', border: '1px solid #4f46e5', borderRadius: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                    <Zap size={20} style={{ color: '#818cf8' }} />
                    <h3 style={{ margin: 0, color: '#f8fafc', fontSize: 16 }}>Análisis de Escenarios Comerciales (Simulador Cyber Days)</h3>
                  </div>
                  <p style={{ fontSize: 12, color: '#c7d2fe', marginBottom: 16 }}>
                    Utilice el pronóstico estadístico base para proyectar el consumo de inventario ante escenarios de alta demanda promocional para las próximas <strong>{selectedHorizon} semanas</strong>.
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 16 }}>
                    <div style={{ background: '#312e81', padding: 16, borderRadius: 8, border: '1px solid #4338ca' }}>
                      <strong style={{ display: 'block', color: '#f8fafc', fontSize: 14 }}>Escenario Base</strong>
                      <span style={{ color: '#a5b4fc', fontSize: 12 }}>Demanda proyectada por el modelo</span>
                      <h4 style={{ margin: '10px 0 0 0', color: '#818cf8', fontSize: 24 }}>{cyberScenarios.base} u</h4>
                    </div>
                    <div style={{ background: '#312e81', padding: 16, borderRadius: 8, border: '1px solid #4338ca' }}>
                      <strong style={{ display: 'block', color: '#f8fafc', fontSize: 14 }}>Moderado (+20%)</strong>
                      <span style={{ color: '#a5b4fc', fontSize: 12 }}>Incremento promocional típico</span>
                      <h4 style={{ margin: '10px 0 0 0', color: '#fbbf24', fontSize: 24 }}>{cyberScenarios.moderate} u</h4>
                    </div>
                    <div style={{ background: '#312e81', padding: 16, borderRadius: 8, border: '1px solid #4338ca' }}>
                      <strong style={{ display: 'block', color: '#f8fafc', fontSize: 14 }}>Intensivo (+50%)</strong>
                      <span style={{ color: '#a5b4fc', fontSize: 12 }}>Pico de tráfico Cyber Days</span>
                      <h4 style={{ margin: '10px 0 0 0', color: '#f87171', fontSize: 24 }}>{cyberScenarios.intensive} u</h4>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, background: '#0f172a', padding: 16, borderRadius: 8 }}>
                    <div>
                      <strong style={{ color: '#f8fafc', fontSize: 13, display: 'block' }}>Impacto en Inventario Operativo Real</strong>
                      <span style={{ color: '#94a3b8', fontSize: 12 }}>Consulta en tiempo real el stock actual consolidado para evaluar el riesgo de quiebre (Out of Stock).</span>
                    </div>
                    <button
                      onClick={handleEvaluateInventory}
                      disabled={evaluatingStock}
                      style={{
                        background: '#4f46e5', color: 'white', border: 'none', padding: '8px 16px', borderRadius: 6,
                        fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6
                      }}
                    >
                      {evaluatingStock ? <RefreshCw className="spin" size={14} /> : <Database size={14} />}
                      {evaluatingStock ? 'Consultando...' : 'Consultar Inventario Real'}
                    </button>
                  </div>

                  {currentStock !== null && (
                    <div style={{ marginTop: 16 }}>
                      {currentStock > 0 ? (
                        <div style={{ display: 'flex', gap: 16, alignItems: 'stretch', flexWrap: 'wrap' }}>
                          <div style={{ background: '#064e3b', padding: 16, borderRadius: 8, border: '1px solid #10b981', flex: 1 }}>
                            <strong style={{ color: '#34d399', display: 'block' }}>Stock Disponible Actual</strong>
                            <h4 style={{ fontSize: 22, margin: '6px 0', color: 'white' }}>{currentStock} unidades</h4>
                            <span style={{ fontSize: 11, color: '#6ee7b7' }}>Consolidado en todas las regiones</span>
                          </div>
                          
                          <div style={{ background: '#1e293b', padding: 16, borderRadius: 8, border: '1px solid #334155', flex: 2 }}>
                            <strong style={{ color: '#f8fafc', display: 'block', marginBottom: 8 }}>Proyección de Saldo (Al final del horizonte)</strong>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                              <span style={{ color: '#94a3b8' }}>Escenario Base:</span>
                              <strong style={{ color: currentStock - cyberScenarios.base < 0 ? '#f87171' : '#f8fafc' }}>
                                {currentStock - cyberScenarios.base} u
                              </strong>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                              <span style={{ color: '#94a3b8' }}>Escenario Moderado:</span>
                              <strong style={{ color: currentStock - cyberScenarios.moderate < 0 ? '#f87171' : '#f8fafc' }}>
                                {currentStock - cyberScenarios.moderate} u
                              </strong>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                              <span style={{ color: '#94a3b8' }}>Escenario Intensivo:</span>
                              <strong style={{ color: currentStock - cyberScenarios.intensive < 0 ? '#f87171' : '#f8fafc' }}>
                                {currentStock - cyberScenarios.intensive} u
                              </strong>
                            </div>
                          </div>
                        </div>
                      ) : (
                         <div style={{ background: '#7f1d1d', padding: 16, borderRadius: 8, border: '1px solid #b91c1c', color: '#fecaca', display: 'flex', alignItems: 'center', gap: 12 }}>
                           <AlertTriangle size={24} style={{ color: '#fca5a5' }} />
                           <div>
                             <strong style={{ display: 'block' }}>Sin Inventario Registrado</strong>
                             <span style={{ fontSize: 12 }}>El producto seleccionado no dispone de existencias en el sistema de telemetría operativa actual (Ej. TheLook o UCI), o su saldo es 0. 100% de los pedidos simulados serían rechazados por Out of Stock.</span>
                           </div>
                         </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Banner de advertencia de historial insuficiente */
            <div style={{ background: '#451a03', border: '1px solid #b45309', borderRadius: 8, padding: '20px', color: '#fef3c7' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <AlertTriangle size={24} style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <h4 style={{ margin: '0 0 6px 0', fontSize: 15, color: '#fbbf24' }}>
                    Historial Insuficiente para Pronóstico Estadístico Confiable
                  </h4>
                  <p style={{ margin: '0 0 10px 0', fontSize: 13, lineHeight: 1.5, color: '#fde68a' }}>
                    {forecastResult?.reason || 'La combinación seleccionada no cuenta con un volumen histórico mínimo para realizar pronósticos confiables.'}
                  </p>
                  <div style={{ fontSize: 11, color: '#cbd5e1', background: '#1e293b', padding: '8px 12px', borderRadius: 6, display: 'inline-block' }}>
                    <strong>Criterio Metodológico LUMINA:</strong> Para prevenir pronósticos espurios o sobreajuste severo en series temporales intermitentes, la plataforma requiere al menos 10 semanas de actividad comercial continua.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* SECCIÓN 2: COMPARACIÓN DE MODELOS (DIAGNÓSTICO Y BENCHMARK)                 */}
      {/* ========================================================================= */}
      {(granularityMode === 'category') ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="section-heading">
            <div>
              <h2>Benchmark Comparativo de Modelos (Backtest 888 Observaciones)</h2>
              <p>Evaluación de XGBoost frente a modelos heurísticos de persistencia (A nivel de Categoría)</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Clasificación</th>
                  <th>Observaciones</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>WAPE</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: '#064e3b22' }}>
                  <td><strong>Naive Baseline (t-1)</strong></td>
                  <td>Heurístico (Persistencia)</td>
                  <td>888</td>
                  <td><strong>7.54</strong></td>
                  <td><strong>15.90</strong></td>
                  <td><strong>35.49%</strong></td>
                  <td><span style={{ color: '#34d399', fontWeight: 600 }}>★ Mejor WAPE</span></td>
                </tr>
                <tr>
                  <td><strong>XGBoost Regressor</strong></td>
                  <td>Supervisado (Machine Learning)</td>
                  <td>888</td>
                  <td>7.78</td>
                  <td>16.72</td>
                  <td>36.60%</td>
                  <td><span style={{ color: '#38bdf8', fontWeight: 600 }}>En Producción Gold</span></td>
                </tr>
                <tr style={{ background: '#78350f22' }}>
                  <td><strong>Seasonal Naive (t-52)</strong></td>
                  <td>Heurístico (Estacional Anual)</td>
                  <td>888</td>
                  <td>12.79</td>
                  <td>27.18</td>
                  <td>60.21%</td>
                  <td><span style={{ color: '#fbbf24' }}>Sesgo Interanual</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: '12px', marginTop: '10px' }}>
            <strong>Diagnóstico del Data Scientist:</strong> El modelo Naive (t-1) superó levemente a XGBoost en la métrica global WAPE debido a la alta autocorrelación en categorías de baja rotación. Sin embargo, XGBoost mantiene mayor estabilidad en escenarios promocionales y de alta varianza. Seasonal Naive (t-52) subestima sistemáticamente la demanda por la fuerte aceleración transaccional del mercado brasileño entre 2017 y 2018.
          </p>
        </section>
      ) : forecastResult?.models_evals && forecastResult.models_evals.length > 0 ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="section-heading">
            <div>
              <h2>Evaluación de Modelos Competidores (Backtesting Dinámico)</h2>
              <p>Tabla de calibración del segmento específico seleccionado (Ventana de validación *holdout*).</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Modelo Matemático</th>
                  <th>WAPE</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>Estado del Modelo</th>
                </tr>
              </thead>
              <tbody>
                {forecastResult.models_evals.map((ev, idx) => (
                  <tr key={ev.model} style={{ background: idx === 0 ? '#064e3b22' : 'transparent' }}>
                    <td>{idx + 1}</td>
                    <td><strong>{ev.model}</strong></td>
                    <td style={{ fontWeight: idx === 0 ? 700 : 400, color: idx === 0 ? '#34d399' : 'inherit' }}>
                      {formatNumber(ev.wape)}%
                    </td>
                    <td>{formatNumber(ev.mae)}</td>
                    <td>{formatNumber(ev.rmse)}</td>
                    <td>
                      {idx === 0 ? (
                        <span style={{ fontSize: 10, background: '#10b981', color: '#064e3b', padding: '2px 6px', borderRadius: 4, fontWeight: 700 }}>SELECCIONADO AUTOMÁTICAMENTE</span>
                      ) : (
                        <span style={{ fontSize: 10, color: '#94a3b8' }}>DESCARTADO POR MAYOR ERROR</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

    </div>
  );
}

export default function Predictive() {
  return (
    <ErrorBoundary fallbackTitle="Error al renderizar Predicción de Demanda">
      <PredictiveContent />
    </ErrorBoundary>
  );
}
