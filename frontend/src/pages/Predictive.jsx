import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, BarChart, Bar
} from 'recharts';
import {
  Target, Activity, TrendingUp, Database, Filter, Store,
  Package, AlertTriangle, CheckCircle2, Info, RotateCcw, Calendar
} from 'lucide-react';

const formatNumber = value =>
  Number(value || 0).toLocaleString('es-PE', {
    maximumFractionDigits: 2
  });

const formatDate = value =>
  value
    ? new Date(`${value}T00:00:00`).toLocaleDateString('es-PE')
    : '—';

export default function Predictive() {
  const [metrics, setMetrics] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [metadataList, setMetadataList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  // 1. Cargar métricas globales de Gold WAP y metadatos de fuentes
  useEffect(() => {
    Promise.all([
      api.predictiveMetrics(),
      api.predictivePredictions(),
      api.predictiveMetadata().catch(() => null)
    ])
      .then(([m, p, meta]) => {
        setMetrics(m || []);
        setPredictions(p || []);
        setMetadataList(meta);
        if (meta && meta.top_sellers && meta.top_sellers.length > 0) {
          setSelectedSeller(meta.top_sellers[0].seller_id);
        }
        if (meta && meta.top_products && meta.top_products.length > 0) {
          setSelectedProduct(meta.top_products[0].product_id);
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // 2. Cargar pronóstico granular cada vez que cambien los filtros
  useEffect(() => {
    setLoadingForecast(true);
    const params = {
      source: selectedSource,
      horizon: selectedHorizon
    };

    if (selectedSource === 'olist') {
      if (granularityMode === 'category') {
        params.category = selectedCategory;
      } else {
        params.sellerId = selectedSeller;
        params.productId = selectedProduct;
      }
    } else if (selectedSource === 'uci') {
      params.country = selectedCountry;
      params.productId = selectedProduct;
    }

    api.predictiveForecast(params)
      .then(res => setForecastResult(res))
      .catch(err => {
        setForecastResult({
          sufficient_history: false,
          reason: err.message || 'Error al consultar pronóstico granular.'
        });
      })
      .finally(() => setLoadingForecast(false));
  }, [selectedSource, granularityMode, selectedCategory, selectedSeller, selectedProduct, selectedCountry, selectedHorizon]);

  const metric = name =>
    metrics.find(item => item.metric === name)?.value;

  const metadata = metrics[0] || {};

  // Agrupación semanal global para gráfico general
  const weekly = useMemo(() => {
    const grouped = {};
    predictions.forEach(row => {
      if (!grouped[row.semana]) {
        grouped[row.semana] = {
          semana: row.semana,
          actual: 0,
          prediccion: 0
        };
      }
      grouped[row.semana].actual += Number(row.actual || 0);
      grouped[row.semana].prediccion += Number(row.prediccion || 0);
    });

    return Object.values(grouped)
      .sort((a, b) => a.semana.localeCompare(b.semana))
      .map(row => ({
        ...row,
        semanaLabel: formatDate(row.semana)
      }));
  }, [predictions]);

  // Categorías con mayor error
  const categories = useMemo(() => {
    const grouped = {};
    predictions.forEach(row => {
      const category = row.categoria;
      if (!grouped[category]) {
        grouped[category] = {
          categoria: category,
          actual: 0,
          prediccion: 0,
          error: 0
        };
      }
      grouped[category].actual += Number(row.actual || 0);
      grouped[category].prediccion += Number(row.prediccion || 0);
      grouped[category].error += Number(row.error_absoluto || 0);
    });

    return Object.values(grouped)
      .sort((a, b) => b.error - a.error)
      .slice(0, 15);
  }, [predictions]);

  // Serie combinada para el gráfico granular (historial + proyección + intervalos)
  const granularChartData = useMemo(() => {
    if (!forecastResult) return [];
    const points = [];

    // Puntos históricos
    if (forecastResult.history) {
      forecastResult.history.forEach(h => {
        points.push({
          semana: h.semana,
          semanaLabel: formatDate(h.semana),
          actual: h.actual,
          prediccion: null,
          lower_bound: null,
          upper_bound: null
        });
      });
    }

    // Puntos de pronóstico
    if (forecastResult.forecast) {
      forecastResult.forecast.forEach(f => {
        const existing = points.find(p => p.semana === f.semana);
        if (existing) {
          existing.prediccion = f.prediccion;
          existing.lower_bound = f.lower_bound;
          existing.upper_bound = f.upper_bound;
        } else {
          points.push({
            semana: f.semana,
            semanaLabel: formatDate(f.semana),
            actual: null,
            prediccion: f.prediccion,
            lower_bound: f.lower_bound,
            upper_bound: f.upper_bound
          });
        }
      });
    }

    return points.sort((a, b) => a.semana.localeCompare(b.semana));
  }, [forecastResult]);

  if (loading) {
    return <div className="panel" style={{ padding: 40, textAlign: 'center' }}>Cargando evaluación predictiva y modelos en BigQuery...</div>;
  }

  if (error && !metrics.length) {
    return (
      <div className="panel error">
        <h3>Error al consultar evaluación</h3>
        <p>{error}</p>
      </div>
    );
  }

  const cards = [
    {
      label: 'MAE',
      value: formatNumber(metric('MAE')),
      description: 'Error absoluto medio',
      icon: Target
    },
    {
      label: 'RMSE',
      value: formatNumber(metric('RMSE')),
      description: 'Raíz del error cuadrático medio',
      icon: Activity
    },
    {
      label: 'WAPE',
      value: `${formatNumber(metric('WAPE'))}%`,
      description: 'Error porcentual ponderado',
      icon: TrendingUp
    },
    {
      label: 'Predicciones',
      value: formatNumber(metadata.n_test_rows || 888),
      description: 'Observaciones de prueba',
      icon: Database
    }
  ];

  return (
    <div className="page-stack">
      {/* ENCABEZADO */}
      <section className="welcome">
        <span className="eyebrow">MACHINE LEARNING / DEMAND FORECAST · WAP GOLD RELEASE</span>
        <h2>Predicción de Demanda Multisource</h2>
        <p>
          Pronóstico y evaluación de demanda semanal por categoría, tienda, vendedor y producto, gobernado mediante el protocolo WAP-02.1.
        </p>
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
          <div>Almacenamiento: <code style={{ color: '#a78bfa' }}>gold_predictive_*</code></div>
        </div>
      </div>

      {/* TARJETAS KPI GLOBALES */}
      <section className="kpi-grid">
        {cards.map(card => {
          const Icon = card.icon;
          return (
            <article className="panel kpi" key={card.label}>
              <div className="kpi-icon"><Icon size={20} /></div>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.description}</small>
            </article>
          );
        })}
      </section>

      {/* ========================================================================= */}
      {/* SECCIÓN NUEVA: PRONÓSTICO GRANULAR POR TIENDA / VENDEDOR Y PRODUCTO        */}
      {/* ========================================================================= */}
      <section className="panel" style={{ border: '1px solid #0284c7', background: '#0f172a', borderRadius: '12px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ background: '#0284c7', color: 'white', fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                NUEVA CAPACIDAD GRANULAR
              </span>
              <span style={{ color: '#94a3b8', fontSize: 12 }}>Filtros Dependientes por Fuente, Unidad y Producto</span>
            </div>
            <h2 style={{ fontSize: 20, color: '#f8fafc', margin: 0 }}>Pronóstico de Demanda por Tienda, Vendedor y Producto</h2>
            <p className="muted" style={{ margin: '4px 0 0 0' }}>
              Consulte proyecciones de demanda, tendencias e intervalos de confianza estadísticos con validación estricta de suficiencia de historial.
            </p>
          </div>
        </div>

        {/* Barra de Filtros Dependientes */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
          {/* 1. Fuente de Datos */}
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
              FUENTE DE DATOS
            </label>
            <select
              value={selectedSource}
              onChange={e => {
                setSelectedSource(e.target.value);
                if (e.target.value === 'uci') setGranularityMode('country_product');
                else if (e.target.value === 'thelook') setGranularityMode('thelook_store');
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
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                NIVEL DE SEGMENTACIÓN
              </label>
              <select
                value={granularityMode}
                onChange={e => setGranularityMode(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                <option value="category">Por Categoría (Modelo Gold XGBoost)</option>
                <option value="seller_product">Por Vendedor y Producto (Olist Fact)</option>
              </select>
            </div>
          )}

          {/* 3. Selector Dependiente: Categoría (Olist) */}
          {selectedSource === 'olist' && granularityMode === 'category' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                CATEGORÍA (74 CATEGORÍAS GOLD)
              </label>
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
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                VENDEDOR (SELLER_ID)
              </label>
              <select
                value={selectedSeller}
                onChange={e => setSelectedSeller(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.top_sellers?.map(s => (
                  <option key={s.seller_id} value={s.seller_id}>
                    {s.seller_id.substring(0, 12)}... ({s.n_items} items)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 3c. Selector Dependiente: Producto (Olist Seller_Product) */}
          {selectedSource === 'olist' && granularityMode === 'seller_product' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                PRODUCTO (PRODUCT_ID)
              </label>
              <select
                value={selectedProduct}
                onChange={e => setSelectedProduct(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.top_products?.map(p => (
                  <option key={p.product_id} value={p.product_id}>
                    {p.product_id.substring(0, 12)}... ({p.n_items} ventas)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 4. Selector Dependiente: País (UCI) */}
          {selectedSource === 'uci' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                PAÍS / MERCADO (UCI)
              </label>
              <select
                value={selectedCountry}
                onChange={e => setSelectedCountry(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.uci_countries?.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          )}

          {/* 4b. Selector Dependiente: Producto UCI */}
          {selectedSource === 'uci' && (
            <div>
              <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
                PRODUCTO (STOCKCODE)
              </label>
              <select
                value={selectedProduct}
                onChange={e => setSelectedProduct(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #475569', color: '#f8fafc', padding: '7px 10px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                {metadataList?.uci_top_products?.map(p => (
                  <option key={p.stock_code} value={p.stock_code}>
                    {p.stock_code} · {p.description ? p.description.substring(0, 16) : 'N/A'} ({p.total_units} u)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 5. Horizonte de Predicción */}
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4, fontWeight: 600 }}>
              HORIZONTE DE PREDICCIÓN
            </label>
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
              <div>Calculando pronóstico de demanda y bandas de incertidumbre...</div>
            </div>
          ) : forecastResult?.sufficient_history ? (
            <div>
              {/* KPIs de la combinación seleccionada */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginBottom: 18 }}>
                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Demanda Promedio</span>
                  <strong style={{ fontSize: 18, color: '#38bdf8' }}>{forecastResult.avg_demand} u/sem</strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Media observada</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Tendencia Reciente</span>
                  <strong style={{
                    fontSize: 16,
                    color: forecastResult.trend === 'CRECIENTE' ? '#4ade80' : forecastResult.trend === 'DECRECIENTE' ? '#f87171' : '#fbbf24'
                  }}>
                    {forecastResult.trend}
                  </strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Dirección de serie</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Variabilidad (Std Dev)</span>
                  <strong style={{ fontSize: 18, color: '#fbbf24' }}>±{forecastResult.variability_std}</strong>
                  <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Desviación estándar (σ)</small>
                </div>

                <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Observaciones</span>
                  <strong style={{ fontSize: 18, color: '#a78bfa' }}>{forecastResult.observations} semanas</strong>
                  <small style={{ color: '#4ade80', display: 'block', fontSize: 10 }}>✓ Historial suficiente (≥10)</small>
                </div>

                {forecastResult.metrics?.WAPE !== undefined && (
                  <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, border: '1px solid #334155' }}>
                    <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>WAPE del Segmento</span>
                    <strong style={{ fontSize: 18, color: '#34d399' }}>{forecastResult.metrics.WAPE}%</strong>
                    <small style={{ color: '#64748b', display: 'block', fontSize: 10 }}>MAE: {forecastResult.metrics.MAE}</small>
                  </div>
                )}
              </div>

              {/* Gráfico de Historial vs. Pronóstico vs. Bandas de Incertidumbre */}
              <div style={{ background: '#1e293b', padding: '16px', borderRadius: 8, border: '1px solid #334155' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                  <strong style={{ fontSize: 13, color: '#f8fafc' }}>
                    Serie Histórica vs. Pronóstico con Intervalo de Confianza 95% (±1.96σ)
                  </strong>
                  <div style={{ display: 'flex', gap: 14, fontSize: 11 }}>
                    <span style={{ color: '#38bdf8' }}>● Demanda Real</span>
                    <span style={{ color: '#10b981' }}>● Demanda Pronosticada</span>
                    <span style={{ color: '#94a3b8' }}>┄ Bandas de Incertidumbre</span>
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
                      <Line
                        type="monotone"
                        dataKey="actual"
                        name="Demanda Real"
                        stroke="#38bdf8"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: '#38bdf8' }}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="prediccion"
                        name="Demanda Pronosticada"
                        stroke="#10b981"
                        strokeWidth={2.5}
                        dot={{ r: 4, fill: '#10b981' }}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="upper_bound"
                        name="Límite Superior (95%)"
                        stroke="#6ee7b7"
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="lower_bound"
                        name="Límite Inferior (95%)"
                        stroke="#fcd34d"
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ marginTop: 10, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Info size={13} style={{ color: '#38bdf8' }} />
                  <span>{forecastResult.note}</span>
                </div>
              </div>
            </div>
          ) : (
            /* Banner de advertencia de historial insuficiente */
            <div style={{
              background: '#451a03',
              border: '1px solid #b45309',
              borderRadius: 8,
              padding: '20px',
              color: '#fef3c7'
            }}>
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
                    <strong>Criterio Metodológico LUMINA:</strong> Para prevenir pronósticos espurios o sobreajuste severo en series temporales intermitentes,
                    la plataforma requiere al menos 10 semanas de actividad comercial continua. No se generan proyecciones sintéticas sin base estadística.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* BENCHMARK COMPARATIVO ACADÉMICO */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Benchmark Comparativo de Modelos (Backtest 888 Observaciones)</h2>
            <p>Evaluación de XGBoost frente a modelos heurísticos de persistencia y estacionalidad</p>
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
                <td><strong>7.5417</strong></td>
                <td><strong>15.9047</strong></td>
                <td><strong>35.49%</strong></td>
                <td><span style={{ color: '#34d399', fontWeight: 600 }}>★ Mejor Modelo</span></td>
              </tr>
              <tr>
                <td><strong>XGBoost Regressor</strong></td>
                <td>Supervisado (Experimental)</td>
                <td>888</td>
                <td>7.7780</td>
                <td>16.7220</td>
                <td>36.60%</td>
                <td><span style={{ color: '#38bdf8', fontWeight: 600 }}>En Producción Gold</span></td>
              </tr>
              <tr style={{ background: '#78350f22' }}>
                <td><strong>Seasonal Naive (t-52)</strong></td>
                <td>Heurístico (Estacional Anual)</td>
                <td>888</td>
                <td>12.7939</td>
                <td>27.1788</td>
                <td>60.21%</td>
                <td><span style={{ color: '#fbbf24' }}>Sesgo Interanual</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: '12px', marginTop: '10px' }}>
          <strong>Hallazgo clave:</strong> El modelo Naive (t-1) superó a XGBoost debido a la alta autocorrelación en categorías de baja rotación.
          Seasonal Naive (t-52) subestima sistemáticamente la demanda por la fuerte aceleración transaccional de Olist entre 2017 y 2018.
        </p>
      </section>

      {/* DEMANDA REAL VS PREDICHA GLOBAL */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Demanda real vs. demanda predicha (Consolidado Semanal)</h2>
            <p>Agregación semanal de las 74 categorías evaluadas en Olist</p>
          </div>
        </div>

        <div className="legend">
          <span><i style={{ background: '#38bdf8' }} /> Demanda real</span>
          <span><i style={{ background: '#10b981' }} /> Demanda predicha</span>
        </div>

        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={weekly}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
            <XAxis
              dataKey="semanaLabel"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              minTickGap={25}
            />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
              formatter={value => formatNumber(value)}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="actual"
              name="Demanda real"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="prediccion"
              name="Demanda predicha"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* CATEGORÍAS CON MAYOR ERROR */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Categorías con mayor error absoluto acumulado</h2>
            <p>Top 15 por suma del error absoluto en el periodo evaluado (12 semanas)</p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={categories} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#334155" />
            <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} />
            <YAxis
              type="category"
              dataKey="categoria"
              width={145}
              tick={{ fontSize: 10, fill: '#94a3b8' }}
            />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
              formatter={value => formatNumber(value)}
            />
            <Bar
              dataKey="error"
              name="Error absoluto acumulado"
              fill="#f59e0b"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Categoría</th>
                <th>Demanda real</th>
                <th>Demanda predicha</th>
                <th>Error absoluto</th>
              </tr>
            </thead>
            <tbody>
              {categories.map(row => (
                <tr key={row.categoria}>
                  <td>{row.categoria}</td>
                  <td>{formatNumber(row.actual)}</td>
                  <td>{formatNumber(row.prediccion)}</td>
                  <td>{formatNumber(row.error)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* INFORMACIÓN DE LA EVALUACIÓN */}
      <section className="panel">
        <h2>Información de la evaluación técnica</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginTop: '14px' }}>
          <div className="source-meta">
            <span>Modelo en Producción</span>
            <b>{metadata.model_name || 'XGBoost'}</b>
          </div>
          <div className="source-meta">
            <span>Variable Objetivo</span>
            <b>{metadata.target || 'lineas_articulo'}</b>
          </div>
          <div className="source-meta">
            <span>Inicio de Evaluación</span>
            <b>{formatDate(metadata.split_start)}</b>
          </div>
          <div className="source-meta">
            <span>Fin de Evaluación</span>
            <b>{formatDate(metadata.split_end)}</b>
          </div>
          <div className="source-meta">
            <span>Run ID WAP</span>
            <b>{metadata.run_id}</b>
          </div>
          <div className="source-meta">
            <span>Tipo de Partición</span>
            <b>{metadata.evaluation_type}</b>
          </div>
        </div>
      </section>
    </div>
  );
}
