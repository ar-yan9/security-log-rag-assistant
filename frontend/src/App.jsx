import React, { useEffect, useRef, useState } from 'react';
const prompts = ['What happened with repeated SSH login failures?', 'What DNS request occurred?', 'Did the scheduled backup finish without errors?'];
const labels = {
  evidence_found: 'Retrieved evidence', answer_ready: 'Evidence selection ready',
  insufficient_evidence: 'Not enough evidence', generation_unavailable: 'Local model is not configured',
  generation_rejected: 'Model output failed validation',
};
export default function App() {
  const [health, setHealth] = useState(null);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState('search');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const abort = useRef(null);
  useEffect(() => {
    let active = true;
    fetch('/api/health').then(r => { if (!r.ok) throw Error(); return r.json(); })
      .then(data => { if(active) setHealth(data); }).catch(() => { if(active) setHealth({offline: true}); });
    return () => { active = false; abort.current?.abort(); };
  }, []);
  async function submit(event) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setError(''); setResult(null); setBusy(true);
    const controller = new AbortController(); abort.current = controller;
    const timer = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(`/api/${mode}`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question:question.trim(),limit:3}), signal:controller.signal,
      });
      if (!response.ok) throw Error(response.status === 503 ? 'Local corpus or model is unavailable. Check the backend terminal and setup guide.' : 'The query or local configuration is invalid. Check the backend terminal.');
      setResult(await response.json());
    } catch (e) {
      setError(e.name === 'AbortError' ? 'Request timed out or was cancelled. The backend may still be finishing inference. Try again after it finishes.' : e.message || 'Could not reach the local backend.');
    } finally { clearTimeout(timer); setBusy(false); abort.current = null; }
  }
  return <div className="workbench">
    <aside><a className="brand" href="/">◈ <span>LOG LENS<small>LOCAL EVIDENCE WORKBENCH</small></span></a>
      <div className="nav-item">01 <span>Investigate</span><b>↗</b></div>
      <section className="source-card"><span className="eyebrow">CURRENT SOURCE</span><h3>{health?.sample_corpus === false ? 'Configured local corpus' : 'Synthetic lab logs'}</h3><p>{health?.sample_corpus === false ? 'Authorized local JSONL. Review the configured source in your backend terminal.' : '7 normalized auth, DNS, network and backup events. No live traffic.'}</p><div className="source-tag">{health?.sample_corpus === false ? 'local JSONL' : 'demo.jsonl'}</div></section>
      <p className="sidebar-note">Local-first learning project.<br/>Not a SIEM or an incident verdict.</p>
    </aside>
    <main>
      <header><span className="eyebrow">SECURITY LOG RAG ASSISTANT / v0.1</span><span className={`status ${health?.offline ? 'offline':''}`}>{health?.offline ? 'Backend unreachable' : health ? `Local · ${health.retrieval_mode}` : 'Connecting to backend…'}</span></header>
      <section className="intro"><div className="eyebrow accent">FROM QUESTION TO SOURCE</div><h1>Ask the logs.<br/><span>Keep the evidence.</span></h1><p>Find relevant events, inspect the original lines, and use a local model to select checked quotes. No unsupported incident conclusions.</p></section>
      <section className="query-panel" aria-label="Investigation query">
        <div className="panel-head"><h2>Start an investigation</h2><span>01 / QUERY</span></div>
        <form onSubmit={submit}><label htmlFor="question">What would you like to check?</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={1000} placeholder="e.g. What happened with repeated SSH login failures?" disabled={busy}/>
          <div className="form-bottom"><label className="mode-label">Mode<select aria-label="Mode" value={mode} onChange={e=>setMode(e.target.value)} disabled={busy}><option value="search">Retrieve evidence</option><option value="ask">Local RAG · checked quotes</option></select></label><span className="count">{question.length}/1000</span><button type="submit" disabled={busy || !question.trim()}>{busy ? 'Checking local evidence…' : mode === 'ask' ? 'Ask local model ↗' : 'Find evidence ↗'}</button></div>
        </form><div className="suggestions"><span>TRY</span>{prompts.map((p,i)=><button key={p} disabled={busy} onClick={()=>setQuestion(p)}>{['SSH login failures','DNS activity','Backup status'][i]}</button>)}</div>
      </section>
      <div role="status" aria-live="polite">{busy && <p className="notice">First semantic search may download the public embedding model. Local generation can take a minute on CPU. Your query is processed by the local backend.</p>}</div>
      {error && <p role="alert" className="error">{error}</p>}
      {result ? <section className="results" aria-label="Results"><div className="panel-head"><h2>{labels[result.status] || 'Result'}</h2><span>{result.evidence?.length || 0} SOURCE EVENTS</span></div><p className="asked">{result.question}</p>
        {result.status === 'generation_unavailable' && <p className="notice">Retrieval works, but no GGUF model is configured. Set LOCAL_GGUF_MODEL using the run guide, then restart the backend. No answer was invented.</p>}
        {result.status === 'generation_rejected' && <p className="notice">The model output did not pass citation/quote checks. Review the retrieved events below. No generated finding was accepted.</p>}
        {result.status === 'insufficient_evidence' && <p className="notice">The current corpus does not provide enough evidence for a checked answer. This does not prove that the event never happened.</p>}
        {result.findings?.length > 0 && <div className="findings"><h3>Model-selected quotes</h3>{result.findings.map(f=><blockquote key={f.event_id}><p>{f.quote}</p><cite>{f.event_id} · source line {f.source_line}</cite></blockquote>)}</div>}
        {result.evidence?.map((e,i)=><article className="evidence" key={e.event_id}><div className="evidence-top"><span className="evidence-index">0{i+1}</span><h3>{e.event_id}</h3><span>LINE {e.source_line}</span><span className="score">similarity {e.similarity.toFixed(3)}</span></div><p>{e.text}</p></article>)}
        <p className="result-warning">{result.warning}</p>
      </section> : !busy && <section className="empty"><span className="empty-icon">⌕</span><div><h3>Every finding starts with a source.</h3><p>Your retrieved events and checked quotes will appear here.</p></div></section>}
      <footer><span>LOCAL BY DESIGN</span><p>Similarity is not confidence. Logs are untrusted data. Review every finding.</p><span>HUMAN REVIEW REQUIRED</span></footer>
    </main>
  </div>;
}
