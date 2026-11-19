import { useEffect, useState, lazy, Suspense } from 'react';
import { RefreshCw } from 'lucide-react';
import Sidebar from './components/Sidebar';
import { api } from './services/api';
import './index.css';

const Overview = lazy(() => import('./pages/Overview'));
const Commercial = lazy(() => import('./pages/Commercial'));
const Logistics = lazy(() => import('./pages/Logistics'));
const Sources = lazy(() => import('./pages/Sources'));
const Inventory = lazy(() => import('./pages/Inventory'));
const Predictive = lazy(() => import('./pages/Predictive'));
const StorePerf = lazy(() => import('./pages/StorePerf'));

const titles = {
  overview: 'Resumen Ejecutivo',
  store: 'Store Performance',
  commercial: 'Análisis Comercial',
  logistics: 'Análisis Logístico',
  sources: 'System Health & Data Sources',
  inventory: 'Control de Inventario',
  predictive: 'Predicción de Demanda'
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
            <span className="eyebrow">LUMINA RETAIL / OPERATIONS PLATFORM</span>
            <h1>{titles[active]}</h1>
          </div>
          {active !== 'inventory' && (
            <button className="refresh" onClick={loadData}>
              <RefreshCw size={16}/> Actualizar
            </button>
          )}
        </header>

        {loading ? (
          <div className="panel" style={{ margin: '0 40px' }}>Consultando Data Warehouse...</div>
        ) : error ? (
          <div className="panel error" style={{ margin: '0 40px', background: '#ef444420', border: '1px solid #ef444440' }}>
            <h3 style={{ color: '#f87171' }}>Excepción en Orquestador WAP</h3>
            <p>{error}</p>
            <button className="refresh" onClick={loadData} style={{ marginTop: 15 }}>Reintentar Conexión</button>
          </div>
        ) : (
          <Suspense fallback={<div className="panel" style={{ margin: '0 40px' }}>Cargando módulo...</div>}>
            {active === 'overview' && <Overview commercial={commercial} logistics={logistics} monthly={monthly}/>}
            {active === 'store' && <StorePerf />}
            {active === 'commercial' && <Commercial/>}
            {active === 'logistics' && <Logistics/>}
            {active === 'sources' && <Sources/>}
            {active === 'inventory' && <Inventory/>}
            {active === 'predictive' && <Predictive/>}
          </Suspense>
        )}

        <footer>LUMINA RETAIL · INTELLIGENCE & OPERATIONS PLATFORM · 2026</footer>
      </main>
    </div>
  );
}
