import { useEffect, useState } from 'react';
import { api } from '../services/api';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid
} from 'recharts';

const currency = (value, code) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: code || 'USD',
    maximumFractionDigits: 0
  }).format(Number(value || 0));

export default function Commercial() {
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [source, setSource] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.categories(), api.products()])
      .then(([c, p]) => {
        setCategories(c);
        setProducts(p);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filter = rows =>
    source === 'all'
      ? rows
      : rows.filter(x => x.source_system === source);

  if (loading) return <div className="panel">Cargando análisis comercial...</div>;
  if (error) return <div className="panel error">{error}</div>;

  return (
    <div className="page-stack">
      <div className="filter-bar">
        <span>Fuente de datos</span>
        <select value={source} onChange={e => setSource(e.target.value)}>
          <option value="all">Todas las fuentes</option>
          <option value="olist">Olist · BRL</option>
          <option value="thelook">TheLook · USD</option>
          <option value="uci">UCI Online Retail · GBP</option>
        </select>
      </div>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Rendimiento por categoría</h2>
            <p>Participación y ventas por categoría de producto con aislamiento estricto de divisas</p>
          </div>
        </div>

        {['olist', 'thelook', 'uci'].filter(s => source === 'all' || source === s).map(s => {
          const rows = filter(categories)
            .filter(x => x.source_system === s)
            .sort((a, b) => a.category_rank - b.category_rank);

          const sourceNames = {
            olist: 'Olist · BRL',
            thelook: 'TheLook · USD',
            uci: 'UCI Online Retail · GBP'
          };
          const sourceColors = {
            olist: '#3B82F6',
            thelook: '#10B981',
            uci: '#8B5CF6'
          };
          const sourceCurrencies = {
            olist: 'BRL',
            thelook: 'USD',
            uci: 'GBP'
          };

          const totalSourceSales = rows.reduce((sum, r) => sum + Number(r.total_sales || 0), 0);

          return (
            <div className="chart-section" key={s} style={{ marginBottom: 36, paddingBottom: 24, borderBottom: '1px solid #1e293b' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
                <div>
                  <h3 style={{ margin: 0, color: sourceColors[s], fontSize: 16 }}>{sourceNames[s]}</h3>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    {rows.length} categorías registradas · Ventas totales: <strong>{currency(totalSourceSales, sourceCurrencies[s])}</strong>
                  </span>
                </div>
                {s === 'uci' && (
                  <div style={{ display: 'flex', gap: 8, fontSize: 11 }}>
                    <span style={{ background: '#0284c722', color: '#38bdf8', padding: '3px 8px', borderRadius: 4, border: '1px solid #0284c744' }}>
                      ● 7 Categorías Derivadas (Reglas de Descripción)
                    </span>
                    <span style={{ background: '#f59e0b22', color: '#fbbf24', padding: '3px 8px', borderRadius: 4, border: '1px solid #f59e0b44' }}>
                      ▲ 1 Sin Clasificar (Unclassified: 18.32%)
                    </span>
                  </div>
                )}
              </div>

              {rows.length === 0 ? (
                <div style={{ padding: 24, color: '#64748b', fontStyle: 'italic', background: '#0b1120', borderRadius: 8 }}>
                  No hay datos comerciales disponibles para {sourceNames[s]}.
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={Math.max(220, Math.min(rows.length * 32 + 40, 360))}>
                    <BarChart data={rows.slice(0, 10)} layout="vertical" margin={{left: 25, right: 30, top: 10, bottom: 10}}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={false}/>
                      <XAxis type="number" tickFormatter={v => currency(v, sourceCurrencies[s])}/>
                      <YAxis type="category" dataKey="category" width={160} tick={{fontSize: 11}}/>
                      <Tooltip 
                        formatter={(val, name, item) => [
                          `${currency(val, sourceCurrencies[s])} (${item.payload.sales_share_pct || 0}%)`,
                          `Ventas [${item.payload.category_origin || item.payload.category_type || 'Nativo'}]`
                        ]}
                      />
                      <Bar dataKey="total_sales" fill={sourceColors[s]} radius={[0,4,4,0]}/>
                    </BarChart>
                  </ResponsiveContainer>

                  {s === 'uci' && (
                    <div className="table-wrap" style={{ marginTop: 16 }}>
                      <table>
                        <thead>
                          <tr>
                            <th>Rank</th>
                            <th>Categoría</th>
                            <th>Origen Taxonomía</th>
                            <th>Unidades Vendidas</th>
                            <th>Productos Únicos</th>
                            <th>Ventas Totales</th>
                            <th>Participación</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map(r => (
                            <tr key={r.category}>
                              <td>#{r.category_rank}</td>
                              <td style={{ fontWeight: 600 }}>{r.category}</td>
                              <td>
                                <span style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  background: r.category_origin === 'DERIVED_RULE' ? '#0284c722' : '#f59e0b22',
                                  color: r.category_origin === 'DERIVED_RULE' ? '#38bdf8' : '#fbbf24',
                                  border: `1px solid ${r.category_origin === 'DERIVED_RULE' ? '#0284c744' : '#f59e0b44'}`
                                }}>
                                  {r.category_origin || r.category_type}
                                </span>
                              </td>
                              <td>{Number(r.items_sold).toLocaleString()}</td>
                              <td>{Number(r.distinct_products).toLocaleString()}</td>
                              <td style={{ fontWeight: 600, color: '#f8fafc' }}>{currency(r.total_sales, 'GBP')}</td>
                              <td><strong style={{ color: '#a78bfa' }}>{r.sales_share_pct}%</strong></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </section>

      <section className="panel">
        <h2>Ranking de productos</h2>
        <p className="muted">Productos ordenados por ventas dentro de cada fuente.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fuente</th>
                <th>Producto</th>
                <th>Categoría</th>
                <th>Unidades</th>
                <th>Ventas</th>
                <th>Moneda</th>
              </tr>
            </thead>
            <tbody>
              {filter(products).map((p, i) => (
                <tr key={`${p.source_system}-${p.source_product_id}-${i}`}>
                  <td>{p.source_system}</td>
                  <td>{p.product_name || p.source_product_id}</td>
                  <td>{p.category || 'Sin categoría'}</td>
                  <td>{Number(p.items_sold).toLocaleString()}</td>
                  <td>{currency(p.total_sales, p.currency_code)}</td>
                  <td>{p.currency_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
