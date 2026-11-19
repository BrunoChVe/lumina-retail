import { useCallback, useEffect, useState, useMemo } from 'react';
import {
  RefreshCw, Package, AlertTriangle, Clock, Activity, Target,
  TrendingUp, Globe, BarChart3, Search, Filter, Layers, DollarSign
} from 'lucide-react';
import { api } from '../services/api';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend, Cell
} from 'recharts';

function formatDate(value) {
  if (!value) return 'Sin registro';
  return new Date(value).toLocaleString('es-PE');
}

function freshnessLabel(value) {
  if (value === 'ACTUALIZADO') return 'Actualizado';
  if (value === 'DESACTUALIZADO') return 'Desactualizado';
  return 'Sin fecha';
}

const currencyGBP = (value) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'GBP',
    maximumFractionDigits: 0
  }).format(Number(value || 0));

const formatCompact = (val) =>
  new Intl.NumberFormat('en-US', { notation: 'compact', compactDisplay: 'short' }).format(Number(val || 0));

export default function Inventory() {
  // Estado Inventario Operativo (Streaming)
  const [current, setCurrent] = useState([]);
  const [risks, setRisks] = useState([]);
  const [showCyber, setShowCyber] = useState(false);

  // Estado Inventario Analítico UCI
  const [uciSummary, setUciSummary] = useState(null);
  const [uciMonthly, setUciMonthly] = useState([]);
  const [uciCatalog, setUciCatalog] = useState([]);
  const [uciCountry, setUciCountry] = useState([]);

  // Estados de control y UI
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState(null);

  // Filtros interactivos para UCI
  const [monthlyMetric, setMonthlyMetric] = useState('all'); // 'all', 'sold', 'returned', 'net'
  const [searchCatalog, setSearchCatalog] = useState('');
  const [abcFilter, setAbcFilter] = useState('ALL');

  const loadAllData = useCallback(async () => {
    setError('');
    try {
      const [stockData, riskData, summaryData, moData, catData, ctryData] = await Promise.all([
        api.inventoryCurrent(showCyber),
        api.inventoryRisks(showCyber),
        api.inventoryUciSummary().catch(() => []),
        api.inventoryUciMonthly().catch(() => []),
        api.inventoryUciCatalog(100).catch(() => []),
        api.inventoryUciCountry().catch(() => [])
      ]);

      setCurrent(stockData || []);
      setRisks(riskData || []);
      if (summaryData && summaryData.length > 0) {
        setUciSummary(summaryData[0]);
      }
      setUciMonthly(moData || []);
      setUciCatalog(catData || []);
      setUciCountry(ctryData || []);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message || 'Error al consultar inventario y telemetría.');
    } finally {
      setLoading(false);
    }
  }, [showCyber]);

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 30000);
    return () => clearInterval(interval);
  }, [loadAllData]);

  // Métricas derivadas inventario operativo
  const filteredCurrent = current;
  const filteredRisks = risks;
  const critical = filteredCurrent.filter(x => Number(x.stock_registrado) < 10).length;
  const low = filteredCurrent.filter(x =>
    Number(x.stock_registrado) >= 10 && Number(x.stock_registrado) <= 20
  ).length;
  const normal = filteredCurrent.filter(x => Number(x.stock_registrado) > 20).length;
  const stale = filteredCurrent.filter(x => x.estado_frescura !== 'ACTUALIZADO').length;
  const topRisks = [...filteredRisks]
    .sort((a, b) => Number(b.porcentaje_alertas) - Number(a.porcentaje_alertas))
    .slice(0, 5);

  // Top 10 productos más demandados para Gráfico 2
  const topDemandProducts = useMemo(() => {
    return [...uciCatalog]
      .sort((a, b) => (Number(b.units_sold) || 0) - (Number(a.units_sold) || 0))
      .slice(0, 10)
      .map(p => ({
        ...p,
        shortDesc: p.description && p.description.length > 22
          ? `${p.description.substring(0, 22)}...`
          : p.description || p.stock_code
      }));
  }, [uciCatalog]);

  // Datos para Gráfico 3: Distribución ABC
  const abcChartData = useMemo(() => {
    if (!uciSummary) return [];
    const total = (uciSummary.count_a || 0) + (uciSummary.count_b || 0) + (uciSummary.count_c || 0) || 1;
    return [
      {
        name: 'Clase A (70% Ingresos)',
        skus: uciSummary.count_a || 0,
        pct: Number(((uciSummary.count_a || 0) / total * 100).toFixed(1)),
        revenuePct: '70% ingresos',
        color: '#10b981'
      },
      {
        name: 'Clase B (20% Ingresos)',
        skus: uciSummary.count_b || 0,
        pct: Number(((uciSummary.count_b || 0) / total * 100).toFixed(1)),
        revenuePct: '20% ingresos',
        color: '#f59e0b'
      },
      {
        name: 'Clase C (10% Ingresos)',
        skus: uciSummary.count_c || 0,
        pct: Number(((uciSummary.count_c || 0) / total * 100).toFixed(1)),
        revenuePct: '10% ingresos',
        color: '#64748b'
      }
    ];
  }, [uciSummary]);

  // Top 10 Países para Gráfico 4
  const topCountriesData = useMemo(() => {
    return [...uciCountry].slice(0, 10);
  }, [uciCountry]);

  // Filtrado de la tabla de catálogo analítico
  const filteredCatalog = useMemo(() => {
    return uciCatalog.filter(item => {
      const matchSearch =
        searchCatalog === '' ||
        (item.stock_code && item.stock_code.toLowerCase().includes(searchCatalog.toLowerCase())) ||
        (item.description && item.description.toLowerCase().includes(searchCatalog.toLowerCase()));
      const matchAbc = abcFilter === 'ALL' || item.abc_class === abcFilter;
      return matchSearch && matchAbc;
    });
  }, [uciCatalog, searchCatalog, abcFilter]);

  if (loading && current.length === 0) {
    return <div className="panel" style={{ padding: 40, textAlign: 'center' }}>Consultando inventario en BigQuery y telemetría de streaming...</div>;
  }

  return (
    <div className="page-stack inventory-page">
      {/* ========================================================================= */}
      {/* SECCIÓN 1: INVENTARIO OPERATIVO EN TIEMPO REAL (STREAMING KAFKA / SPARK)  */}
      {/* ========================================================================= */}
      <section className="inventory-heading">
        <div>
          <h2>Control de Inventario Operativo</h2>
          <p className="muted">
            Telemetría de stock en tiempo real (Spark Streaming), niveles de existencias y riesgo por región (Olist / RetailSmart).
          </p>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <label style={{
            display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer',
            background: showCyber ? '#1e1b4b' : '#1e293b', padding: '6px 12px', borderRadius: '6px',
            border: `1px solid ${showCyber ? '#6366f1' : '#334155'}`, color: showCyber ? '#818cf8' : '#cbd5e1'
          }}>
            <input type="checkbox" checked={showCyber} onChange={e => setShowCyber(e.target.checked)} style={{ margin: 0 }} />
            Simulación Cyber Days
          </label>
          <button className="refresh" onClick={loadAllData}>
            <RefreshCw size={15} /> Actualizar
          </button>
        </div>
      </section>

      {error && <div className="panel error">{error}. Mostrando último resultado disponible.</div>}

      {stale > 0 && (
        <div className="inventory-warning">
          <AlertTriangle size={20} />
          <div>
            <strong>Atención: telemetría desactualizada</strong>
            <p>
              {stale} de {filteredCurrent.length} registros superan el umbral de frescura
              de cinco minutos. Los valores mostrados corresponden al último
              stock registrado y no necesariamente al stock disponible actual.
            </p>
          </div>
        </div>
      )}

      {/* Tarjetas KPI Inventario Operativo */}
      <section className="kpi-grid inventory-kpis">
        <div className="panel kpi">
          <div className="kpi-icon"><Package size={20} /></div>
          <span>Productos / regiones</span>
          <strong>{filteredCurrent.length}</strong>
          <small>Registros de stock actual</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-icon" style={{ background: '#7f1d1d', color: '#f87171' }}><AlertTriangle size={20} /></div>
          <span>Stock crítico</span>
          <strong style={{ color: '#f87171' }}>{critical}</strong>
          <small>Menos de 10 unidades</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-icon" style={{ background: '#78350f', color: '#fbbf24' }}><Activity size={20} /></div>
          <span>Stock bajo</span>
          <strong style={{ color: '#fbbf24' }}>{low}</strong>
          <small>Entre 10 y 20 unidades</small>
        </div>

        <div className="panel kpi">
          <div className="kpi-icon"><Clock size={20} /></div>
          <span>Datos no actualizados</span>
          <strong>{stale}</strong>
          <small>Registros sin frescura vigente</small>
        </div>
      </section>

      {/* Tabla Stock Actual */}
      <section className="panel">
        <div className="inventory-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h3>Stock actual por región</h3>
            <p className="muted">Último valor registrado por producto y región vía telemetría en streaming.</p>
          </div>
          <span className="inventory-count" style={{ fontSize: 13, color: '#94a3b8' }}>{normal} en nivel normal</span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Región</th>
                <th>Stock</th>
                <th>Estado de stock</th>
                <th>Frescura</th>
                <th>Último evento</th>
              </tr>
            </thead>
            <tbody>
              {filteredCurrent.map((item, index) => (
                <tr key={`${item.product_id}-${item.region}-${index}`} style={{ background: item.region === 'CYBER_TEST' ? '#1e1b4b' : 'transparent' }}>
                  <td>
                    <strong>{item.product_id}</strong>
                    {item.region === 'CYBER_TEST' && (
                      <span style={{ fontSize: '10px', background: '#4338ca', color: 'white', padding: '2px 6px', borderRadius: '4px', marginLeft: '6px' }}>
                        SINTÉTICO
                      </span>
                    )}
                  </td>
                  <td>{item.region}</td>
                  <td><strong>{item.stock_registrado}</strong></td>
                  <td>
                    <span className={`inventory-badge ${item.estado_stock?.toLowerCase()}`}>
                      {item.estado_stock}
                    </span>
                  </td>
                  <td>
                    <span className={`inventory-badge ${item.estado_frescura === 'ACTUALIZADO' ? 'fresh' : 'stale'}`}>
                      {freshnessLabel(item.estado_frescura)}
                    </span>
                  </td>
                  <td>{formatDate(item.fecha_ultimo_evento)}</td>
                </tr>
              ))}
              {filteredCurrent.length === 0 && (
                <tr><td colSpan="6" style={{ textAlign: 'center', padding: 20 }}>No hay registros de inventario operativo.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Riesgos Históricos */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', marginTop: '10px' }}>
        <section className="panel">
          <div className="inventory-section-title" style={{ marginBottom: 16 }}>
            <div>
              <h3>Riesgo histórico de inventario</h3>
              <p className="muted">Frecuencia de eventos críticos y stock mínimo registrado.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Región</th>
                  <th>Stock mín.</th>
                  <th>Alertas</th>
                  <th>% Alertas</th>
                </tr>
              </thead>
              <tbody>
                {filteredRisks.slice(0, 7).map((item, index) => (
                  <tr key={`${item.product_id}-${item.region}-${index}`} style={{ background: item.region === 'CYBER_TEST' ? '#1e1b4b' : 'transparent' }}>
                    <td><strong>{item.product_id}</strong></td>
                    <td>{item.region}</td>
                    <td>{item.stock_minimo}</td>
                    <td><span className="inventory-risk-number" style={{ color: '#f87171' }}>{item.alertas_criticas}</span></td>
                    <td>{Number(item.porcentaje_alertas).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="inventory-section-title" style={{ marginBottom: 16 }}>
            <div>
              <h3>Top 5 focos de riesgo histórico</h3>
              <p className="muted">Combinaciones producto-región con mayor tasa histórica de alertas críticas.</p>
            </div>
          </div>
          <div className="inventory-risk-ranking" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {topRisks.map((item, index) => (
              <div className="inventory-risk-row" key={`${item.product_id}-${item.region}`} style={{ background: '#0f172a', padding: '10px 14px', borderRadius: 8 }}>
                <div className="inventory-risk-label" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <strong style={{ fontSize: 13 }}>{index + 1}. {item.product_id} · {item.region}</strong>
                  <span style={{ color: '#f87171', fontWeight: 600 }}>{Number(item.porcentaje_alertas).toFixed(1)}%</span>
                </div>
                <div className="inventory-risk-track" style={{ height: 6, background: '#334155', borderRadius: 3, overflow: 'hidden' }}>
                  <div
                    className="inventory-risk-fill"
                    style={{ width: `${Math.min(Number(item.porcentaje_alertas), 100)}%`, height: '100%', background: '#ef4444' }}
                  />
                </div>
                <small style={{ color: '#94a3b8', marginTop: 4, display: 'block', fontSize: 11 }}>
                  {item.alertas_criticas} eventos críticos de {item.total_eventos} observaciones
                </small>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* ========================================================================= */}
      {/* SECCIÓN 2: ANÁLISIS DE INVENTARIO Y DEMANDA HISTÓRICA — UCI ONLINE RETAIL  */}
      {/* ========================================================================= */}
      <div style={{ marginTop: 48, borderTop: '2px solid #334155', paddingTop: 32 }}>
        <section className="inventory-heading">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ background: '#0284c7', color: 'white', fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                FUENTE: UCI ONLINE RETAIL (UK / EUROPA)
              </span>
              <span style={{ color: '#94a3b8', fontSize: 12 }}>Periodo: Dic 2010 – Dic 2011 (53 semanas)</span>
            </div>
            <h2 style={{ fontSize: 22, color: '#38bdf8' }}>ANÁLISIS DE INVENTARIO Y DEMANDA HISTÓRICA — UCI ONLINE RETAIL</h2>
            <p className="muted" style={{ maxWidth: 900 }}>
              UCI Online Retail proporciona registros históricos de transacciones. Los indicadores de este apartado representan
              <strong> actividad comercial y demanda histórica, no existencias físicas disponibles</strong> ni stock en almacén.
            </p>
          </div>
        </section>

        {/* A. Indicadores Principales (KPI Cards) */}
        <section className="kpi-grid" style={{ marginTop: 20 }}>
          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#0369a1', color: '#e0f2fe' }}><Package size={20} /></div>
            <span>Total de Productos</span>
            <strong>{uciSummary ? Number(uciSummary.total_products).toLocaleString('en-US') : '3,941'}</strong>
            <small>SKUs con actividad histórica</small>
          </div>

          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#047857', color: '#d1fae5' }}><TrendingUp size={20} /></div>
            <span>Unidades Comercializadas</span>
            <strong>{uciSummary ? formatCompact(uciSummary.total_units_sold) : '5.66M'}</strong>
            <small>{uciSummary ? Number(uciSummary.total_units_sold).toLocaleString('en-US') : '5,660,981'} unidades brutas</small>
          </div>

          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#991b1b', color: '#fee2e2' }}><AlertTriangle size={20} /></div>
            <span>Unidades Devueltas</span>
            <strong style={{ color: '#f87171' }}>{uciSummary ? formatCompact(uciSummary.total_units_returned) : '458K'}</strong>
            <small>{uciSummary ? Number(uciSummary.total_units_returned).toLocaleString('en-US') : '458,319'} unidades negativas</small>
          </div>

          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#6b21a8', color: '#f3e8ff' }}><DollarSign size={20} /></div>
            <span>Ingresos Históricos (GBP)</span>
            <strong style={{ color: '#c084fc' }}>{uciSummary ? currencyGBP(uciSummary.total_revenue_gbp) : '£10,666,685'}</strong>
            <small>Moneda original: GBP</small>
          </div>

          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#1e3a8a', color: '#dbeafe' }}><Globe size={20} /></div>
            <span>Países Comerciales</span>
            <strong>{uciSummary ? uciSummary.total_countries : '38'}</strong>
            <small>Mercados internacionales</small>
          </div>

          <div className="panel kpi">
            <div className="kpi-icon" style={{ background: '#374151', color: '#f3f4f6' }}><Clock size={20} /></div>
            <span>Periodo Histórico</span>
            <strong style={{ fontSize: 15 }}>13 Meses</strong>
            <small>Dic 2010 a Dic 2011</small>
          </div>
        </section>

        {/* B. Gráfico 1 — Evolución Mensual de Demanda */}
        <section className="panel" style={{ marginTop: 24 }}>
          <div className="inventory-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div>
              <h3>Evolución Mensual de Demanda — UCI Online Retail</h3>
              <p className="muted">Comportamiento mensual de unidades vendidas brutas, devoluciones registradas y demanda neta.</p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { id: 'all', label: 'Todas las series' },
                { id: 'sold', label: 'Unidades vendidas' },
                { id: 'returned', label: 'Devoluciones' },
                { id: 'net', label: 'Demanda neta' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setMonthlyMetric(tab.id)}
                  style={{
                    background: monthlyMetric === tab.id ? '#0284c7' : '#1e293b',
                    color: monthlyMetric === tab.id ? 'white' : '#94a3b8',
                    border: '1px solid #334155',
                    borderRadius: 6,
                    padding: '6px 12px',
                    fontSize: 12,
                    cursor: 'pointer'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="chart-box" style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={uciMonthly} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="sales_month"
                  stroke="#94a3b8"
                  fontSize={11}
                  tickFormatter={val => {
                    if (!val) return '';
                    const d = new Date(val);
                    return isNaN(d) ? String(val) : d.toLocaleDateString('es-PE', { month: 'short', year: '2-digit' });
                  }}
                />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={formatCompact} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                  labelFormatter={val => new Date(val).toLocaleDateString('es-PE', { month: 'long', year: 'numeric' })}
                  formatter={(val, name) => [Number(val).toLocaleString('en-US'), name]}
                />
                <Legend wrapperStyle={{ paddingTop: 10 }} />
                {(monthlyMetric === 'all' || monthlyMetric === 'sold') && (
                  <Bar dataKey="total_units_sold" name="Unidades Comercializadas" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                )}
                {(monthlyMetric === 'all' || monthlyMetric === 'returned') && (
                  <Bar dataKey="total_units_returned" name="Unidades Devueltas" fill="#f87171" radius={[4, 4, 0, 0]} />
                )}
                {(monthlyMetric === 'all' || monthlyMetric === 'net') && (
                  <Bar dataKey="total_units_net" name="Unidades Netas" fill="#10b981" radius={[4, 4, 0, 0]} />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Fila con Gráfico 2 (Top Productos) y Gráfico 3 (Clasificación ABC) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px', marginTop: '20px' }}>
          {/* C. Gráfico 2 — Productos con Mayor Demanda */}
          <section className="panel">
            <div className="inventory-section-title" style={{ marginBottom: 16 }}>
              <div>
                <h3>Top 10 Productos con Mayor Demanda</h3>
                <p className="muted">Ranking de SKUs por volumen total de unidades comercializadas en UCI.</p>
              </div>
            </div>
            <div className="chart-box" style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topDemandProducts} layout="vertical" margin={{ left: 10, right: 30, top: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                  <XAxis type="number" stroke="#94a3b8" fontSize={11} tickFormatter={formatCompact} />
                  <YAxis type="category" dataKey="shortDesc" stroke="#94a3b8" width={150} fontSize={11} />
                  <Tooltip
                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                    formatter={(val, name, item) => [
                      `${Number(val).toLocaleString('en-US')} unidades (${currencyGBP(item.payload.gross_revenue_gbp)})`,
                      `SKU: ${item.payload.stock_code}`
                    ]}
                  />
                  <Bar dataKey="units_sold" name="Unidades Vendidas" fill="#818cf8" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* D. Gráfico 3 — Clasificación ABC */}
          <section className="panel">
            <div className="inventory-section-title" style={{ marginBottom: 16 }}>
              <div>
                <h3>Distribución de Catálogo por Clasificación ABC</h3>
                <p className="muted">Estratificación de SKUs según contribución acumulada a los ingresos históricos (GBP).</p>
              </div>
            </div>
            <div className="chart-box" style={{ height: 210 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={abcChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                    formatter={(val, name, item) => [`${val} SKUs (${item.payload.pct}%)`, item.payload.revenuePct]}
                  />
                  <Bar dataKey="skus" name="Cantidad de SKUs" radius={[4, 4, 0, 0]}>
                    {abcChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 12 }}>
              <div style={{ background: '#064e3b', padding: '10px 12px', borderRadius: 6 }}>
                <strong style={{ color: '#34d399', fontSize: 13, display: 'block' }}>Clase A (524 SKUs)</strong>
                <span style={{ fontSize: 11, color: '#a7f3d0' }}>70% de ventas acumuladas (13.3% del catálogo)</span>
              </div>
              <div style={{ background: '#78350f', padding: '10px 12px', borderRadius: 6 }}>
                <strong style={{ color: '#fbbf24', fontSize: 13, display: 'block' }}>Clase B (789 SKUs)</strong>
                <span style={{ fontSize: 11, color: '#fde68a' }}>20% de ventas acumuladas (20.0% del catálogo)</span>
              </div>
              <div style={{ background: '#1e293b', padding: '10px 12px', borderRadius: 6 }}>
                <strong style={{ color: '#cbd5e1', fontSize: 13, display: 'block' }}>Clase C (2,628 SKUs)</strong>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>10% de ventas acumuladas (66.7% del catálogo)</span>
              </div>
            </div>
          </section>
        </div>

        {/* E. Gráfico 4 — Demanda por País */}
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="inventory-section-title" style={{ marginBottom: 16 }}>
            <div>
              <h3>Demanda y Volumen Comercializado por País (Top 10 Mercados)</h3>
              <p className="muted">Distribución de unidades comercializadas e ingresos generados por mercado geográfico.</p>
            </div>
          </div>
          <div className="chart-box" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCountriesData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="country" stroke="#94a3b8" fontSize={11} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={formatCompact} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                  formatter={(val, name, item) => [
                    `${Number(val).toLocaleString('en-US')} unidades (${currencyGBP(item.payload.total_revenue)})`,
                    item.payload.country
                  ]}
                />
                <Bar dataKey="total_units_sold" name="Unidades Comercializadas" fill="#0284c7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* F. Tabla de Catálogo Analítico con Filtros */}
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="inventory-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div>
              <h3>Catálogo Analítico de Productos UCI</h3>
              <p className="muted">Catálogo detallado con unidades comercializadas, devoluciones, rotación y clasificación ABC.</p>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#0f172a', padding: '6px 12px', borderRadius: 6, border: '1px solid #334155' }}>
                <Search size={14} style={{ color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Buscar por código o descripción..."
                  value={searchCatalog}
                  onChange={e => setSearchCatalog(e.target.value)}
                  style={{ background: 'transparent', border: 'none', color: '#f8fafc', fontSize: 12, outline: 'none', width: 200 }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Filter size={14} style={{ color: '#94a3b8' }} />
                <select
                  value={abcFilter}
                  onChange={e => setAbcFilter(e.target.value)}
                  style={{ background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: 12, borderRadius: 6, padding: '6px 10px', outline: 'none' }}
                >
                  <option value="ALL">Todas las Clases ABC</option>
                  <option value="A">Clase A (Top 70%)</option>
                  <option value="B">Clase B (20%)</option>
                  <option value="C">Clase C (10%)</option>
                </select>
              </div>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>StockCode</th>
                  <th>Descripción</th>
                  <th>Unidades Comercializadas</th>
                  <th>Devoluciones</th>
                  <th>Unidades Netas</th>
                  <th>Demanda Prom. Mensual</th>
                  <th>Precio Prom. (GBP)</th>
                  <th>Clase ABC</th>
                  <th>Ingresos Históricos</th>
                </tr>
              </thead>
              <tbody>
                {filteredCatalog.slice(0, 50).map((item, index) => (
                  <tr key={`${item.stock_code}-${index}`}>
                    <td><strong>{item.stock_code}</strong></td>
                    <td style={{ maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.description || 'Sin descripción'}
                    </td>
                    <td>{Number(item.units_sold || 0).toLocaleString('en-US')}</td>
                    <td style={{ color: Number(item.units_returned) > 0 ? '#f87171' : 'inherit' }}>
                      {Number(item.units_returned || 0).toLocaleString('en-US')}
                    </td>
                    <td><strong>{Number(item.units_net || 0).toLocaleString('en-US')}</strong></td>
                    <td>{Number(item.avg_monthly_demand || 0).toFixed(1)} u/mes</td>
                    <td>£{Number(item.avg_unit_price || 0).toFixed(2)}</td>
                    <td>
                      <span className={`inventory-badge ${item.abc_class === 'A' ? 'fresh' : item.abc_class === 'B' ? 'stale' : 'warning'}`}>
                        Clase {item.abc_class}
                      </span>
                    </td>
                    <td><strong>{currencyGBP(item.gross_revenue_gbp)}</strong></td>
                  </tr>
                ))}
                {filteredCatalog.length === 0 && (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: 24, color: '#94a3b8' }}>
                      No se encontraron productos en el catálogo UCI con los filtros seleccionados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 10, fontSize: 11, color: '#64748b', textAlign: 'right' }}>
            Mostrando {Math.min(filteredCatalog.length, 50)} de {filteredCatalog.length} productos coincidentes
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="inventory-footer" style={{ marginTop: 32 }}>
        <span>
          <Clock size={13} /> Actualización automática cada 30 segundos
        </span>
        <span>
          Última consulta: {lastRefresh ? lastRefresh.toLocaleTimeString('es-PE') : 'Pendiente'}
        </span>
      </div>
    </div>
  );
}
