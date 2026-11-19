import { useEffect, useState, useMemo } from 'react';
import { api } from '../services/api';
import { Store, TrendingUp, RefreshCw, ShoppingCart, DollarSign, PackageX } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import KPICard from '../components/KPICard';

const currency = (value, code) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: code || 'USD',
    maximumFractionDigits: 0
  }).format(Number(value || 0));

export default function StorePerf() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedStore, setSelectedStore] = useState('all');

  useEffect(() => {
    api.storePerformance()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const aggregated = useMemo(() => {
    const agg = {};
    data.forEach(r => {
      if (!agg[r.store_id]) {
        agg[r.store_id] = {
          store_id: r.store_id,
          store_name: r.store_name,
          location: r.location,
          currency_code: r.currency_code,
          total_orders: 0,
          completed_orders: 0,
          gross_sales: 0,
          net_sales: 0,
          total_returns: 0
        };
      }
      agg[r.store_id].total_orders += Number(r.total_orders || 0);
      agg[r.store_id].completed_orders += Number(r.completed_orders || 0);
      agg[r.store_id].gross_sales += Number(r.gross_sales || 0);
      agg[r.store_id].net_sales += Number(r.net_sales || 0);
      agg[r.store_id].total_returns += Number(r.total_returns || 0);
    });
    return Object.values(agg);
  }, [data]);

  if (loading) return <div className="panel">Cargando Store Performance...</div>;
  if (error) return <div className="panel error">{error}</div>;

  return (
    <div className="page-stack">
      <div className="filter-bar">
        <span>Unidad / Tienda Analizada</span>
        <select value={selectedStore} onChange={e => setSelectedStore(e.target.value)}>
          <option value="all">Todas las Tiendas (Visión Global)</option>
          {aggregated.map(s => (
            <option key={s.store_id} value={s.store_id}>{s.store_name} ({s.location})</option>
          ))}
        </select>
      </div>

      <section className="kpi-grid">
        {aggregated.filter(s => selectedStore === 'all' || selectedStore === s.store_id).map(s => (
          <div className="panel kpi" key={s.store_id} style={{ borderColor: s.store_id === 'olist' ? '#3b82f6' : s.store_id === 'thelook' ? '#10b981' : '#8b5cf6' }}>
            <div className="kpi-icon" style={{ background: s.store_id === 'olist' ? '#3b82f620' : s.store_id === 'thelook' ? '#10b98120' : '#8b5cf620', color: s.store_id === 'olist' ? '#3b82f6' : s.store_id === 'thelook' ? '#10b981' : '#8b5cf6' }}>
              <Store size={20} />
            </div>
            <span>{s.store_name}</span>
            <strong style={{ fontSize: 24 }}>{currency(s.net_sales, s.currency_code)}</strong>
            <small>Ventas Netas | {s.location}</small>
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Matriz Comercial y Devoluciones por Tienda</h2>
            <p>Análisis de Ventas Brutas frente a Ventas Netas y Volumen de Órdenes</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Identificador</th>
                <th>Nombre Comercial</th>
                <th>Ubicación</th>
                <th>Órdenes (Total)</th>
                <th>Órdenes (Completadas)</th>
                <th>Devoluciones</th>
                <th>Ventas Brutas</th>
                <th>Ventas Netas</th>
                <th>Divisa</th>
              </tr>
            </thead>
            <tbody>
              {aggregated.map(s => (
                <tr key={s.store_id}>
                  <td><code style={{ background: '#1e293b', padding: '2px 6px', borderRadius: 4 }}>{s.store_id}</code></td>
                  <td style={{ fontWeight: 600 }}>{s.store_name}</td>
                  <td>{s.location}</td>
                  <td>{s.total_orders.toLocaleString('en-US')}</td>
                  <td>{s.completed_orders.toLocaleString('en-US')}</td>
                  <td style={{ color: s.total_returns > 0 ? '#ef4444' : '#94a3b8' }}>{s.total_returns.toLocaleString('en-US')}</td>
                  <td>{currency(s.gross_sales, s.currency_code)}</td>
                  <td style={{ color: '#10b981', fontWeight: 600 }}>{currency(s.net_sales, s.currency_code)}</td>
                  <td><span style={{ fontSize: 11, background: '#1e293b', padding: '2px 6px', borderRadius: 4 }}>{s.currency_code}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: '16px 20px', background: '#1e293b', borderRadius: '8px', marginTop: '20px', fontSize: '12px', color: '#cbd5e1' }}>
          <strong>Limitación Documentada de Modelo Dimensional:</strong> Los datos transaccionales originales de Olist (Marketplace Brasil), TheLook y UCI Online Retail (UK) carecen de granularidad verificable hacia tres tiendas físicas unificadas. Se ha mapeado cada fuente primaria como una `dim_store` independiente para preservar la integridad del dato, evitando la fabricación de métricas sintéticas.
        </div>
      </section>
    </div>
  );
}
