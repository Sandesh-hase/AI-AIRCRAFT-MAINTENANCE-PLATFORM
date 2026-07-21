import { useEffect, useMemo, useState } from 'react';
import { getMaintenanceRecommendation, healthCheck, uploadAnalyticsFile } from './api/client';
import PanelCard from './components/PanelCard';

function App() {
  const [excelFile, setExcelFile] = useState(null);
  const [manualFile, setManualFile] = useState(null);
  const [status, setStatus] = useState('Checking backend connection...');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState('');
  const [analyticsResult, setAnalyticsResult] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const pingBackend = async () => {
      try {
        const result = await healthCheck();
        setStatus(`Backend online · ${result.service || 'API ready'}`);
      } catch (err) {
        setStatus('Backend offline. Start FastAPI on port 8000.');
        setError(err.message);
      }
    };

    pingBackend();
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!excelFile) {
      setError('Please upload an Excel file first.');
      return;
    }

    setIsLoading(true);
    setLoadingPhase('analytics');
    setError('');
    setRecommendation(null);

    try {
      const response = await uploadAnalyticsFile(excelFile);
      setAnalyticsResult(response);
      setStatus(`Analytics ready for ${response.aircraft_id || 'selected aircraft'}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
      setLoadingPhase('');
    }
  };

  const handleRecommendation = async () => {
    if (!analyticsResult) {
      setError('Generate analytics first.');
      return;
    }

    setIsLoading(true);
    setLoadingPhase('ai');
    setError('');

    try {
      const response = await getMaintenanceRecommendation(analyticsResult);
      setRecommendation(response);
      setStatus('AI maintenance recommendation generated');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
      setLoadingPhase('');
    }
  };

  const currentRecord = analyticsResult?.summary?.current_record;
  const historicalAnalysis = analyticsResult?.summary?.historical_analysis || [];

  const metrics = useMemo(() => {
    if (!analyticsResult?.summary) return [];

    const summary = analyticsResult.summary;
    const analysis = summary.historical_analysis || [];
    const riskSignal = analysis.find((item) => item.column === 'Risk_Score');
    const vibrationSignal = analysis.find((item) => item.column === 'Engine_Vibration');
    const rulSignal = analysis.find((item) => item.column === 'Remaining_Useful_Life');
    const record = summary.current_record || {};

    return [
      {
        icon: '✈',
        label: 'Aircraft',
        value: analyticsResult.aircraft_id || 'N/A',
        sub: record.Aircraft_Model || 'Unknown model',
        accent: 'cyan',
      },
      {
        icon: '⚙',
        label: 'Engine',
        value: record.Engine_Model || 'N/A',
        sub: `Airport: ${record.Airport_Code || 'N/A'}`,
        accent: 'blue',
      },
      {
        icon: '🔄',
        label: 'Flight Cycle',
        value: summary.latest_flight_cycle || 'N/A',
        sub: `${record.Flight_Hours || 0} flight hours logged`,
        accent: 'sky',
      },
      {
        icon: '🔧',
        label: 'Since Overhaul',
        value: record.Cycles_Since_Overhaul || 'N/A',
        sub: `Last maintenance: ${record.Last_Maintenance_Date || 'N/A'}`,
        accent: 'teal',
      },
      {
        icon: '⚠',
        label: 'Risk Score',
        value: riskSignal ? riskSignal.latest_value : 'N/A',
        sub: riskSignal ? `${riskSignal.change_percent > 0 ? '+' : ''}${riskSignal.change_percent.toFixed(1)}% vs history` : '',
        accent: riskSignal && riskSignal.latest_value > 70 ? 'red' : riskSignal && riskSignal.latest_value > 50 ? 'amber' : 'green',
      },
      {
        icon: '🛡',
        label: 'Remaining Life',
        value: rulSignal ? `${rulSignal.latest_value} cycles` : 'N/A',
        sub: rulSignal ? `${rulSignal.change_percent > 0 ? '+' : ''}${rulSignal.change_percent.toFixed(1)}% vs avg` : '',
        accent: rulSignal && rulSignal.latest_value < 30 ? 'red' : rulSignal && rulSignal.latest_value < 50 ? 'amber' : 'green',
      },
      {
        icon: '📳',
        label: 'Vibration',
        value: vibrationSignal ? `${vibrationSignal.latest_value} mm/s` : 'N/A',
        sub: vibrationSignal ? vibrationSignal.trend_direction : '',
        accent: vibrationSignal && vibrationSignal.trend_direction === 'INCREASING' ? 'orange' : 'teal',
      },
      {
        icon: '📊',
        label: 'Signals',
        value: historicalAnalysis.length,
        sub: `Window: ${analyticsResult.summary.historical_window_size || 10} cycles`,
        accent: 'violet',
      },
      {
        icon: '🌡',
        label: 'Ambient',
        value: `${currentRecord?.Ambient_Temperature?.toFixed(1) || 'N/A'}°C`,
        sub: `Humidity: ${currentRecord?.Humidity || 'N/A'}%`,
        accent: 'sky',
      },
    ];
  }, [analyticsResult, currentRecord, historicalAnalysis.length]);

  // Engine gauge data
  const engineGauges = useMemo(() => {
    if (!currentRecord) return [];
    return [
      { label: 'Engine Temp', value: currentRecord.Engine_Temperature, unit: '°C', max: 900, warn: 750 },
      { label: 'EGT', value: currentRecord.Exhaust_Gas_Temperature, unit: '°C', max: 850, warn: 700 },
      { label: 'Oil Temp', value: currentRecord.Oil_Temperature, unit: '°C', max: 150, warn: 110 },
      { label: 'Oil Pressure', value: currentRecord.Oil_Pressure, unit: 'psi', max: 65, warn: 45 },
      { label: 'Engine RPM', value: currentRecord.Engine_RPM, unit: 'RPM', max: 12000, warn: 10500 },
      { label: 'Fuel Flow', value: currentRecord.Fuel_Flow, unit: 'kg/h', max: 3200, warn: 2800 },
      { label: 'Compressor', value: currentRecord.Compressor_Pressure, unit: 'psi', max: 55, warn: 48 },
      { label: 'Hydraulic', value: currentRecord.Hydraulic_Pressure, unit: 'psi', max: 3500, warn: 3200 },
    ];
  }, [currentRecord]);

  const recommendationSummary = recommendation?.report || null;

  const workflowSteps = [
    {
      number: '1',
      title: 'Flight intake',
      description: 'Upload the landed-flight telemetry export for review.',
    },
    {
      number: '2',
      title: 'Condition review',
      description: 'Compare the current signals with recent historical behavior.',
    },
    {
      number: '3',
      title: 'Action guidance',
      description: 'Receive AI-backed maintenance direction grounded in the manual.',
    },
  ];

  const getGaugeLevel = (value, warn, max) => {
    const pct = (value / max) * 100;
    if (value >= warn) return 'level-warn';
    if (pct > 85) return 'level-danger';
    return 'level-ok';
  };

  const getTrendArrow = (direction) => {
    switch (direction) {
      case 'INCREASING': return '↑';
      case 'DECREASING': return '↓';
      case 'STABLE': return '→';
      default: return '·';
    }
  };

  const getHealthBadgeClass = (status) => {
    switch (status?.toUpperCase()) {
      case 'MONITOR': return 'monitor';
      case 'OK':
      case 'NORMAL': return 'ok';
      case 'CRITICAL':
      case 'ALERT': return 'critical';
      default: return 'monitor';
    }
  };

  const getRiskBadgeClass = (level) => {
    switch (level?.toUpperCase()) {
      case 'LOW': return 'risk-low';
      case 'MEDIUM': return 'risk-medium';
      case 'HIGH': return 'risk-high';
      default: return 'risk-medium';
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-glow" aria-hidden="true" />
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="eyebrow-line" />
            Post-landing operational intelligence
            <span className="eyebrow-line" />
          </p>
          <h1>
            <span className="logo-mark" aria-hidden="true">
              <svg viewBox="0 0 36 36" width="36" height="36">
                <circle cx="18" cy="18" r="17" fill="none" stroke="url(#logoGrad)" strokeWidth="1.5" opacity="0.5" />
                <circle cx="18" cy="18" r="12" fill="none" stroke="url(#logoGrad)" strokeWidth="0.8" opacity="0.3" />
                <defs>
                  <linearGradient id="logoGrad" x1="0" y1="0" x2="36" y2="36">
                    <stop offset="0%" stopColor="#22d3ee" />
                    <stop offset="100%" stopColor="#a78bfa" />
                  </linearGradient>
                </defs>
                <text x="18" y="22" textAnchor="middle" fontSize="16" fill="url(#logoGrad)">✈</text>
              </svg>
            </span>
            <span className="title-text">
              <span className="title-aero">Aero</span>
              <span className="title-care">Care</span>
            </span>
            <span className="title-divider" />
            <span className="title-suffix">Maintenance</span>
          </h1>
          <p className="hero-subtitle">
            From touchdown to action — every flight is reviewed with clarity and precision.
          </p>
          <div className="hero-tags">
            <span className="hero-tag">AI-Powered</span>
            <span className="hero-tag">Real-time Analytics</span>
            <span className="hero-tag">Manual-Grounded</span>
          </div>
        </div>
        <div className="status-pill">
          <span className="status-dot" />
          {status}
        </div>
      </header>

      <section className="workflow-strip" aria-label="Dashboard workflow">
        {workflowSteps.map((step) => (
          <div key={step.title} className="workflow-step">
            <div className="step-number">{step.number}</div>
            <h4>{step.title}</h4>
            <p>{step.description}</p>
          </div>
        ))}
      </section>

      <section className="flight-track-card">
        <div className="track-copy">
          <p className="eyebrow">Live flight monitoring</p>
          <h3>{analyticsResult ? `Flight ${analyticsResult.aircraft_id} has landed and is being assessed.` : 'A landed flight is ready for assessment.'}</h3>
          <p>The telemetry loop is visualized here so the transition from landing to maintenance review feels immediate and operational.</p>
        </div>
        <div className="track-visual" aria-hidden="true">
          <svg viewBox="0 0 340 120" role="presentation">
            <defs>
              <linearGradient id="trackGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.3" />
                <stop offset="50%" stopColor="#2dd4bf" stopOpacity="0.7" />
                <stop offset="100%" stopColor="#34d399" stopOpacity="0.3" />
              </linearGradient>
            </defs>

            {/* Flight path arc */}
            <path d="M24 82 C70 20, 130 20, 170 55 S250 108, 316 32" className="track-arc" />

            {/* Departure node */}
            <circle cx="24" cy="82" r="5" className="track-node departure" />
            {/* En route node */}
            <circle cx="170" cy="55" r="5" className="track-node active" />
            {/* Landing node */}
            <circle cx="316" cy="32" r="5" className="track-node landing" />

            {/* Proper airplane shape */}
            <g className="plane-group">
              {/* Fuselage */}
              <ellipse cx="60" cy="62" rx="24" ry="5" className="plane-body" />
              {/* Nose */}
              <path d="M84 62 Q92 62 88 60 Q84 58 84 62 Z" className="plane-body" />
              {/* Main wing */}
              <path d="M54 62 L44 46 L48 46 L64 60 Z" className="plane-wing" />
              <path d="M54 62 L44 78 L48 78 L64 64 Z" className="plane-wing" />
              {/* Tail fin */}
              <path d="M36 62 L30 50 L34 50 L38 60 Z" className="plane-tail" />
              <path d="M36 62 L32 56 L36 56 Z" className="plane-accent" />
              {/* Tail horizontal */}
              <path d="M36 62 L30 68 L34 68 L38 64 Z" className="plane-tail" />
              {/* Windows */}
              <circle cx="68" cy="61" r="1.2" className="plane-window" />
              <circle cx="64" cy="61" r="1.2" className="plane-window" />
              <circle cx="60" cy="61" r="1.2" className="plane-window" />
              <circle cx="56" cy="61" r="1.2" className="plane-window" />
              {/* Engine glow */}
              <line x1="33" y1="62" x2="26" y2="62" className="plane-engine-glow" />
            </g>
          </svg>
          <div className="track-labels">
            <span>Departure</span>
            <span>En route</span>
            <span>Landing</span>
          </div>
        </div>
      </section>

      <div className="dashboard-grid">
        <aside className="sidebar">
          <PanelCard title="Flight Data Upload" subtitle="Upload the landed-flight telemetry export and begin the engineering review.">
            <form onSubmit={handleSubmit} className="upload-form">
              <label className="file-field">
                <span>Engineering Excel (.xlsx)</span>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={(event) => setExcelFile(event.target.files?.[0] || null)}
                />
              </label>

              <p className="helper-text compact">
                This stage compares the latest landed-flight telemetry with the historical baseline to reveal the current aircraft condition.
              </p>

              <button type="submit" className="primary-btn" disabled={isLoading}>
                {isLoading && loadingPhase === 'analytics' ? 'Analyzing telemetry...' : 'Generate Engineering Analytics'}
              </button>
            </form>
          </PanelCard>

          <PanelCard
            title="Maintenance Guidance"
            subtitle="Use the analytics output and the aviation manual for action guidance."
            accent="ai"
          >
            <label className="file-field">
              <span>Maintenance PDF (.pdf)</span>
              <input
                type="file"
                accept=".pdf"
                onChange={(event) => setManualFile(event.target.files?.[0] || null)}
              />
            </label>

            <p className="helper-text compact">
              {manualFile ? `Manual loaded: ${manualFile.name}` : 'The PDF is used to enrich the AI recommendation with manual-specific guidance.'}
            </p>

            <button className="primary-btn wide ai-btn" onClick={handleRecommendation} disabled={isLoading || !analyticsResult}>
              {isLoading && loadingPhase === 'ai' ? '✨ AI is analyzing...' : '✨ Generate AI Recommendation'}
            </button>
          </PanelCard>
        </aside>

        <main className="main-content">
          {/* Metric cards row */}
          <div className="metric-row">
            {metrics.map((metric) => (
              <div className={`metric-card ${metric.accent}`} key={metric.label}>
                <span className="metric-icon">{metric.icon}</span>
                <span className="metric-label">{metric.label}</span>
                <strong className="metric-value">{metric.value}</strong>
                <small className="metric-sub">{metric.sub}</small>
              </div>
            ))}
          </div>

          {error ? <div className="error-box">⚠ {error}</div> : null}

          <div className="split-view">
            {/* ─── Engineering Analytics ─── */}
            <PanelCard title="Engineering Analytics" subtitle="Operational health derived from the uploaded aircraft dataset">
              {isLoading && loadingPhase === 'analytics' ? (
                <div className="loading-overlay">
                  <div className="loading-spinner" />
                  <span className="loading-text">Processing telemetry data...</span>
                </div>
              ) : analyticsResult ? (
                <div className="analytics-panel">
                  {/* Aircraft overview header */}
                  <div className="aircraft-header">
                    <div className="aircraft-avatar">✈</div>
                    <div className="aircraft-info">
                      <h4>{analyticsResult.aircraft_id} — {currentRecord?.Aircraft_Model || 'Unknown'}</h4>
                      <div className="aircraft-meta">
                        <span>🔧 {currentRecord?.Engine_Model || 'N/A'}</span>
                        <span>📍 {currentRecord?.Airport_Code || 'N/A'}</span>
                        <span>🔄 Cycle {analyticsResult.summary.latest_flight_cycle}</span>
                      </div>
                    </div>
                  </div>

                  {/* Engine Gauges */}
                  <div className="gauge-grid">
                    {engineGauges.map((gauge) => {
                      const pct = Math.min(((gauge.value || 0) / gauge.max) * 100, 100);
                      const level = getGaugeLevel(gauge.value || 0, gauge.warn, gauge.max);
                      return (
                        <div className="gauge-card" key={gauge.label}>
                          <span className="gauge-label">{gauge.label}</span>
                          <div className="gauge-value-row">
                            <span className="gauge-value">{gauge.value?.toLocaleString() || 'N/A'}</span>
                            <span className="gauge-unit">{gauge.unit}</span>
                          </div>
                          <div className="gauge-bar-track">
                            <div className={`gauge-bar-fill ${level}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Signal Trends */}
                  <div className="signal-list">
                    <h4>
                      Signal Trends
                      <span className="signal-count">{historicalAnalysis.length} parameters</span>
                    </h4>
                    {/* Header row */}
                    <div className="signal-row" style={{ color: 'var(--text-dim)', fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      <span>Parameter</span>
                      <span style={{ textAlign: 'right' }}>Current</span>
                      <span style={{ textAlign: 'right' }}>Change</span>
                      <span>Trend</span>
                    </div>
                    {historicalAnalysis.map((item) => (
                      <div key={item.column} className="signal-row">
                        <span className="signal-name">{item.column.replace(/_/g, ' ')}</span>
                        <span className="signal-value">{item.latest_value.toLocaleString()}</span>
                        <span className={`signal-change ${item.change_percent >= 0 ? 'positive' : 'negative'}`}>
                          {item.change_percent > 0 ? '+' : ''}{item.change_percent.toFixed(1)}%
                        </span>
                        <span className={`trend-badge ${item.trend_direction.toLowerCase()}`}>
                          <span className="trend-arrow">{getTrendArrow(item.trend_direction)}</span>
                          {item.trend_direction}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="empty-state">
                  <span className="empty-state-icon">📊</span>
                  Upload the Excel file and generate engineering analytics to view the aircraft health dashboard.
                </p>
              )}
            </PanelCard>

            {/* ─── AI Maintenance Recommendation ─── */}
            <PanelCard
              title="AI Maintenance Recommendation"
              subtitle="Intelligent guidance generated from analytics & maintenance manual"
              accent="ai"
              badge={
                <span className="panel-badge ai-badge">
                  <span className="ai-sparkle">✨</span>
                  AI Powered
                </span>
              }
            >
              {isLoading && loadingPhase === 'ai' ? (
                <div className="loading-overlay">
                  <div className="loading-spinner" />
                  <span className="loading-text">AI is analyzing aircraft health...</span>
                </div>
              ) : recommendationSummary ? (
                <div className="recommendation-panel">
                  {/* AI Header */}
                  <div className="ai-header">
                    <div className="ai-brain-icon">🧠</div>
                    <div>
                      <span className="ai-label">AI Analysis</span>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {recommendationSummary.aircraft} · {recommendationSummary.aircraft_model}
                      </div>
                    </div>
                  </div>

                  {/* Health & Risk Status */}
                  <div className="status-banner">
                    <span className={`status-badge ${getHealthBadgeClass(recommendationSummary.health_status)}`}>
                      <span className="badge-dot" />
                      {recommendationSummary.health_status}
                    </span>
                    <span className={`status-badge ${getRiskBadgeClass(recommendationSummary.risk_level)}`}>
                      <span className="badge-dot" />
                      {recommendationSummary.risk_level} RISK
                    </span>
                    <span className={`status-badge ${recommendationSummary.safe_for_next_flight ? 'ok' : 'critical'}`}>
                      <span className="badge-dot" />
                      {recommendationSummary.safe_for_next_flight ? 'SAFE FOR FLIGHT' : 'GROUND AIRCRAFT'}
                    </span>
                  </div>

                  {/* Overall Summary */}
                  {recommendationSummary.overall_summary && (
                    <div className="overall-summary">
                      <p>{recommendationSummary.overall_summary}</p>
                    </div>
                  )}

                  {/* Flight Decision */}
                  {recommendationSummary.final_flight_decision && (
                    <div className="flight-decision">
                      <div className="decision-header">
                        <div className={`decision-icon ${recommendationSummary.final_flight_decision.can_fly_now ? 'fly' : 'ground'}`}>
                          {recommendationSummary.final_flight_decision.can_fly_now ? '✅' : '🚫'}
                        </div>
                        <div>
                          <div className="decision-title">{recommendationSummary.final_flight_decision.decision?.replace(/_/g, ' ')}</div>
                          <div className="decision-subtitle">
                            {recommendationSummary.final_flight_decision.required_before_next_flight}
                          </div>
                        </div>
                      </div>
                      <div className="decision-statement">
                        {recommendationSummary.final_flight_decision.ui_statement}
                      </div>
                      {recommendationSummary.final_flight_decision.decision_rationale && (
                        <div className="decision-rationale">
                          💡 {recommendationSummary.final_flight_decision.decision_rationale}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Threshold Violations */}
                  {recommendationSummary.threshold_violations?.length > 0 && (
                    <div className="violations-section">
                      <h4>⚠ Threshold Violations</h4>
                      {recommendationSummary.threshold_violations.map((v, i) => (
                        <div className="violation-card" key={i}>
                          <div className="violation-header">
                            <span className="violation-param">{v.parameter?.replace(/_/g, ' ')}</span>
                            <span className="violation-severity">{v.severity}</span>
                          </div>
                          <div className="violation-values">
                            <div className="violation-val">
                              <label>Observed</label>
                              <span style={{ color: 'var(--red)' }}>{v.observed_value}</span>
                            </div>
                            <div className="violation-val">
                              <label>Threshold</label>
                              <span>{v.manual_threshold}</span>
                            </div>
                          </div>
                          {v.explanation && <div className="violation-explanation">{v.explanation}</div>}
                          {v.manual_reference && <span className="manual-ref">📖 {v.manual_reference}</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Root Cause Analysis */}
                  {recommendationSummary.root_cause && (
                    <div className="root-cause-card">
                      <h4>🔍 Root Cause Analysis</h4>
                      <div className="cause-title">{recommendationSummary.root_cause.most_likely_cause}</div>
                      <ul className="evidence-list">
                        {(recommendationSummary.root_cause.supporting_evidence || []).map((e, i) => (
                          <li key={i}>{e}</li>
                        ))}
                      </ul>
                      {recommendationSummary.root_cause.manual_reference && (
                        <span className="manual-ref">📖 {recommendationSummary.root_cause.manual_reference}</span>
                      )}
                    </div>
                  )}

                  {/* Maintenance Actions */}
                  {recommendationSummary.maintenance_actions?.length > 0 && (
                    <div className="actions-list">
                      <h4>🔧 Maintenance Actions</h4>
                      {recommendationSummary.maintenance_actions.map((action, i) => (
                        <div className="action-item" key={i}>
                          <div className="action-priority">P{action.priority}</div>
                          <div className="action-content">
                            <div className="action-text">{action.action}</div>
                            <div className="action-reason">{action.reason}</div>
                            {action.manual_reference && <span className="manual-ref">📖 {action.manual_reference}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Inspection Checklist */}
                  {recommendationSummary.inspection_checklist?.length > 0 && (
                    <div className="checklist-section">
                      <h4>📋 Inspection Checklist</h4>
                      {recommendationSummary.inspection_checklist.map((item, i) => (
                        <div className="checklist-item" key={i}>
                          <div className="checklist-step">{item.step}</div>
                          <div className="checklist-content">
                            <div className="check-title">{item.inspection_item}</div>
                            <div className="check-criteria">✓ {item.acceptance_criteria}</div>
                            {item.manual_reference && <span className="manual-ref">📖 {item.manual_reference}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Confidence & Work Order Row */}
                  <div className="info-row">
                    <div className="info-card">
                      <span className="info-label">AI Confidence</span>
                      <span className="info-value" style={{ color: 'var(--purple)' }}>
                        {recommendationSummary.confidence?.score
                          ? `${(recommendationSummary.confidence.score * 100).toFixed(0)}%`
                          : 'N/A'}
                      </span>
                      <div className="confidence-bar-track">
                        <div
                          className="confidence-bar-fill"
                          style={{ width: `${(recommendationSummary.confidence?.score || 0) * 100}%` }}
                        />
                      </div>
                      {recommendationSummary.confidence?.rationale && (
                        <span className="info-sub">{recommendationSummary.confidence.rationale}</span>
                      )}
                    </div>
                    <div className="info-card">
                      <span className="info-label">Work Order Type</span>
                      <span className="info-value" style={{ color: 'var(--sky)' }}>
                        {recommendationSummary.work_order?.work_order_type || 'N/A'}
                      </span>
                      <span className="info-sub">
                        Priority: {recommendationSummary.work_order?.priority || 'N/A'}
                      </span>
                      <span className="info-sub">
                        {recommendationSummary.work_order?.estimated_maintenance_category || ''}
                      </span>
                    </div>
                  </div>

                  {/* Work Order Details */}
                  {recommendationSummary.work_order && (
                    <div className="work-order-card">
                      <h4>📝 Work Order — {recommendationSummary.work_order.title}</h4>
                      <div className="wo-meta">
                        <div className="wo-meta-item">
                          <label>Aircraft</label>
                          <span>{recommendationSummary.work_order.aircraft_id}</span>
                        </div>
                        <div className="wo-meta-item">
                          <label>Category</label>
                          <span>{recommendationSummary.work_order.estimated_maintenance_category}</span>
                        </div>
                      </div>

                      {recommendationSummary.work_order.tasks?.length > 0 && (
                        <ul className="wo-tasks">
                          {recommendationSummary.work_order.tasks.map((task, i) => (
                            <li key={i}>{task}</li>
                          ))}
                        </ul>
                      )}

                      {recommendationSummary.work_order.required_parts_or_tools?.length > 0 && (
                        <div className="wo-parts">
                          {recommendationSummary.work_order.required_parts_or_tools.map((part, i) => (
                            <span className="wo-part-tag" key={i}>{part}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Missing Information */}
                  {recommendationSummary.confidence?.missing_information?.length > 0 && (
                    <div className="summary-box" style={{ borderColor: 'rgba(251, 191, 36, 0.15)' }}>
                      <h4 style={{ color: 'var(--amber)' }}>⚡ Missing Information</h4>
                      <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0' }}>
                        {recommendationSummary.confidence.missing_information.map((info, i) => (
                          <li key={i} style={{ fontSize: '0.82rem', color: 'var(--text-muted)', padding: '3px 0', paddingLeft: '14px', position: 'relative' }}>
                            <span style={{ position: 'absolute', left: 0, color: 'var(--amber)' }}>·</span>
                            {info}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="empty-state">
                  <span className="empty-state-icon">🧠</span>
                  Generate the AI recommendation to view the intelligent maintenance decision board.
                </p>
              )}
            </PanelCard>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
