import {
  ShoppingCart, Package, Truck, Activity
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts';
import KPICard from '../components/KPICard';

export default function Overview({ commercial, logistics, monthly }) {
  const sum = (data, field) =>
    data.reduce((total, row) => total + Number(row[field] || 0), 0);

  const orders = sum(commercial, 'total_orders');
  const completed = sum(commercial, 'completed_orders');
  const shipments = sum(logistics, 'valid_shipments');
  const deliveries = sum(logistics, 'valid_deliveries');

  const olist = monthly.filter(x => x.source_system === 'olist');
  const thelook = monthly.filter(x => x.source_system === 'thelook');
  const uci = monthly.filter(x => x.source_system === 'uci');

  return (
    <>
      <div className="welcome">
        <div>
          <span className="eyebrow">VISIÓN GENERAL</span>
          <h2>Inteligencia para mejores decisiones.</h2>
          <p>Información comercial y logística multisource auditada y gobernada.</p>
        </div>
      </div>

      <div className="kpi-grid">
        <KPICard icon={ShoppingCart} label="Pedidos registrados"
          value={orders.toLocaleString('en-US')} />
        <KPICard icon={Package} label="Pedidos completados"
          value={completed.toLocaleString('en-US')} />
        <KPICard icon={Truck} label="Envíos válidos"
          value={shipments.toLocaleString('en-US')} />
        <KPICard icon={Activity} label="Entregas válidas"
          value={deliveries.toLocaleString('en-US')} />
      </div>

      <div className="section-heading">
        <div>
          <h2>Evolución comercial</h2>
          <p>Ventas mensuales por fuente, sin mezclar monedas (Aislamiento de divisas BRL, USD y GBP)</p>
        </div>
      </div>

      <div className="panel">
        <div className="legend">
          <span><i className="olist" /> Olist (BRL)</span>
          <span><i className="thelook" /> TheLook (USD)</span>
          <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#8B5CF6', marginRight: 6 }} /> UCI Online Retail (GBP)</span>
        </div>

        <div className="chart-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
          <div>
            <h3>Olist · BRL</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={olist}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="order_month" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Line dataKey="total_product_sales" stroke="#3B82F6"
                  strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>TheLook · USD</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={thelook}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="order_month" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Line dataKey="total_product_sales" stroke="#10B981"
                  strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>UCI Online Retail · GBP</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={uci}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="order_month" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Line dataKey="total_product_sales" stroke="#8B5CF6"
                  strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="section-heading">
        <h2>Desempeño por fuente</h2>
      </div>

      <div className="source-grid">
        {commercial.map(row => (
          <div className="panel source-card" key={row.source_system}>
            <span className="eyebrow">{row.source_label}</span>
            <h3>{new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: row.currency_code,
              maximumFractionDigits: 0
            }).format(row.total_product_sales)}</h3>
            <p>{row.currency_code} · {row.currency_status}</p>
            <div className="source-stats">
              <span>Pedidos: <b>{row.total_orders.toLocaleString()}</b></span>
              <span>Completados: <b>{row.completed_orders.toLocaleString()}</b></span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
