import { useCallback, useEffect, useState, useMemo } from 'react';
import {
  Zap, Play, Square, RefreshCw, AlertTriangle, CheckCircle2, Clock,
  Package, ShoppingCart, ShieldAlert, Layers, Activity, Cpu, Database,
  TrendingUp, ArrowRight, Check, X, FileText, Info, Flame
} from 'lucide-react';
import { api } from '../services/api';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend, Cell, LineChart, Line
} from 'recharts';

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('es-PE');
  } catch {
    return String(value);
  }
}

export default function SimulationCenter() {
  const [activeTab, setActiveTab] = useState('config'); // 'config', 'monitoring', 'history'
  const [modalities, setModalities] = useState([]);
  const [infraStatus, setInfraStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Formulario de Configuración
  const [testName, setTestName] = useState('Cyber Day — Prueba de Ciclo de Pedidos');
  const [selectedMode, setSelectedMode] = useState('ECONOMIC');
  const [selectedScenario, setSelectedScenario] = useState('ORDER_CYCLE');
  const [numOrders, setNumOrders] = useState(50);
  const [numProducts, setNumProducts] = useState(5);
  const [initialStock, setInitialStock] = useState(60);
  const [simulateIdempotency, setSimulateIdempotency] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  // Estado de Ejecución Activa
  const [activeRunId, setActiveRunId] = useState(null);
  const [runStatus, setRunStatus] = useState(null);
  const [runEvents, setRunEvents] = useState([]);
  const [selectedEventType, setSelectedEventType] = useState('ALL');
  const [startingRun, setStartingRun] = useState(false);
  const [cancellingRun, setCancellingRun] = useState(false);

  // 1. Cargar metadatos y estado inicial
  const loadInitialData = useCallback(async () => {
    try {
      const [mods, infra, hist] = await Promise.all([
        api.simulationModalities().catch(() => []),
        api.simulationInfrastructureStatus().catch(() => null),
        api.simulationHistory().catch(() => [])
      ]);
      setModalities(mods);
      setInfraStatus(infra);
      setHistory(hist);
      // Seleccionar la ejecución más reciente para mostrar por defecto
      if (hist.length > 0 && !activeRunId) {
        setActiveRunId(hist[0].run_id);
      }
    } catch (e) {
      setError(e.message || 'Error al consultar estado de simulación.');
    } finally {
      setLoading(false);
    }
  }, [activeRunId]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // 2. Polling de la ejecución activa (si está en progreso o seleccionada)
  useEffect(() => {
    if (!activeRunId) return;

    const fetchStatus = () => {
      api.simulationStatus(activeRunId)
        .then(st => {
          setRunStatus(st);
          // Si sigue corriendo, volver a refrescar historia
          if (st.status === 'RUNNING' || st.status === 'PENDING') {
            api.simulationHistory().then(setHistory).catch(() => {});
          }
        })
        .catch(() => {});

      api.simulationEvents(activeRunId, 100, selectedEventType)
        .then(evts => setRunEvents(evts || []))
        .catch(() => {});
    };

    fetchStatus();
    // Si la simulación está activa, hacer polling cada 1 segundo
    let interval = null;
    if (runStatus?.status === 'RUNNING' || runStatus?.status === 'PENDING') {
      interval = setInterval(fetchStatus, 1200);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeRunId, runStatus?.status, selectedEventType]);

  // Iniciar Simulación
  const handleStartSimulation = async () => {
    setError('');
    setStartingRun(true);

    const payload = {
      name: testName,
      mode: selectedMode,
      scenario: selectedScenario,
      num_orders: Number(numOrders),
      num_products: Number(numProducts),
      initial_stock: Number(initialStock),
      simulate_idempotency: simulateIdempotency,
      authorized: authorized
    };

    try {
      const res = await api.simulationRun(payload);
      if (res.success && res.run_id) {
        setActiveRunId(res.run_id);
        setActiveTab('monitoring');
        loadInitialData();
      } else {
        setError(res.errors ? res.errors.join('; ') : 'No se pudo iniciar la simulación.');
      }
    } catch (e) {
      setError(e.message || 'Excepción al invocar inicio de simulación.');
    } finally {
      setStartingRun(false);
    }
  };

  // Cancelar Simulación
  const handleCancelSimulation = async () => {
    if (!activeRunId) return;
    setCancellingRun(true);
    try {
      await api.simulationCancel(activeRunId);
      const st = await api.simulationStatus(activeRunId);
      setRunStatus(st);
      loadInitialData();
    } catch (e) {
      setError(e.message || 'Error al cancelar la simulación.');
    } finally {
      setCancellingRun(false);
    }
  };

  // Datos para gráfico de eventos por tipo
  const eventTypesData = useMemo(() => {
    if (!runEvents || runEvents.length === 0) return [];
    const counts = {};
    runEvents.forEach(e => {
      counts[e.event_type] = (counts[e.event_type] || 0) + 1;
    });
    return Object.entries(counts).map(([name, count]) => ({
      name,
      count,
      label: name.replace('_', ' ')
    }));
  }, [runEvents]);

  // Lista de SKUs de inventario del run actual
  const inventoryStateList = useMemo(() => {
    if (!runStatus?.inventory_state) return [];
    return Object.entries(runStatus.inventory_state).map(([sku, data]) => ({
      sku,
      ...data
    }));
  }, [runStatus?.inventory_state]);

  const isRunning = runStatus?.status === 'RUNNING' || runStatus?.status === 'PENDING';

  return (
    <div className="page-stack simulation-page">
      {/* ENCABEZADO */}
      <section className="welcome">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ background: '#f59e0b', color: '#78350f', fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
            MÓDULO DE AUTOMATIZACIÓN DE PRUEBAS
          </span>
          <span style={{ color: '#94a3b8', fontSize: 12 }}>Ambiente Aislado de Estrés y Telemetría</span>
        </div>
        <h2>Centro de Simulación Cyber Days</h2>
        <p>
          Configure, ejecute, monitoree y audite simulaciones de alto volumen de pedidos y eventos de telemetría,
          validando reglas de inventario, prevención de stock negativo e idempotencia.
        </p>
      </section>

      {/* TABS DE NAVEGACIÓN */}
      <div style={{ display: 'flex', gap: 10, borderBottom: '1px solid #334155', paddingBottom: 12 }}>
        <button
          onClick={() => setActiveTab('config')}
          style={{
            background: activeTab === 'config' ? '#0284c7' : '#1e293b',
            color: activeTab === 'config' ? '#ffffff' : '#94a3b8',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '8px 18px',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <Play size={15} /> 1. Configuración y Ejecución
        </button>

        <button
          onClick={() => setActiveTab('monitoring')}
          style={{
            background: activeTab === 'monitoring' ? '#0284c7' : '#1e293b',
            color: activeTab === 'monitoring' ? '#ffffff' : '#94a3b8',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '8px 18px',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <Activity size={15} /> 2. Monitoreo en Vivo {isRunning && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ade80' }} />}
        </button>

        <button
          onClick={() => setActiveTab('history')}
          style={{
            background: activeTab === 'history' ? '#0284c7' : '#1e293b',
            color: activeTab === 'history' ? '#ffffff' : '#94a3b8',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '8px 18px',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <Clock size={15} /> 3. Historial y Auditoría ({history.length})
        </button>
      </div>

      {error && (
        <div className="panel error" style={{ background: '#451a03', border: '1px solid #b45309', color: '#fef3c7', padding: '14px 18px', borderRadius: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertTriangle size={20} style={{ color: '#fbbf24' }} />
            <div><strong>Error de Validación:</strong> {error}</div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PESTAÑA 1: CONFIGURACIÓN Y EJECUCIÓN                                     */}
      {/* ========================================================================= */}
      {activeTab === 'config' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px' }}>
          {/* Panel Izquierdo: Formulario de Parámetros */}
          <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 18, color: '#f8fafc', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers size={18} style={{ color: '#38bdf8' }} /> Parámetros de la Prueba
            </h3>

            {/* 1. Modalidad de Ejecución */}
            <div style={{ marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 8, fontWeight: 600 }}>
                MODALIDAD DE EJECUCIÓN
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{
                  display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                  background: selectedMode === 'ECONOMIC' ? '#042f2e' : '#1e293b',
                  border: `1px solid ${selectedMode === 'ECONOMIC' ? '#14b8a6' : '#334155'}`
                }}>
                  <input
                    type="radio"
                    name="mode"
                    value="ECONOMIC"
                    checked={selectedMode === 'ECONOMIC'}
                    onChange={() => setSelectedMode('ECONOMIC')}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <strong style={{ color: '#f8fafc', fontSize: 13 }}>Modo Económico (Serverless / Recomendado)</strong>
                      <span style={{ fontSize: 10, background: '#10b981', color: '#064e3b', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                        COSTO $0
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                      Simula el ciclo completo de pedidos y reglas de inventario en memoria sin encender infraestructura de cómputo en la nube.
                    </p>
                  </div>
                </label>

                <label style={{
                  display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                  background: selectedMode === 'REAL_STREAMING' ? '#451a03' : '#1e293b',
                  border: `1px solid ${selectedMode === 'REAL_STREAMING' ? '#f59e0b' : '#334155'}`
                }}>
                  <input
                    type="radio"
                    name="mode"
                    value="REAL_STREAMING"
                    checked={selectedMode === 'REAL_STREAMING'}
                    onChange={() => setSelectedMode('REAL_STREAMING')}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <strong style={{ color: '#f8fafc', fontSize: 13 }}>Modo Streaming Real (Kafka + Spark Dataproc)</strong>
                      <span style={{ fontSize: 10, background: '#78350f', color: '#fef3c7', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                        RESTAURACIÓN BAJO DEMANDA
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                      Inyecta mensajes físicos a Kafka y los procesa vía Dataproc Spark hacia GCS y BigQuery. Requiere encender cómputo.
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Advertencia y Autorización para Streaming Real */}
            {selectedMode === 'REAL_STREAMING' && (
              <div style={{ background: '#451a03', border: '1px solid #b45309', borderRadius: 8, padding: 14, marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <AlertTriangle size={18} style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <strong style={{ fontSize: 12, color: '#fbbf24' }}>Infraestructura de Cómputo Pausada</strong>
                    <p style={{ margin: '4px 0 8px 0', fontSize: 11, color: '#fde68a', lineHeight: 1.4 }}>
                      La VM de Kafka y el clúster Dataproc (12 vCPUs) se encuentran detenidos para reducir costos.
                      La activación genera una tarifa estimada de <strong>~$0.85 USD / hora</strong>.
                    </p>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer', color: '#ffffff' }}>
                      <input
                        type="checkbox"
                        checked={authorized}
                        onChange={e => setAuthorized(e.target.checked)}
                      />
                      <span>Entiendo el costo de cómputo y autorizo la activación de infraestructura</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* 2. Escenario de Prueba */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>
                ESCENARIO DE SIMULACIÓN
              </label>
              <select
                value={selectedScenario}
                onChange={e => setSelectedScenario(e.target.value)}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', padding: '9px 12px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              >
                <option value="ORDER_CYCLE">Ciclo Completo de Pedidos (Creación, Reserva, Descuento, Alerta, Rechazo)</option>
                <option value="BURST_TRAFFIC">Picos de Tráfico Cyber Day (Alta Concurrencia TPS)</option>
                <option value="INVENTORY_DEPLETION">Desabastecimiento Rápido (Agotamiento de Stock Crítico)</option>
                <option value="IDEMPOTENCY_STRESS">Estrés de Idempotencia (Re-intento de Órdenes Duplicadas)</option>
              </select>
            </div>

            {/* 3. Nombre de la Prueba */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>
                NOMBRE DESCRIPTIVO DE LA PRUEBA
              </label>
              <input
                type="text"
                value={testName}
                onChange={e => setTestName(e.target.value)}
                style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', padding: '9px 12px', borderRadius: 6, fontSize: 12, outline: 'none' }}
              />
            </div>

            {/* 4. Sliders y Cantidades */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 20 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  CANTIDAD DE PEDIDOS: <strong>{numOrders}</strong>
                </label>
                <input
                  type="range"
                  min="10"
                  max={selectedMode === 'ECONOMIC' ? '300' : '800'}
                  step="10"
                  value={numOrders}
                  onChange={e => setNumOrders(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  PRODUCTOS SIMULADOS: <strong>{numProducts}</strong>
                </label>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={numProducts}
                  onChange={e => setNumProducts(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  STOCK INICIAL / SKU: <strong>{initialStock}</strong>
                </label>
                <input
                  type="range"
                  min="20"
                  max="150"
                  step="10"
                  value={initialStock}
                  onChange={e => setInitialStock(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {/* Botón de Inicio */}
            <button
              onClick={handleStartSimulation}
              disabled={startingRun || isRunning || (selectedMode === 'REAL_STREAMING' && !authorized)}
              style={{
                width: '100%',
                background: isRunning ? '#334155' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                color: 'white',
                border: 'none',
                padding: '12px 20px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                cursor: isRunning ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
                boxShadow: '0 4px 12px rgba(2, 132, 199, 0.3)'
              }}
            >
              {startingRun ? (
                <>
                  <RefreshCw className="spin" size={18} /> Validando e iniciando...
                </>
              ) : isRunning ? (
                <>
                  <Clock size={18} /> Simulación en progreso ({runStatus?.progress_pct || 0}%)
                </>
              ) : (
                <>
                  <Zap size={18} /> Iniciar Simulación Cyber Days
                </>
              )}
            </button>
          </section>

          {/* Panel Derecho: Arquitectura y Reglas del Ciclo de Pedidos */}
          <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 18, color: '#f8fafc', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
              <ShieldAlert size={18} style={{ color: '#10b981' }} /> Reglas de Negocio del Ciclo de Pedidos
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, borderLeft: '4px solid #38bdf8' }}>
                <strong style={{ fontSize: 13, color: '#f8fafc', display: 'block', marginBottom: 2 }}>
                  1. Secuencia de Eventos Causal
                </strong>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  Cada transacción emite la cadena <code>order_created</code> → <code>order_item_created</code> →
                  <code>inventory_decrement</code> → <code>order_completed</code> (o <code>order_rejected</code> si el stock es insuficiente).
                </span>
              </div>

              <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, borderLeft: '4px solid #10b981' }}>
                <strong style={{ fontSize: 13, color: '#f8fafc', display: 'block', marginBottom: 2 }}>
                  2. Prevención de Stock Negativo (Salvaguarda Estricta)
                </strong>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  El inventario se valida antes de confirmar la orden. Si la cantidad solicitada excede el saldo remanente,
                  el pedido es rechazado inmediatamente sin alterar el inventario existente.
                </span>
              </div>

              <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, borderLeft: '4px solid #f59e0b' }}>
                <strong style={{ fontSize: 13, color: '#f8fafc', display: 'block', marginBottom: 2 }}>
                  3. Alertas de Umbral Crítico (inventory_low)
                </strong>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  Cuando el inventario de un SKU desciende a 20 unidades o menos, se dispara un evento de alerta preventiva
                  para abastecimiento logístico.
                </span>
              </div>

              <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, borderLeft: '4px solid #a855f7' }}>
                <strong style={{ fontSize: 13, color: '#f8fafc', display: 'block', marginBottom: 2 }}>
                  4. Control de Idempotencia y Deduplicación
                </strong>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  Si una orden duplicada reintenta procesarse, el sistema la reconoce por su <code>order_id</code> unívoco
                  y neutraliza el cobro sin descontar inventario duplicado.
                </span>
              </div>

              <div style={{ background: '#1e293b', padding: '12px 14px', borderRadius: 8, borderLeft: '4px solid #ef4444' }}>
                <strong style={{ fontSize: 13, color: '#f8fafc', display: 'block', marginBottom: 2 }}>
                  5. Aislamiento Absoluto de Datos Reales
                </strong>
                <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.4 }}>
                  Todos los registros poseen la etiqueta <code>synthetic_flag = true</code> y operan en el catálogo
                  <code>CYBER_SKU_*</code>, garantizando 0% de contaminación sobre las ventas de Olist, TheLook y UCI.
                </span>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PESTAÑA 2: MONITOREO EN VIVO                                              */}
      {/* ========================================================================= */}
      {activeTab === 'monitoring' && (
        <div>
          {/* Header de la Ejecución Seleccionada */}
          <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 20, marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                    background: runStatus?.status === 'COMPLETED' ? '#10b981' : runStatus?.status === 'RUNNING' ? '#0284c7' : '#f59e0b',
                    color: 'white'
                  }}>
                    ESTADO: {runStatus?.status || 'PENDIENTE'}
                  </span>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>Modalidad: {runStatus?.mode || 'ECONOMIC'}</span>
                  {runStatus?.is_historical && (
                    <span style={{ fontSize: 10, background: '#7c3aed', color: 'white', padding: '1px 6px', borderRadius: 4 }}>
                      HISTÓRICO REAL
                    </span>
                  )}
                </div>
                <h3 style={{ fontSize: 18, color: '#f8fafc', margin: 0 }}>
                  {runStatus?.name || 'Ejecución de Simulación'}
                </h3>
                <small style={{ color: '#64748b', fontSize: 11 }}>Run ID: {activeRunId}</small>
              </div>

              {isRunning && (
                <button
                  onClick={handleCancelSimulation}
                  disabled={cancellingRun}
                  style={{
                    background: '#7f1d1d', color: '#fecaca', border: '1px solid #b91c1c',
                    padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6
                  }}
                >
                  <Square size={14} /> Cancelar Simulación
                </button>
              )}
            </div>

            {/* Barra de Progreso */}
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
                <span>Progreso de Procesamiento</span>
                <strong>{runStatus?.progress_pct || 0}%</strong>
              </div>
              <div style={{ height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${runStatus?.progress_pct || 0}%`,
                    height: '100%',
                    background: runStatus?.status === 'COMPLETED' ? '#10b981' : '#0284c7',
                    transition: 'width 0.3s ease'
                  }}
                />
              </div>
            </div>
          </section>

          {/* Tarjetas KPI en Vivo */}
          <section className="kpi-grid">
            <div className="panel kpi">
              <div className="kpi-icon"><ShoppingCart size={20} /></div>
              <span>Pedidos Totales</span>
              <strong>{runStatus?.total_orders || 0}</strong>
              <small>Emitidos en la prueba</small>
            </div>

            <div className="panel kpi">
              <div className="kpi-icon" style={{ background: '#064e3b', color: '#34d399' }}><CheckCircle2 size={20} /></div>
              <span>Pedidos Aprobados</span>
              <strong style={{ color: '#34d399' }}>{runStatus?.completed_orders || 0}</strong>
              <small>Stock suficiente</small>
            </div>

            <div className="panel kpi">
              <div className="kpi-icon" style={{ background: '#7f1d1d', color: '#f87171' }}><AlertTriangle size={20} /></div>
              <span>Pedidos Rechazados</span>
              <strong style={{ color: '#f87171' }}>{runStatus?.rejected_orders || 0}</strong>
              <small>Out of Stock prevenido</small>
            </div>

            <div className="panel kpi">
              <div className="kpi-icon" style={{ background: '#581c87', color: '#c084fc' }}><Layers size={20} /></div>
              <span>Eventos del Ciclo</span>
              <strong style={{ color: '#c084fc' }}>{runStatus?.total_events || 0}</strong>
              <small>Auditados unívocamente</small>
            </div>

            <div className="panel kpi">
              <div className="kpi-icon"><Activity size={20} /></div>
              <span>Throughput</span>
              <strong>{runStatus?.throughput_events_per_sec || 0} ev/s</strong>
              <small>Tasa de procesamiento</small>
            </div>

            <div className="panel kpi">
              <div className="kpi-icon"><Clock size={20} /></div>
              <span>Duración</span>
              <strong>{runStatus?.duration_sec || 0}s</strong>
              <small>Tiempo total de ejecución</small>
            </div>
          </section>

          {/* Fila con Gráfico de Composición y Estado de Inventario */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20, marginTop: 20 }}>
            {/* Gráfico: Distribución de Eventos por Tipo */}
            <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 20 }}>
              <h3 style={{ fontSize: 16, color: '#f8fafc', marginBottom: 4 }}>
                Distribución de Eventos del Ciclo de Pedidos
              </h3>
              <p className="muted" style={{ marginBottom: 14 }}>
                Conteo por tipo de evento emitido durante la simulación.
              </p>
              <div className="chart-box" style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={eventTypesData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} interval={0} angle={-20} textAnchor="end" height={50} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                    />
                    <Bar dataKey="count" name="Cantidad de Eventos" fill="#38bdf8" radius={[4, 4, 0, 0]}>
                      {eventTypesData.map((e, idx) => (
                        <Cell
                          key={`cell-${idx}`}
                          fill={
                            e.name === 'order_rejected' ? '#ef4444' :
                            e.name === 'order_completed' ? '#10b981' :
                            e.name === 'inventory_low' ? '#f59e0b' : '#38bdf8'
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Estado de Inventario Sintético por SKU */}
            <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 20 }}>
              <h3 style={{ fontSize: 16, color: '#f8fafc', marginBottom: 4 }}>
                Estado de Inventario por SKU (Catálogo Sintético)
              </h3>
              <p className="muted" style={{ marginBottom: 14 }}>
                Saldos en bodega, unidades vendidas y rechazos tras la simulación.
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Stock Inicial</th>
                      <th>Stock Remanente</th>
                      <th>Ventas</th>
                      <th>Rechazos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventoryStateList.map(item => (
                      <tr key={item.sku}>
                        <td><strong>{item.sku}</strong></td>
                        <td>{item.initial}</td>
                        <td>
                          <strong style={{ color: item.current <= 20 ? '#f87171' : '#34d399' }}>
                            {item.current}
                          </strong>
                          {item.current <= 20 && (
                            <span style={{ fontSize: 10, background: '#7f1d1d', color: '#fecaca', padding: '1px 5px', borderRadius: 4, marginLeft: 6 }}>
                              BAJO
                            </span>
                          )}
                        </td>
                        <td>{item.total_sold || 0}</td>
                        <td>{item.total_rejected || 0}</td>
                      </tr>
                    ))}
                    {inventoryStateList.length === 0 && (
                      <tr><td colSpan="5" style={{ textAlign: 'center', padding: 20, color: '#94a3b8' }}>Sin datos de inventario para esta ejecución.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          {/* Log de Eventos Cronológico */}
          <section className="panel" style={{ marginTop: 20, background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
              <div>
                <h3 style={{ fontSize: 16, color: '#f8fafc', margin: 0 }}>
                  Log de Eventos Cronológico (Trazabilidad End-to-End)
                </h3>
                <p className="muted" style={{ margin: '4px 0 0 0' }}>
                  Eventos unívocos auditados con marca temporal en milisegundos.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>Filtrar evento:</span>
                <select
                  value={selectedEventType}
                  onChange={e => setSelectedEventType(e.target.value)}
                  style={{ background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: 12, borderRadius: 6, padding: '5px 10px', outline: 'none' }}
                >
                  <option value="ALL">Todos los Eventos</option>
                  <option value="order_created">order_created</option>
                  <option value="order_item_created">order_item_created</option>
                  <option value="inventory_decrement">inventory_decrement</option>
                  <option value="inventory_low">inventory_low</option>
                  <option value="order_completed">order_completed</option>
                  <option value="order_rejected">order_rejected</option>
                  <option value="duplicate_order_neutralized">duplicate_order_neutralized</option>
                </select>
              </div>
            </div>

            <div className="table-wrap" style={{ maxHeight: 360, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Event ID</th>
                    <th>Tipo de Evento</th>
                    <th>Order ID</th>
                    <th>Producto</th>
                    <th>Cantidad</th>
                    <th>Detalles / Razón</th>
                    <th>Marca de Tiempo (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {runEvents.slice(0, 50).map((evt, idx) => (
                    <tr key={evt.event_id || idx} style={{ background: evt.event_type === 'order_rejected' ? '#451a0333' : 'transparent' }}>
                      <td><code>{evt.event_id}</code></td>
                      <td>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                          background:
                            evt.event_type === 'order_completed' ? '#064e3b' :
                            evt.event_type === 'order_rejected' ? '#7f1d1d' :
                            evt.event_type === 'inventory_low' ? '#78350f' :
                            evt.event_type === 'inventory_decrement' ? '#1e3a8a' : '#1e293b',
                          color:
                            evt.event_type === 'order_completed' ? '#34d399' :
                            evt.event_type === 'order_rejected' ? '#f87171' :
                            evt.event_type === 'inventory_low' ? '#fbbf24' :
                            evt.event_type === 'inventory_decrement' ? '#93c5fd' : '#cbd5e1'
                        }}>
                          {evt.event_type}
                        </span>
                      </td>
                      <td><code>{evt.order_id || '—'}</code></td>
                      <td><strong>{evt.product_id || '—'}</strong></td>
                      <td>{evt.quantity || '—'}</td>
                      <td style={{ fontSize: 11, maxWidth: 280, color: evt.reason ? '#fca5a5' : '#94a3b8' }}>
                        {evt.reason || (evt.new_stock !== undefined ? `Stock remanente: ${evt.new_stock}` : 'Procesado')}
                      </td>
                      <td style={{ fontSize: 11, color: '#64748b' }}>{formatDate(evt.event_timestamp)}</td>
                    </tr>
                  ))}
                  {runEvents.length === 0 && (
                    <tr><td colSpan="7" style={{ textAlign: 'center', padding: 20, color: '#94a3b8' }}>Sin eventos para este filtro.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PESTAÑA 3: HISTORIAL Y AUDITORÍA                                          */}
      {/* ========================================================================= */}
      {activeTab === 'history' && (
        <section className="panel" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: 18, color: '#f8fafc', margin: 0 }}>Historial de Simulaciones y Auditorías</h3>
              <p className="muted" style={{ margin: '4px 0 0 0' }}>
                Registro inmutable de todas las pruebas ejecutadas en la plataforma con balance de masa y métricas.
              </p>
            </div>
            <button className="refresh" onClick={loadInitialData}>
              <RefreshCw size={14} /> Refrescar Historial
            </button>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre de la Prueba</th>
                  <th>Modalidad</th>
                  <th>Escenario</th>
                  <th>Estado</th>
                  <th>Pedidos</th>
                  <th>Aprobados</th>
                  <th>Rechazados</th>
                  <th>Eventos</th>
                  <th>Throughput</th>
                  <th>Fecha</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {history.map(run => (
                  <tr key={run.run_id} style={{ background: run.run_id === activeRunId ? '#1e293b' : 'transparent' }}>
                    <td>
                      <strong>{run.name}</strong>
                      {run.is_historical && (
                        <span style={{ fontSize: 9, background: '#7c3aed', color: 'white', padding: '1px 5px', borderRadius: 3, marginLeft: 6 }}>
                          HISTÓRICO REAL
                        </span>
                      )}
                      <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>{run.run_id}</div>
                    </td>
                    <td>
                      <span style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 700,
                        background: run.mode === 'REAL_STREAMING' ? '#451a03' : '#064e3b',
                        color: run.mode === 'REAL_STREAMING' ? '#fbbf24' : '#34d399'
                      }}>
                        {run.mode}
                      </span>
                    </td>
                    <td><span style={{ fontSize: 11 }}>{run.scenario || 'BURST'}</span></td>
                    <td>
                      <span style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 700,
                        background: run.status === 'COMPLETED' ? '#064e3b' : run.status === 'RUNNING' ? '#0369a1' : '#7f1d1d',
                        color: run.status === 'COMPLETED' ? '#34d399' : run.status === 'RUNNING' ? '#38bdf8' : '#f87171'
                      }}>
                        {run.status}
                      </span>
                    </td>
                    <td><strong>{run.total_orders || 0}</strong></td>
                    <td style={{ color: '#34d399' }}>{run.completed_orders || 0}</td>
                    <td style={{ color: Number(run.rejected_orders) > 0 ? '#f87171' : 'inherit' }}>{run.rejected_orders || 0}</td>
                    <td>{run.total_events || 0}</td>
                    <td>{run.throughput_events_per_sec || 0} ev/s</td>
                    <td style={{ fontSize: 11, color: '#94a3b8' }}>{formatDate(run.created_at)}</td>
                    <td>
                      <button
                        onClick={() => {
                          setActiveRunId(run.run_id);
                          setActiveTab('monitoring');
                        }}
                        style={{
                          background: '#0284c7', color: 'white', border: 'none', padding: '5px 10px',
                          borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
                        }}
                      >
                        Ver Detalle <ArrowRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
