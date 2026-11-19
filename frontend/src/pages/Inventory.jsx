import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Package, AlertTriangle, Clock, Activity } from 'lucide-react';
import { api } from '../services/api';

function formatDate(value) {
  if (!value) return 'Sin registro';
  return new Date(value).toLocaleString('es-PE');
}

function freshnessLabel(value) {
  if (value === 'ACTUALIZADO') return 'Actualizado';
  if (value === 'DESACTUALIZADO') return 'Desactualizado';
  return 'Sin fecha';
}

export default function Inventory() {
  const [current, setCurrent] = useState([]);
  const [risks, setRisks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState(null);
  const [showCyber, setShowCyber] = useState(false);

  const loadInventory = useCallback(async () => {
    setError('');

    try {
      const [stockData, riskData] = await Promise.all([
        api.inventoryCurrent(),
        api.inventoryRisks()
      ]);

      setCurrent(stockData);
      setRisks(riskData);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message || 'No se pudo consultar el inventario.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInventory();
    const interval = setInterval(loadInventory, 30000);
    return () => clearInterval(interval);
  }, [loadInventory]);

  const filteredCurrent = showCyber ? current : current.filter(x => x.region !== 'CYBER_TEST');
  const filteredRisks = showCyber ? risks : risks.filter(x => x.region !== 'CYBER_TEST');

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
