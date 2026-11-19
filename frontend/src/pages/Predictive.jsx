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
        <span className="eyebrow">MACHINE LEARNING / DEMAND FORECAST</span>
        <h2>Evaluación del modelo de demanda</h2>
        <p>
          Desempeño de XGBoost sobre la demanda semanal por categoría
          de productos de Olist.
        </p>
      </section>

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
