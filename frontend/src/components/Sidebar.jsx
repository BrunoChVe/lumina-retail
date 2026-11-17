import {
  LayoutDashboard, ShoppingCart, Truck, Database, Activity
} from 'lucide-react';

const items = [
  { id: 'overview', label: 'Resumen ejecutivo', icon: LayoutDashboard },
  { id: 'commercial', label: 'Comercial', icon: ShoppingCart },
  { id: 'logistics', label: 'Logística', icon: Truck },
  { id: 'sources', label: 'Fuentes de datos', icon: Database }
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
        <div className="connection"><span /> BigQuery conectado</div>
        <small>lumina-retail-001</small>
      </div>
    </aside>
  );
}
