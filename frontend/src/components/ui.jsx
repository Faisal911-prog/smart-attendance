import { useEffect, useState } from "react";
import { errorMessage } from "../api.js";

export function Alert({ kind = "error", children }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading…" }) {
  return <p className="muted">{label}</p>;
}

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function ProgressBar({ value, tone }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const autoTone = tone || (pct >= 75 ? "good" : pct >= 50 ? "warn" : "bad");
  return (
    <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className={`progress-fill tone-${autoTone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

// Horizontal bars: items = [{ label, value }]
export function BarList({ items, unit = "", emptyText = "No data yet." }) {
  if (!items.length) return <p className="muted">{emptyText}</p>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="barlist">
      {items.map((item) => (
        <li key={item.label}>
          <span className="barlist-label">{item.label}</span>
          <span className="barlist-track">
            <span className="barlist-fill" style={{ width: `${(item.value / max) * 100}%` }} />
          </span>
          <span className="barlist-value">
            {item.value}
            {unit}
          </span>
        </li>
      ))}
    </ul>
  );
}

// Vertical columns: items = [{ label, value }]
export function Columns({ items, max, unit = "" }) {
  const top = max ?? Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="columns" role="img" aria-label="Bar chart">
      {items.map((item) => (
        <div className="column" key={item.label} title={`${item.label}: ${item.value}${unit}`}>
          <div className="column-value">{item.value}</div>
          <div className="column-bar" style={{ height: `${Math.max(2, (item.value / top) * 100)}%` }} />
          <div className="column-label">{item.label}</div>
        </div>
      ))}
    </div>
  );
}

// Loads data on mount (and whenever `deps` change) and exposes reload().
export function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: "" }));
    loader()
      .then((data) => !cancelled && setState({ data, error: "", loading: false }))
      .catch((err) => !cancelled && setState({ data: null, error: errorMessage(err), loading: false }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}

export const fmtDateTime = (value) =>
  value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "–";

export const fmtTime = (value) =>
  value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "–";

export const fmtPct = (value) => (value === null || value === undefined ? "–" : `${value}%`);

export const REASON_LABELS = {
  INVALID_TOKEN: "Invalid QR code",
  EXPIRED_TOKEN: "Expired QR code",
  SESSION_CLOSED: "Session closed",
  NOT_ENROLLED: "Not enrolled",
  ALREADY_RECORDED: "Already recorded",
  OUT_OF_RANGE: "Outside allowed area",
  LOW_ACCURACY: "Location too imprecise",
  BAD_COORDINATES: "Invalid coordinates",
};
