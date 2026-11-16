import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api.js";
import { Alert, Card, REASON_LABELS, Spinner, fmtDateTime, fmtTime, useLoad } from "../components/ui.jsx";

// Live view for the lecturer: rotating QR code on the projector, live roster beside it.
export default function SessionLive() {
  const { id } = useParams();
  const session = useLoad(() => api.get(`/sessions/${id}/`), [id]);
  const [actionError, setActionError] = useState("");

  async function act(action) {
    setActionError("");
    try {
      await api.post(`/sessions/${id}/${action}/`);
      session.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  async function exportCsv() {
    try {
      const blob = await api.download(`/sessions/${id}/export/`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `attendance_${id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  if (session.loading && !session.data) return <Spinner />;
  if (session.error) return <Alert>{session.error}</Alert>;
  const s = session.data;
  const accepting = s.is_accepting;

  return (
    <div>
      <p className="crumb">
        <Link to={`/courses/${s.course}`}>← {s.course_code}</Link>
      </p>
      <div className="page-head">
        <div>
          <h1>{s.title}</h1>
          <p className="muted">
            {s.course_code} · {fmtDateTime(s.starts_at)} · allowed radius {s.radius_m} m · code changes every{" "}
            {s.qr_interval_seconds} s
          </p>
        </div>
        <div className="row">
          <button className="btn btn-secondary" onClick={exportCsv}>
            Export CSV
          </button>
          {accepting ? (
            <button className="btn btn-danger" onClick={() => act("close")}>
              Close attendance
            </button>
          ) : (
            <button className="btn" onClick={() => act("open")}>
              {s.opened_at ? "Reopen attendance" : "Open attendance"}
            </button>
          )}
        </div>
      </div>
      <Alert>{actionError}</Alert>

      <div className="live-grid">
        <Card title="QR code" className="qr-card">
          {accepting ? (
            <QrPanel sessionId={id} />
          ) : (
            <p className="muted">
              Attendance is not open. Press “{s.opened_at ? "Reopen attendance" : "Open attendance"}” to show the QR
              code to the students.
            </p>
          )}
        </Card>
        <Roster sessionId={id} />
      </div>
    </div>
  );
}

function QrPanel({ sessionId }) {
  const [qr, setQr] = useState(null);
  const [error, setError] = useState("");
  const [left, setLeft] = useState(0);

  // Fetch a fresh code whenever the current one is about to rotate.
  useEffect(() => {
    let cancelled = false;
    let timer;
    const load = async () => {
      try {
        const data = await api.get(`/sessions/${sessionId}/qr/`);
        if (cancelled) return;
        setQr(data);
        setError("");
        setLeft(Math.ceil(data.expires_in));
        timer = setTimeout(load, Math.max(1000, data.expires_in * 1000 + 250));
      } catch (err) {
        if (cancelled) return;
        setError(errorMessage(err));
        timer = setTimeout(load, 5000);
      }
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId]);

  // Countdown display.
  useEffect(() => {
    const timer = setInterval(() => setLeft((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, []);

  if (error && !qr) return <Alert>{error}</Alert>;
  if (!qr) return <Spinner label="Generating QR code…" />;

  return (
    <div className="qr-box">
      <img src={qr.image} alt="Attendance QR code" className="qr-img" />
      <div className="qr-timer">
        New code in <strong>{left}</strong> s
      </div>
      <div className="progress">
        <div className="progress-fill tone-good" style={{ width: `${(left / qr.interval) * 100}%` }} />
      </div>
      {error && <Alert>{error}</Alert>}
      <p className="muted small">
        Students scan this code with their phone camera or inside the app. A photo of an old code stops working
        after about {qr.interval * 2} seconds.
      </p>
    </div>
  );
}

function Roster({ sessionId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer;
    const load = async () => {
      try {
        const result = await api.get(`/sessions/${sessionId}/attendance/`);
        if (!cancelled) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
      if (!cancelled) timer = setTimeout(load, 4000);
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId]);

  if (!data) return <Card title="Attendance">{error ? <Alert>{error}</Alert> : <Spinner />}</Card>;

  return (
    <Card title={`Attendance: ${data.present} / ${data.enrolled}`}>
      <Alert>{error}</Alert>
      <div className="table-wrap roster">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Status</th>
              <th className="num">Time</th>
              <th className="num">Distance</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.student_id} className={r.present ? "row-present" : ""}>
                <td>
                  {r.name}
                  <div className="muted small">{r.neptun_code}</div>
                </td>
                <td>{r.present ? <span className="badge badge-live">present</span> : <span className="badge badge-muted">absent</span>}</td>
                <td className="num">{fmtTime(r.scanned_at)}</td>
                <td className="num">{r.distance_m !== null ? `${r.distance_m} m` : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.recent_rejections.length > 0 && (
        <>
          <h3>Rejected attempts</h3>
          <ul className="plain-list small">
            {data.recent_rejections.map((r, i) => (
              <li key={i}>
                <span>
                  {r.student} · {REASON_LABELS[r.reason] || r.reason}
                  {r.distance_m !== null && ` (${r.distance_m} m away)`}
                </span>
                <span className="muted">{fmtTime(r.created_at)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
