import { useEffect, useState } from 'react';
import { api } from '../services/api';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid
} from 'recharts';

function Metric({ label, value, suffix = '' }) {
  return (
    <div className="metric-box">
      <span>{label}</span>
      <strong>
        {value === null || value === undefined
          ? 'No disponible'
          : `${Number(value).toLocaleString('en-US')}${suffix}`}
      </strong>
    </div>
  );
}

export default function Logistics() {
  const [rows, setRows] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.logistics(), api.logisticsMonthly()])
      .then(([summary, history]) => {
        setRows(summary);
        setMonthly(history);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="panel">Cargando indicadores logísticos...</div>;
  if (error) return <div className="panel error">{error}</div>;

  return (
    <div className="page-stack">
      <div className="source-grid">
        {rows.map(row => (
          <section className="panel" key={row.source_system}>
            <span className="eyebrow">{row.source_label}</span>
            <h2 className="logistics-title">Indicadores operativos</h2>
            <div className="metric-grid">
              <Metric label="Pedidos" value={row.total_orders}/>
              <Metric label="Envíos válidos" value={row.valid_shipments}/>
              <Metric label="Entregas válidas" value={row.valid_deliveries}/>
              <Metric label="Devoluciones válidas" value={row.valid_returns}/>
              <Metric label="Cobertura de envíos" value={row.shipment_coverage_pct} suffix="%"/>
              <Metric label="Cobertura de entregas" value={row.delivery_coverage_pct} suffix="%"/>
              <Metric label="Entregas tardías" value={row.late_deliveries}/>
              <Metric label="Tasa de tardanza" value={row.late_delivery_rate_pct} suffix="%"/>
            </div>
            <p className="muted">
              Disponibilidad de datos de tardanza: {row.late_delivery_data_status}
            </p>
          </section>
        ))}
      </div>

      <section className="panel">
        <h2>Calidad de la secuencia logística</h2>
        <p className="muted">Incidencias detectadas en los eventos de envío y entrega.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fuente</th>
                <th>Secuencia de envío inválida</th>
                <th>Secuencia de entrega inválida</th>
                <th>Entrega sin envío</th>
                <th>Envíos futuros</th>
                <th>Entregas futuras</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.source_system}>
                  <td>{row.source_label}</td>
                  <td>{Number(row.invalid_shipping_sequence).toLocaleString()}</td>
                  <td>{Number(row.invalid_delivery_sequence).toLocaleString()}</td>
                  <td>{Number(row.delivery_without_shipment).toLocaleString()}</td>
                  <td>{Number(row.future_shipments).toLocaleString()}</td>
                  <td>{Number(row.future_deliveries).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>Evolución mensual de pedidos y entregas</h2>
        <p className="muted">Serie por fuente y mes de cohorte del pedido.</p>
        {['olist', 'thelook'].map(source => {
          const data = monthly.filter(x => x.source_system === source);
          return (
            <div className="chart-section" key={source}>
              <h3>{source === 'olist' ? 'Olist' : 'TheLook'}</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false}/>
                  <XAxis dataKey="order_cohort_month" tick={{fontSize: 10}}/>
                  <YAxis/>
                  <Tooltip/>
                  <Bar dataKey="valid_shipments" name="Envíos" fill="#3B82F6"/>
                  <Bar dataKey="valid_deliveries" name="Entregas" fill="#10B981"/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </section>
    </div>
  );
}
