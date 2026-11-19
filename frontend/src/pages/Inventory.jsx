import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Package, AlertTriangle, Clock, Activity, Target } from 'lucide-react';
import { api } from '../services/api';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid
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

const currency = (value, code) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: code || 'GBP',
    maximumFractionDigits: 0
  }).format(value || 0);

export default function Inventory() {
  const [current, setCurrent] = useState([]);
  const [risks, setRisks] = useState([]);
  const [uciCatalog, setUciCatalog] = useState([]);
  const [uciCountry, setUciCountry] = useState([]);
  const [uciMonthly, setUciMonthly] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState(null);
  const [showCyber, setShowCyber] = useState(false);

  const loadInventory = useCallback(async () => {
    setError('');

    try {
      const [stockData, riskData, catData, ctryData, moData] = await Promise.all([
        api.inventoryCurrent(showCyber),
        api.inventoryRisks(showCyber),
        api.inventoryUciCatalog(),
        api.inventoryUciCountry(),
        api.inventoryUciMonthly()
      ]);

      setCurrent(stockData);
      setRisks(riskData);
      setUciCatalog(catData);
      setUciCountry(ctryData);
      setUciMonthly(moData);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message || 'No se pudo consultar el inventario.');
    } finally {
      setLoading(false);
    }
  }, [showCyber]);

  useEffect(() => {
    loadInventory();
    const interval = setInterval(loadInventory, 30000);
    return () => clearInterval(interval);
  }, [loadInventory]);

  const filteredCurrent = current;
  const filteredRisks = risks;

  const critical = filteredCurrent.filter(x => Number(x.stock_registrado) < 10).length;
  const low = filteredCurrent.filter(x =>
    Number(x.stock_registrado) >= 10 &&
    Number(x.stock_registrado) <= 20
  ).length;
  const normal = filteredCurrent.filter(x => Number(x.stock_registrado) > 20).length;
  const stale = filteredCurrent.filter(x => x.estado_frescura !== 'ACTUALIZADO').length;
  const topRisks = [...filteredRisks]
    .sort((a, b) => Number(b.porcentaje_alertas) - Number(a.porcentaje_alertas))
    .slice(0, 5);

  if (loading) {
    return <div className="panel">Consultando inventario en BigQuery...</div>;
  }

  if (error && current.length === 0) {
    return (
      <div className="panel error">
        <h3>Error al consultar inventario</h3>
        <p>{error}</p>
        <button onClick={loadInventory}>Reintentar</button>
      </div>
    );
  }

  return (
    <div className="page-stack inventory-page">
      <section className="inventory-heading">
        <div>
          <h2>Monitoreo de inventario</h2>
          <p className="muted">
            Stock registrado, frescura de telemetría y riesgo histórico por región.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', background: showCyber ? '#1e1b4b' : '#1e293b', padding: '6px 12px', borderRadius: '6px', border: `1px solid ${showCyber ? '#6366f1' : '#334155'}`, color: showCyber ? '#818cf8' : '#cbd5e1' }}>
            <input type="checkbox" checked={showCyber} onChange={e => setShowCyber(e.target.checked)} style={{ margin: 0 }} />
            Simulación Cyber Days
          </label>
          <button className="refresh" onClick={loadInventory}>
            <RefreshCw size={15}/> Actualizar
          </button>
        </div>
      </section>

      {error && <div className="panel error">{error}. Mostrando último resultado disponible.</div>}

      {stale > 0 && (
        <div className="inventory-warning">
          <AlertTriangle size={20}/>
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

      <section className="kpi-grid inventory-kpis">
        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon"><Package size={20}/></div>
          <span>Productos / regiones</span>
          <strong>{filteredCurrent.length}</strong>
          <small>Registros de stock actual</small>
        </div>

        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon critical"><AlertTriangle size={20}/></div>
          <span>Stock crítico</span>
          <strong>{critical}</strong>
          <small>Menos de 10 unidades</small>
        </div>

        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon warning"><Activity size={20}/></div>
          <span>Stock bajo</span>
          <strong>{low}</strong>
          <small>Entre 10 y 20 unidades</small>
        </div>

        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon stale"><Clock size={20}/></div>
          <span>Datos no actualizados</span>
          <strong>{stale}</strong>
          <small>Registros sin frescura vigente</small>
        </div>
      </section>

      <section className="panel">
        <div className="inventory-section-title">
          <div>
            <h3>Stock actual por región</h3>
            <p className="muted">Último valor registrado por producto y región.</p>
          </div>
          <span className="inventory-count">{normal} normales</span>
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
                  <td><strong>{item.product_id}</strong> {item.region === 'CYBER_TEST' && <span style={{ fontSize: '10px', background: '#4338ca', color: 'white', padding: '2px 6px', borderRadius: '4px', marginLeft: '6px' }}>SINTÉTICO</span>}</td>
                  <td>{item.region}</td>
                  <td><strong>{item.stock_registrado}</strong></td>
                  <td>
                    <span className={`inventory-badge ${item.estado_stock?.toLowerCase()}`}>
                      {item.estado_stock}
                    </span>
                  </td>
                  <td>
                    <span className={`inventory-badge ${
                      item.estado_frescura === 'ACTUALIZADO' ? 'fresh' : 'stale'
                    }`}>
                      {freshnessLabel(item.estado_frescura)}
                    </span>
                  </td>
                  <td>{formatDate(item.fecha_ultimo_evento)}</td>
                </tr>
              ))}
              {filteredCurrent.length === 0 && (
                <tr><td colSpan="6">No hay registros de inventario.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="inventory-section-title">
          <div>
            <h3>Riesgo histórico de inventario</h3>
            <p className="muted">
              Frecuencia de eventos críticos y stock mínimo histórico.
            </p>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Región</th>
                <th>Eventos</th>
                <th>Stock promedio</th>
                <th>Stock mínimo</th>
                <th>Alertas críticas</th>
                <th>% alertas</th>
              </tr>
            </thead>
            <tbody>
              {filteredRisks.map((item, index) => (
                <tr key={`${item.product_id}-${item.region}-${index}`} style={{ background: item.region === 'CYBER_TEST' ? '#1e1b4b' : 'transparent' }}>
                  <td><strong>{item.product_id}</strong></td>
                  <td>{item.region}</td>
                  <td>{item.total_eventos}</td>
                  <td>{Number(item.stock_promedio).toFixed(2)}</td>
                  <td>{item.stock_minimo}</td>
                  <td>
                    <span className="inventory-risk-number">
                      {item.alertas_criticas}
                    </span>
                  </td>
                  <td>{Number(item.porcentaje_alertas).toFixed(2)}%</td>
                </tr>
              ))}
              {filteredRisks.length === 0 && (
                <tr><td colSpan="7">No hay registros históricos de riesgo.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="inventory-section-title">
          <div>
            <h3>Principales focos de riesgo histórico</h3>
            <p className="muted">
              Cinco combinaciones producto-región con mayor porcentaje histórico de alertas críticas.
            </p>
          </div>
        </div>

        <div className="inventory-risk-ranking">
          {topRisks.map((item, index) => (
            <div className="inventory-risk-row" key={`${item.product_id}-${item.region}`}>
              <div className="inventory-risk-label">
                <strong>{index + 1}. {item.product_id} · {item.region}</strong>
                <span>{Number(item.porcentaje_alertas).toFixed(2)}%</span>
              </div>
              <div className="inventory-risk-track">
                <div
                  className="inventory-risk-fill"
                  style={{ width: `${Math.min(Number(item.porcentaje_alertas), 100)}%` }}
                />
              </div>
              <small>
                {item.alertas_criticas} eventos críticos de {item.total_eventos} eventos
              </small>
            </div>
          ))}
        </div>
      </section>

      <section className="inventory-heading" style={{ marginTop: '32px' }}>
        <div>
          <h2>Inventario analítico y demanda histórica — UCI Online Retail</h2>
          <p className="muted">
            UCI Online Retail proporciona registros históricos de transacciones. Los indicadores de este apartado representan actividad comercial y demanda histórica, no existencias físicas disponibles.
          </p>
        </div>
      </section>

      <section className="kpi-grid inventory-kpis">
        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon"><Package size={20}/></div>
          <span>Productos</span>
          <strong>{uciCatalog.length}</strong>
          <small>Identificados en catálogo</small>
        </div>
        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon"><Activity size={20}/></div>
          <span>Demanda Mensual</span>
          <strong>
            {uciCatalog.length > 0 
              ? Math.round(uciCatalog.reduce((sum, item) => sum + (Number(item.avg_monthly_demand) || 0), 0) / uciCatalog.length)
              : 0}
          </strong>
          <small>Unidades promedio/mes por SKU</small>
        </div>
        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon"><Target size={20}/></div>
          <span>Devoluciones</span>
          <strong>
            {uciCatalog.length > 0 
              ? Number(uciCatalog.reduce((sum, item) => sum + (Number(item.units_returned) || 0), 0)).toLocaleString('en-US')
              : 0}
          </strong>
          <small>Unidades históricas</small>
        </div>
        <div className="panel inventory-kpi">
          <div className="inventory-kpi-icon"><Target size={20}/></div>
          <span>Mercados</span>
          <strong>
            {new Set(uciCountry.map(c => c.country)).size}
          </strong>
          <small>Países activos</small>
        </div>
      </section>

      <section className="panel" style={{ marginTop: '20px' }}>
        <div className="inventory-section-title">
          <div>
            <h3>Catálogo analítico de productos (UCI)</h3>
            <p className="muted">Top 100 productos de mayor rotación comercial en el registro transaccional.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Código (StockCode)</th>
                <th>Descripción</th>
                <th>Unid. Vendidas</th>
                <th>Devueltas</th>
                <th>Netas</th>
                <th>Demanda Prom. Mensual</th>
                <th>Clase ABC</th>
                <th>Ingresos Históricos</th>
              </tr>
            </thead>
            <tbody>
              {uciCatalog.map((item, index) => (
                <tr key={`${item.stock_code}-${index}`}>
                  <td><strong>{item.stock_code}</strong></td>
                  <td>{item.description || 'N/A'}</td>
                  <td>{item.units_sold}</td>
                  <td>{item.units_returned}</td>
                  <td><strong>{item.units_net}</strong></td>
                  <td>{Number(item.avg_monthly_demand || 0).toFixed(1)}</td>
                  <td>
                    <span className={`inventory-badge ${item.abc_class === 'A' ? 'fresh' : item.abc_class === 'B' ? 'stale' : 'warning'}`}>
                      {item.abc_class}
                    </span>
                  </td>
                  <td>{currency(item.gross_revenue_gbp, 'GBP')}</td>
                </tr>
              ))}
              {uciCatalog.length === 0 && (
                <tr><td colSpan="8">No hay registros analíticos disponibles para UCI.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" style={{ marginTop: '20px' }}>
        <div className="inventory-section-title">
          <div>
            <h3>Evolución histórica de demanda (UCI)</h3>
            <p className="muted">Curva de demanda global en el periodo transaccional reportado (Dic 2010 - Dic 2011).</p>
          </div>
        </div>
        <div className="chart-box" style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={uciMonthly}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155"/>
              <XAxis dataKey="sales_month" stroke="#94a3b8" fontSize={12} tickFormatter={v => value => new Date(value).toLocaleDateString('es-PE', { month: 'short', year: '2-digit' })} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px', color: '#f8fafc' }}
                itemStyle={{ color: '#e2e8f0' }}
                labelFormatter={v => new Date(v).toLocaleDateString('es-PE', { month: 'long', year: 'numeric' })}
              />
              <Line type="monotone" dataKey="total_units_sold" name="Unidades Vendidas" stroke="#818cf8" strokeWidth={3} dot={{ r: 4, fill: '#818cf8', strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <div className="inventory-footer">
        <span>
          <Clock size={13}/> Actualización automática cada 30 segundos
        </span>
        <span>
          Última consulta: {lastRefresh ? lastRefresh.toLocaleTimeString('es-PE') : 'Pendiente'}
        </span>
      </div>
    </div>
  );
}
