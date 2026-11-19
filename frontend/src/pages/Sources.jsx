import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Database, Cloud, Table2, ShieldCheck, Globe, Users, XCircle, AlertCircle } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import KPICard from '../components/KPICard';

const currency = (value, code) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: code || 'USD',
    maximumFractionDigits: 0
  }).format(Number(value || 0));

export default function Sources() {
  const [countries, setCountries] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [cancels, setCancels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.countries(),
      api.customersSummary(),
      api.cancellations()
    ])
    .then(([ct, cu, ca]) => {
      setCountries(ct);
      setCustomers(cu);
      setCancels(ca);
    })
    .catch(e => setError(e.message))
    .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="panel" style={{ margin: '0 40px' }}>Verificando salud del sistema e integridad de fuentes...</div>;
  if (error) return <div className="panel error" style={{ margin: '0 40px' }}>{error}</div>;

  const sourcesData = [
    { id: 'olist', name: 'Olist Store', type: 'Marketplace', location: 'Brasil', currency: 'BRL', color: '#3B82F6' },
    { id: 'thelook', name: 'TheLook', type: 'Global eCommerce', location: 'Internacional', currency: 'USD', color: '#10B981' },
    { id: 'uci', name: 'UCI Online Retail', type: 'B2B/B2C eCommerce', location: 'Reino Unido / Europa', currency: 'GBP', color: '#8B5CF6' }
  ];

  return (
    <div className="page-stack">
      <section className="welcome">
        <span className="eyebrow">SYSTEM HEALTH & DATA SOURCES</span>
        <h2>Salud del Sistema y Auditoría de Fuentes</h2>
        <p>Gobernanza de transacciones, penetración geográfica y métricas de clientes identificados por origen.</p>
      </section>

      <section className="panel">
        <div className="architecture-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
          <div className="architecture-item" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, background: '#1e293b', borderRadius: 12 }}>
            <Cloud size={24} color="#38bdf8"/>
            <b style={{ fontSize: 16 }}>Google Cloud</b>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>Proyecto lumina-retail-001</span>
          </div>
          <div className="architecture-item" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, background: '#1e293b', borderRadius: 12 }}>
            <Database size={24} color="#10b981"/>
            <b style={{ fontSize: 16 }}>BigQuery</b>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>Gold WAP Sandbox · US Multi-region</span>
          </div>
          <div className="architecture-item" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, background: '#1e293b', borderRadius: 12 }}>
            <Table2 size={24} color="#a78bfa"/>
            <b style={{ fontSize: 16 }}>Data Warehouse</b>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>Pipeline Medallion (Bronze/Silver/Gold)</span>
          </div>
          <div className="architecture-item" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, background: '#1e293b', borderRadius: 12 }}>
            <ShieldCheck size={24} color="#f59e0b"/>
            <b style={{ fontSize: 16 }}>Gobernanza WAP-02.1</b>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>4 Dominios Auditados (16/16 Pruebas)</span>
          </div>
        </div>
      </section>

      {sourcesData.map(src => {
        const cu = customers.find(c => c.source_system === src.id) || {};
        const ca = cancels.find(c => c.source_system === src.id) || {};
        const ctr = countries.filter(c => c.source_system === src.id).sort((a,b) => b.gross_sales - a.gross_sales).slice(0, 5);

        return (
          <section className="panel" key={src.id} style={{ borderColor: src.color }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 20 }}>
              <div>
                <span className="eyebrow" style={{ color: src.color }}>{src.type}</span>
                <h3 style={{ fontSize: 24, margin: '8px 0', color: '#f8fafc' }}>{src.name}</h3>
                <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>Cobertura nativa: {src.location}</p>
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <div style={{ background: '#1e293b', padding: '12px 16px', borderRadius: 8, textAlign: 'right' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Divisa Documentada</span>
                  <strong style={{ fontSize: 18, color: '#f8fafc' }}>{src.currency}</strong>
                </div>
                <div style={{ background: '#1e293b', padding: '12px 16px', borderRadius: 8, textAlign: 'right' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', display: 'block' }}>Ventas Brutas Trazadas</span>
                  <strong style={{ fontSize: 18, color: '#f8fafc' }}>{currency(cu.total_gross_sales, src.currency)}</strong>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginTop: 24 }}>
              <div style={{ background: '#0b1120', padding: 16, borderRadius: 8, border: '1px solid #1e293b' }}>
                <Users size={18} color="#94a3b8" style={{ marginBottom: 8 }}/>
                <span style={{ display: 'block', fontSize: 12, color: '#94a3b8' }}>Clientes Identificados</span>
                <strong style={{ fontSize: 20 }}>{Number(cu.total_customers || 0).toLocaleString()}</strong>
              </div>
              <div style={{ background: '#0b1120', padding: 16, borderRadius: 8, border: '1px solid #1e293b' }}>
                <Globe size={18} color="#94a3b8" style={{ marginBottom: 8 }}/>
                <span style={{ display: 'block', fontSize: 12, color: '#94a3b8' }}>Venta Promedio por Cliente</span>
                <strong style={{ fontSize: 20 }}>{currency(cu.avg_sales_per_customer, src.currency)}</strong>
              </div>
              <div style={{ background: '#0b1120', padding: 16, borderRadius: 8, border: '1px solid #1e293b' }}>
                <XCircle size={18} color="#ef4444" style={{ marginBottom: 8 }}/>
                <span style={{ display: 'block', fontSize: 12, color: '#94a3b8' }}>Facturas Canceladas</span>
                <strong style={{ fontSize: 20 }}>{Number(ca.canceled_orders || 0).toLocaleString()}</strong>
              </div>
              <div style={{ background: '#0b1120', padding: 16, borderRadius: 8, border: '1px solid #1e293b' }}>
                <AlertCircle size={18} color="#f59e0b" style={{ marginBottom: 8 }}/>
                <span style={{ display: 'block', fontSize: 12, color: '#94a3b8' }}>Devoluciones Detectadas</span>
                <strong style={{ fontSize: 20 }}>{currency(ca.return_sales, src.currency)}</strong>
              </div>
            </div>

            {ctr.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <h4 style={{ fontSize: 14, color: '#cbd5e1', marginBottom: 12 }}>Top 5 Países por Ventas</h4>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>País</th>
                        <th>Órdenes Trazables</th>
                        <th>Ventas Brutas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ctr.map(c => (
                        <tr key={c.country}>
                          <td style={{ fontWeight: 600 }}>{c.country}</td>
                          <td>{Number(c.orders).toLocaleString()}</td>
                          <td>{currency(c.gross_sales, src.currency)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
