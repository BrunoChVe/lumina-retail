import { useEffect, useState, lazy, Suspense } from 'react';
import { RefreshCw } from 'lucide-react';
import Sidebar from './components/Sidebar';
import { api } from './services/api';
import './index.css';

const Overview = lazy(() => import('./pages/Overview'));
const Commercial = lazy(() => import('./pages/Commercial'));
const Logistics = lazy(() => import('./pages/Logistics'));
const Sources = lazy(() => import('./pages/Sources'));

const titles = {
  overview: 'Resumen ejecutivo',
  commercial: 'Análisis comercial',
  logistics: 'Análisis logístico',
  sources: 'Fuentes de datos'
};

export default function App() {
  const [active, setActive] = useState('overview');
  const [commercial, setCommercial] = useState([]);
  const [logistics, setLogistics] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadData() {
    setLoading(true);
    setError('');

    try {
      const [c, l, m] = await Promise.all([
        api.commercial(),
        api.logistics(),
        api.monthly()
      ]);
      setCommercial(c);
      setLogistics(l);
      setMonthly(m);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  return (
    <div className="app-shell">
      <Sidebar active={active} onNavigate={setActive}/>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">LUMINA RETAIL / ANALYTICS</span>
            <h1>{titles[active]}</h1>
          </div>
          <button className="refresh" onClick={loadData}>
            <RefreshCw size={16}/> Actualizar
          </button>
        </header>

        {loading ? (
          <div className="panel">Consultando BigQuery...</div>
        ) : error ? (
          <div className="panel error">
            <h3>Error de conexión</h3>
            <p>{error}</p>
            <button onClick={loadData}>Reintentar</button>
          </div>
        ) : (
          <Suspense fallback={<div className="panel">Cargando módulo...</div>}>
            {active === 'overview' && (
              <Overview commercial={commercial}
                logistics={logistics} monthly={monthly}/>
            )}
            {active === 'commercial' && <Commercial/>}
            {active === 'logistics' && <Logistics/>}
            {active === 'sources' && <Sources/>}
          </Suspense>
        )}

        <footer>LUMINA RETAIL · DATA INTELLIGENCE PLATFORM · 2026</footer>
      </main>
    </div>
  );
}
