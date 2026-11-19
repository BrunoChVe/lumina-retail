import {
  LayoutDashboard, ShoppingCart, Truck, Database, Activity, Package, BrainCircuit
} from 'lucide-react';

const items = [
  { id: 'overview', label: 'Resumen ejecutivo', icon: LayoutDashboard },
  { id: 'commercial', label: 'Comercial', icon: ShoppingCart },
  { id: 'logistics', label: 'Logística', icon: Truck },
  { id: 'sources', label: 'Fuentes de datos', icon: Database },
  { id: 'inventory', label: 'Inventario', icon: Package },
  { id: 'predictive', label: 'Predicción de demanda', icon: BrainCircuit }
];

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon"><Activity /></div>
        <div>
          <strong>LUMINA</strong>
          <span>RETAIL INTELLIGENCE</span>
        </div>
      </div>

      <div className="nav-label">PLATAFORMA</div>

      {items.map(item => {
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            className={`nav-item ${active === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <Icon size={18} />
            {item.label}
          </button>
        );
      })}

      <div className="sidebar-bottom">
        <div className="connection"><span style={{ background: '#10b981' }} /> BigQuery conectado</div>
        <small style={{ display: 'block', color: '#91a2bf', fontSize: '11px', marginTop: '2px' }}>lumina-retail-001</small>
        <div style={{
          marginTop: '10px',
          padding: '6px 8px',
          background: '#1d2b45',
          borderRadius: '6px',
          fontSize: '10px',
          color: '#38bdf8',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8' }} />
          <span>WAP Gold v1.0 · 4/4 Dominios</span>
        </div>
      </div>
    </aside>
  );
}
