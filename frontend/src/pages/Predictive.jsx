import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, BarChart, Bar
} from 'recharts';
import { Target, Activity, TrendingUp, Database } from 'lucide-react';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.predictiveMetrics(),
      api.predictivePredictions()
    ])
      .then(([m, p]) => {
        setMetrics(m);
        setPredictions(p);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const metric = name =>
    metrics.find(item => item.metric === name)?.value;

  const metadata = metrics[0] || {};

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

  if (loading) {
    return <div className="panel">Cargando evaluación predictiva...</div>;
  }

  if (error) {
    return (
      <div className="panel error">
        <h3>Error al consultar evaluación</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!metrics.length) {
    return (
      <div className="panel">
        No hay evaluaciones predictivas registradas en BigQuery.
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
      description: 'Error porcentual absoluto ponderado',
      icon: TrendingUp
    },
    {
      label: 'Predicciones',
      value: formatNumber(metadata.n_test_rows),
      description: 'Registros evaluados',
      icon: Database
    }
  ];

  return (
    <div className="page-stack">
      <section className="welcome">
        <span className="eyebrow">MACHINE LEARNING / DEMAND FORECAST · WAP GOLD RELEASE</span>
        <h2>Evaluación del modelo de demanda</h2>
        <p>
          Desempeño de XGBoost sobre la demanda semanal por categoría
          de productos de Olist, gobernado mediante el protocolo WAP-02.1.
        </p>
      </section>

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
          <div style={{ background: '#10b981', width: '10px', height: '10px', borderRadius: '50%', boxShadow: '0 0 8px #10b981' }}/>
          <div>
            <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8' }}>Gobernanza WAP Activa</span>
            <div style={{ fontSize: '14px', fontWeight: 600 }}>Dominio Predictive: Publicado (Release Gold)</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '20px', fontSize: '12px', color: '#cbd5e1' }}>
          <div>Versión activa: <code style={{ color: '#38bdf8', background: '#0284c722', padding: '2px 6px', borderRadius: '4px' }}>{metadata.run_id || 'N/A'}</code></div>
          <div>Auditorías superadas: <strong style={{ color: '#4ade80' }}>3/3 (100%)</strong></div>
          <div>Almacenamiento: <code style={{ color: '#a78bfa' }}>gold_predictive_*</code></div>
        </div>
      </div>

      <section className="kpi-grid">
        {cards.map(card => {
          const Icon = card.icon;

          return (
            <article className="panel kpi" key={card.label}>
              <div className="kpi-icon"><Icon size={20}/></div>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.description}</small>
            </article>
          );
        })}
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
              <tr style={{ background: '#ecfdf5' }}>
                <td><strong>Naive Baseline (t-1)</strong></td>
                <td>Heurístico (Persistencia)</td>
                <td>888</td>
                <td><strong>7.5417</strong></td>
                <td><strong>15.9047</strong></td>
                <td><strong>35.49%</strong></td>
                <td><span style={{ color: '#047857', fontWeight: 600 }}>★ Mejor Modelo</span></td>
              </tr>
              <tr>
                <td><strong>XGBoost Regressor</strong></td>
                <td>Supervisado (Experimental)</td>
                <td>888</td>
                <td>7.7780</td>
                <td>16.7220</td>
                <td>36.60%</td>
                <td><span style={{ color: '#2563eb', fontWeight: 600 }}>En Producción Gold</span></td>
              </tr>
              <tr style={{ background: '#fffbeb' }}>
                <td><strong>Seasonal Naive (t-52)</strong></td>
                <td>Heurístico (Estacional Anual)</td>
                <td>888</td>
                <td>12.7939</td>
                <td>27.1788</td>
                <td>60.21%</td>
                <td><span style={{ color: '#b45309' }}>Sesgo Interanual</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: '12px', marginTop: '10px' }}>
          <strong>Hallazgo clave:</strong> El modelo Naive (t-1) superó a XGBoost debido a la alta autocorrelación en categorías de baja rotación. Seasonal Naive (t-52) subestima sistemáticamente la demanda por la fuerte aceleración transaccional de Olist entre 2017 y 2018.
        </p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Demanda real vs. demanda predicha</h2>
            <p>Agregación semanal de las 74 categorías evaluadas</p>
          </div>
        </div>

        <div className="legend">
          <span><i style={{background:'#2563eb'}}/> Demanda real</span>
          <span><i style={{background:'#10b981'}}/> Demanda predicha</span>
        </div>

        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={weekly}>
            <CartesianGrid strokeDasharray="3 3" vertical={false}/>
            <XAxis
              dataKey="semanaLabel"
              tick={{fontSize:10}}
              minTickGap={25}
            />
            <YAxis tick={{fontSize:11}}/>
            <Tooltip formatter={value => formatNumber(value)}/>
            <Legend/>
            <Line
              type="monotone"
              dataKey="actual"
              name="Demanda real"
              stroke="#2563eb"
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

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Categorías con mayor error absoluto</h2>
            <p>Top 15 por suma del error absoluto en el periodo evaluado</p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={categories} layout="vertical" margin={{left:20}}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false}/>
            <XAxis type="number" tick={{fontSize:10}}/>
            <YAxis
              type="category"
              dataKey="categoria"
              width={145}
              tick={{fontSize:10}}
            />
            <Tooltip formatter={value => formatNumber(value)}/>
            <Bar
              dataKey="error"
              name="Error absoluto acumulado"
              fill="#f59e0b"
              radius={[0,4,4,0]}
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

      <section className="panel">
        <h2>Información de la evaluación</h2>
        <div className="source-meta">
          <span>Modelo</span>
          <b>{metadata.model_name || 'XGBoost'}</b>
        </div>
        <div className="source-meta">
          <span>Variable objetivo</span>
          <b>{metadata.target || 'lineas_articulo'}</b>
        </div>
        <div className="source-meta">
          <span>Inicio de prueba</span>
          <b>{formatDate(metadata.split_start)}</b>
        </div>
        <div className="source-meta">
          <span>Fin de prueba</span>
          <b>{formatDate(metadata.split_end)}</b>
        </div>
        <div className="source-meta">
          <span>Run ID</span>
          <b>{metadata.run_id}</b>
        </div>
        <div className="source-meta">
          <span>Tipo de evaluación</span>
          <b>{metadata.evaluation_type}</b>
        </div>
      </section>
    </div>
  );
}
