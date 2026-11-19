export default function KPICard({ icon: Icon, label, value }) {
  return (
    <article className="panel kpi">
      <div className="kpi-icon">
        <Icon size={20} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
