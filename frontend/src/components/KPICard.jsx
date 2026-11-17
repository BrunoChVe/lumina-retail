export default function KPICard({ icon: Icon, label, value, detail }) {
  return (
    <div className="panel kpi">
      <div className="kpi-icon"><Icon size={20} /></div>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}
