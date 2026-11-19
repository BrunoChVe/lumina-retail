import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="panel error" style={{
          margin: '20px',
          padding: '24px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '10px',
          color: '#f8fafc'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <AlertTriangle size={28} style={{ color: '#f87171' }} />
            <div>
              <h3 style={{ margin: 0, color: '#f87171', fontSize: '18px' }}>
                {this.props.fallbackTitle || 'Error en el Módulo'}
              </h3>
              <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '13px' }}>
                Se produjo una excepción durante el renderizado del componente. La aplicación continúa operativa.
              </p>
            </div>
          </div>
          
          <div style={{
            background: '#0f172a',
            padding: '12px',
            borderRadius: '6px',
            fontFamily: 'monospace',
            fontSize: '12px',
            color: '#fca5a5',
            overflowX: 'auto',
            marginBottom: '16px',
            border: '1px solid #334155'
          }}>
            {this.state.error?.toString()}
          </div>

          <button
            onClick={this.handleReset}
            style={{
              background: '#ef4444',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              fontWeight: 600,
              fontSize: '13px'
            }}
          >
            <RefreshCw size={14} /> Reintentar Carga
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
