import { Database, Cloud, Table2, ShieldCheck } from 'lucide-react';

const sources = [
  {
    id: 'olist',
    name: 'Olist',
    currency: 'BRL',
    status: 'Moneda documentada',
    description: 'Datos de comercio electrónico de Brasil.'
  },
  {
    id: 'thelook',
    name: 'TheLook',
    currency: 'USD',
    status: 'Moneda confirmada para el proyecto',
    description: 'Datos de comercio electrónico y productos.'
  },
  {
    id: 'uci',
    name: 'UCI Online Retail',
    currency: 'GBP',
    status: 'Moneda documentada',
    description: 'Transacciones minoristas y mayoristas del Reino Unido y Europa.'
  }
];

export default function Sources() {
  return (
    <div className="page-stack">
      <section className="panel">
        <span className="eyebrow">DATA PLATFORM</span>
        <h2>Arquitectura de datos</h2>
        <div className="architecture-grid">
          <div className="architecture-item">
            <Cloud/>
            <b>Google Cloud</b>
            <span>Proyecto lumina-retail-001</span>
          </div>
          <div className="architecture-item">
            <Database/>
            <b>BigQuery</b>
            <span>Dataset lumina_stage · US</span>
          </div>
          <div className="architecture-item">
            <Table2/>
            <b>Data Warehouse</b>
            <span>Vistas comerciales y logísticas</span>
          </div>
          <div className="architecture-item">
            <ShieldCheck/>
            <b>API</b>
            <span>FastAPI · consultas centralizadas</span>
          </div>
        </div>
      </section>

      <section className="source-grid">
        {sources.map(source => (
          <article className="panel" key={source.id}>
            <span className="eyebrow">SOURCE SYSTEM</span>
            <h2>{source.name}</h2>
            <p>{source.description}</p>
            <div className="source-meta">
              <span>Moneda</span><b>{source.currency}</b>
            </div>
            <div className="source-meta">
              <span>Estado</span><b>{source.status}</b>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
