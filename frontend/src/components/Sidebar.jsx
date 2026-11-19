import {
  LayoutDashboard, ShoppingCart, Truck, Database, Activity, Package, BrainCircuit, Store, Zap
} from 'lucide-react';

const items = [
  { id: 'overview', label: 'Resumen Ejecutivo', icon: LayoutDashboard },
  { id: 'store', label: 'Store Performance', icon: Store },
  { id: 'commercial', label: 'Análisis Comercial', icon: ShoppingCart },
  { id: 'logistics', label: 'Logística', icon: Truck },
  { id: 'inventory', label: 'Control de Inventario', icon: Package },
  { id: 'predictive', label: 'Predicción de Demanda', icon: BrainCircuit },
  { id: 'simulation', label: 'Centro de Simulación', icon: Zap },
  { id: 'sources', label: 'System Health', icon: Database }
];

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon"><Activity size={24} /></div>
        <div>
          <strong>LUMINA</strong>
          <span>RETAIL PLATFORM</span>
        </div>
      </div>

      <div className="nav-label">MÓDULOS DE NEGOCIO</div>

      {items.map(item => {
        const Icon = item.icon;
        const isActive = active === item.id ? 'active' : '';
        return (
          <button
            key={item.id}
            className={"nav-item " + isActive}
            onClick={() => onNavigate(item.id)}
          >
            <Icon size={18} />
            {item.label}
          </button>
        );
      })}

      <div className="sidebar-bottom">
        <div className="connection"><span style={{ background: '#10b981' }} /> BigQuery Conectado</div>
        <small style={{ display: 'block', color: '#64748b', fontSize: '11px', marginTop: '2px' }}>lumina-retail-001</small>
        <div style={{
          marginTop: '10px',
          padding: '6px 8px',
          background: '#0b1120',
          borderRadius: '6px',
          border: '1px solid #1e293b',
          fontSize: '10px',
          color: '#38bdf8',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#38bdf8', boxShadow: '0 0 4px #38bdf8' }} />
          <span>WAP Gold v1.0 · 4/4 Activos</span>
        </div>
      </div>
    </aside>
  );
}
