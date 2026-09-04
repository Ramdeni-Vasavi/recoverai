import { useEffect, useState } from "react";
import { executeRecovery, getDecision, getExecution, getHealth, getOptimization, getPayments, getPrediction, getSummary } from "../services/api";

const stages = ["Payment", "ML Prediction", "AI Agent", "Optimization", "Guardrails", "Execution"];

function Stat({ label, value, accent }) {
  return <article className="stat"><span>{label}</span><strong className={accent ? "accent" : ""}>{value}</strong></article>;
}

function Pipeline({ data, onExecute, executing }) {
  const { payment, prediction, decision, optimization, execution } = data;
  return <section className="pipeline-panel">
    <div className="panel-heading"><div><span className="eyebrow">Selected payment</span><h2>{payment.external_payment_id}</h2></div><span className={`status-pill ${payment.status}`}>{payment.status}</span></div>
    <div className="pipeline">
      <div className="stage"><span className="stage-index">01</span><b>Payment</b><strong>{payment.currency} {Number(payment.amount).toFixed(2)}</strong><small>{payment.failure_reason || "Failure reason not supplied"}</small><small>{payment.attempt_count} attempt{payment.attempt_count === 1 ? "" : "s"}</small></div>
      <div className="stage"><span className="stage-index">02</span><b>ML Prediction</b>{prediction ? <><strong>{(Number(prediction.recovery_probability) * 100).toFixed(1)}%</strong><small>{prediction.model_version}</small></> : <small className="muted">No prediction yet</small>}</div>
      <div className="stage"><span className="stage-index">03</span><b>AI Agent</b>{decision ? <><strong>{decision.selected_action}</strong><small>{decision.reasoning_summary}</small></> : <small className="muted">No decision yet</small>}</div>
      <div className="stage"><span className="stage-index">04</span><b>Optimization</b>{optimization ? <><strong>{(Number(optimization.final_score) * 100).toFixed(1)}%</strong><small>Quantum {Number(optimization.quantum_inspired_score).toFixed(3)}</small></> : <small className="muted">No optimization yet</small>}</div>
      <div className="stage"><span className="stage-index">05</span><b>Guardrails</b>{optimization ? <><strong className={optimization.guardrail_allowed ? "good" : "bad"}>{optimization.guardrail_allowed ? "APPROVED" : "BLOCKED"}</strong><small>{optimization.guardrail_reason}</small></> : <small className="muted">Awaiting optimization</small>}</div>
      <div className="stage"><span className="stage-index">06</span><b>Execution</b>{execution ? <><strong className={execution.status === "BLOCKED" ? "bad" : "good"}>{execution.status}</strong><small>{execution.message}</small></> : <small className="muted">Not executed</small>}</div>
    </div>
    {optimization && !execution && <button className="primary-button" onClick={onExecute} disabled={executing || !optimization.guardrail_allowed}>{executing ? "Running..." : "Run Recovery"}</button>}
    {execution?.status === "SIMULATED" && <p className="simulation-note">Simulation: no real payment or customer message was sent.</p>}
  </section>;
}

export default function Dashboard() {
  const [health, setHealth] = useState("checking");
  const [summary, setSummary] = useState(null);
  const [payments, setPayments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [executing, setExecuting] = useState(false);

  async function loadDashboard() {
    setLoading(true); setError("");
    try {
      const [healthResult, summaryResult, paymentResult] = await Promise.all([getHealth(), getSummary(), getPayments()]);
      setHealth(healthResult.status === "healthy" ? "connected" : "disconnected"); setSummary(summaryResult); setPayments(paymentResult);
      const id = selectedId || paymentResult[0]?.id; setSelectedId(id || null);
      if (id) await loadPipeline(id);
    } catch (err) { setHealth("disconnected"); setError(err.message); } finally { setLoading(false); }
  }

  async function loadPipeline(id) {
    const results = await Promise.allSettled([getPrediction(id), getDecision(id), getOptimization(id), getExecution(id)]);
    setPipeline({ payment: payments.find((item) => item.id === id) || (await getPayments()).find((item) => item.id === id), prediction: results[0].status === "fulfilled" ? results[0].value : null, decision: results[1].status === "fulfilled" ? results[1].value : null, optimization: results[2].status === "fulfilled" ? results[2].value : null, execution: results[3].status === "fulfilled" ? results[3].value : null });
  }

  useEffect(() => { loadDashboard(); }, []);
  useEffect(() => { if (selectedId && payments.length) loadPipeline(selectedId); }, [selectedId]);

  async function handleExecute() { setExecuting(true); setError(""); try { await executeRecovery(selectedId); await loadPipeline(selectedId); } catch (err) { setError(err.message); } finally { setExecuting(false); } }

  return <main className="app-shell"><header className="topbar"><div className="brand-mark"><span className="brand-dot" /><div><h1>RecoverAI</h1><p>AI-Powered Payment Recovery System</p></div></div><div className="top-actions"><span className={`connection ${health}`}><i />{health === "checking" ? "Checking backend" : health === "connected" ? "Backend connected" : "Backend disconnected"}</span><button className="refresh-button" onClick={loadDashboard} disabled={loading}>Refresh</button></div></header>
    <section className="hero"><div><span className="eyebrow">Recovery command center</span><h2>Make every failed payment legible.</h2><p>Trace probability, decision, safety, and execution in one accountable workflow.</p></div><div className="hero-line">{stages.map((stage, index) => <span key={stage}><b>{String(index + 1).padStart(2, "0")}</b>{stage}</span>)}</div></section>
    {error && <div className="alert">{error}</div>}
    {loading && !summary ? <div className="loading">Connecting to RecoverAI backend...</div> : <><section className="stats"><Stat label="Failed payments" value={summary?.failed_payments ?? 0} /><Stat label="High recovery probability" value={summary?.high_recovery_probability ?? 0} accent /><Stat label="Recoveries" value={summary?.recoveries ?? 0} /><Stat label="Blocked actions" value={summary?.blocked_actions ?? 0} /></section><section className="workspace"><aside className="payment-list"><div className="section-heading"><div><span className="eyebrow">Inbox</span><h2>Payments</h2></div><span className="count">{payments.length}</span></div>{payments.length === 0 ? <p className="empty">No payments found.</p> : payments.map((payment) => <button className={`payment-row ${payment.id === selectedId ? "selected" : ""}`} key={payment.id} onClick={() => setSelectedId(payment.id)}><span><b>{payment.external_payment_id}</b><small>{payment.failure_reason || "Payment event"}</small></span><span className="row-meta"><strong>{payment.currency} {Number(payment.amount).toFixed(2)}</strong><em className={`status-pill ${payment.status}`}>{payment.status}</em></span></button>)}</aside>{pipeline?.payment ? <Pipeline data={pipeline} onExecute={handleExecute} executing={executing} /> : <div className="empty large">Select a payment to inspect its recovery pipeline.</div>}</section></>}
  </main>;
}
