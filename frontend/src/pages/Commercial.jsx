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
            <p>Participación y ventas por categoría de producto</p>
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

          return (
            <div className="chart-section" key={s}>
              <h3>{sourceNames[s]}</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={rows.slice(0, 10)} layout="vertical" margin={{left: 20}}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false}/>
                  <XAxis type="number"/>
                  <YAxis type="category" dataKey="category" width={145} tick={{fontSize: 11}}/>
                  <Tooltip formatter={v => currency(v, sourceCurrencies[s])}/>
                  <Bar dataKey="total_sales" fill={sourceColors[s]} radius={[0,4,4,0]}/>
                </BarChart>
              </ResponsiveContainer>
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
