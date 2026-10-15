import React, { useState } from "react";
export default function Analytics() {
  const [filters, setFilters] = useState({
    service: "",
    outcome: "",
    source_ip: "",
    start: "",
    end: "",
  });
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [page, setPage] = useState(0);
  async function run(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setData(null);
    try {
      const r = await fetch("/api/analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          Object.fromEntries(
            Object.entries(filters).map(([k, v]) => [k, v.trim() || null]),
          ),
        ),
      });
      const d = await r.json();
      if (!r.ok) throw Error(d.detail || "Analytics unavailable");
      setData(d);
      setPage(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function save() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "loglens-analytics.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section
      className="query-panel analytics"
      aria-label="Whole-corpus analytics"
    >
      <div className="panel-head">
        <h2>Count records. Keep the sources.</h2>
        <span>02 / STRUCTURED</span>
      </div>
      <p>
        Deterministic analytics over every input record, not a model answer or
        top-3 sample. Filters use exact author-supplied fields, not
        natural-language guesses.
      </p>
      <form onSubmit={run}>
        <div className="analytics-fields">
          {[
            ["service", "Service", "ssh"],
            ["outcome", "Outcome", "failure"],
            ["source_ip", "Source IP", "192.0.2.10"],
            ["start", "From, inclusive (ISO + offset)", "2026-01-01T00:00:00Z"],
            ["end", "Until, exclusive (ISO + offset)", "2026-01-02T00:00:00Z"],
          ].map(([key, label, placeholder]) => (
            <label key={key}>
              {label}
              <input
                aria-label={label}
                value={filters[key]}
                placeholder={placeholder}
                onChange={(e) => {
                  setData(null);
                  setFilters({ ...filters, [key]: e.target.value });
                }}
              />
            </label>
          ))}
        </div>
        <button disabled={busy} type="submit">
          {busy ? "Counting…" : "Summarize all records"}
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {data && (
        <div aria-live="polite">
          <div className="panel-head">
            <h3>
              {data.matching_records} matching records / {data.corpus_records}{" "}
              total
            </h3>
            <button onClick={save}>Export analytics JSON</button>
          </div>
          <p>
            {data.structured_records} records carry structured fields. A line
            saying "five failures" counts as one record, not five attempts.
          </p>
          <div className="analytics-counts">
            {[
              ["by_service", "Service"],
              ["by_outcome", "Outcome"],
              ["by_source_ip", "Source IP"],
            ].map(([key, label]) => (
              <div key={key}>
                <h3>{label}</h3>
                {data[key].map((x) => (
                  <p key={x.value}>
                    <code>{x.value}</code>
                    <b>{x.records} records</b>
                  </p>
                ))}
              </div>
            ))}
          </div>
          <h3>Timeline / source records</h3>
          <p>
            UTC where explicit timestamps exist; undated records appear last.
            All matched rows are included in the JSON export.
          </p>
          {data.timeline.slice(page * 20, page * 20 + 20).map((x, i) => (
            <article className="evidence" key={x.event_id + "-" + i}>
              <h3>
                {x.event_id} · line {x.source_line}
              </h3>
              <small>{x.timestamp || "Timestamp unknown"}</small>
              <p>{x.text}</p>
            </article>
          ))}
          <div className="analytics-pages">
            <button disabled={!page} onClick={() => setPage(page - 1)}>
              Previous records
            </button>
            <span>
              Page {page + 1} /{" "}
              {Math.max(1, Math.ceil(data.timeline.length / 20))}
            </span>
            <button
              disabled={(page + 1) * 20 >= data.timeline.length}
              onClick={() => setPage(page + 1)}
            >
              Next records
            </button>
          </div>
          <p className="result-warning">{data.warning}</p>
        </div>
      )}
    </section>
  );
}
