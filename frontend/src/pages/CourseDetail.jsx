import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api.js";
import {
  Alert,
  BarList,
  Card,
  Columns,
  ProgressBar,
  REASON_LABELS,
  Spinner,
  Stat,
  fmtDateTime,
  fmtPct,
  useLoad,
} from "../components/ui.jsx";

const TABS = [
  ["sessions", "Sessions"],
  ["students", "Students"],
  ["analytics", "Analytics"],
];

export default function CourseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState("sessions");
  const course = useLoad(() => api.get(`/courses/${id}/`), [id]);

  async function removeCourse() {
    if (!window.confirm("Delete this course with all its sessions and attendance records? This cannot be undone.")) return;
    try {
      await api.del(`/courses/${id}/`);
      navigate("/courses", { replace: true });
    } catch (err) {
      window.alert(errorMessage(err));
    }
  }

  if (course.loading) return <Spinner />;
  if (course.error) return <Alert>{course.error}</Alert>;

  return (
    <div>
      <p className="crumb">
        <Link to="/courses">← Courses</Link>
      </p>
      <div className="page-head">
        <div>
          <div className="course-code">{course.data.code}</div>
          <h1>{course.data.name}</h1>
          <p className="muted">Lecturer: {course.data.lecturer_name}</p>
        </div>
        <button className="btn btn-danger btn-sm" onClick={removeCourse}>
          Delete course
        </button>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "tab active" : "tab"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "sessions" && <SessionsTab courseId={id} />}
      {tab === "students" && <StudentsTab courseId={id} />}
      {tab === "analytics" && <AnalyticsTab courseId={id} />}
    </div>
  );
}

/* ------------------------------------------------------------------ sessions */

function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function SessionsTab({ courseId }) {
  const sessions = useLoad(() => api.get(`/sessions/?course=${courseId}`), [courseId]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [locating, setLocating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    starts_at: toLocalInput(new Date()),
    duration: 90,
    latitude: "",
    longitude: "",
    radius_m: 100,
    qr_interval_seconds: 30,
  });
  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  function fillMyLocation() {
    setError("");
    if (!navigator.geolocation) {
      setError("This browser cannot provide your location.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({
          ...f,
          latitude: pos.coords.latitude.toFixed(6),
          longitude: pos.coords.longitude.toFixed(6),
        }));
        setLocating(false);
      },
      () => {
        setError("Could not read your location. Allow location access or type the coordinates.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 20000 },
    );
  }

  async function create(event) {
    event.preventDefault();
    setError("");
    try {
      const start = new Date(form.starts_at);
      const end = new Date(start.getTime() + Number(form.duration) * 60000);
      await api.post("/sessions/", {
        course: Number(courseId),
        title: form.title.trim(),
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        radius_m: Number(form.radius_m),
        qr_interval_seconds: Number(form.qr_interval_seconds),
      });
      setShowForm(false);
      setForm({ ...form, title: "" });
      sessions.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div>
      <div className="row row-end">
        <button className="btn" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New session"}
        </button>
      </div>

      {showForm && (
        <Card title="New session">
          <form className="form" onSubmit={create}>
            <Alert>{error}</Alert>
            <label>
              Title
              <input value={form.title} onChange={set("title")} placeholder="Week 3 – Arrays" required />
            </label>
            <div className="grid-2">
              <label>
                Starts
                <input type="datetime-local" value={form.starts_at} onChange={set("starts_at")} required />
              </label>
              <label>
                Attendance window (minutes)
                <input type="number" min="5" max="600" value={form.duration} onChange={set("duration")} required />
              </label>
            </div>
            <fieldset>
              <legend>Classroom location</legend>
              <div className="grid-3">
                <label>
                  Latitude
                  <input value={form.latitude} onChange={set("latitude")} required />
                </label>
                <label>
                  Longitude
                  <input value={form.longitude} onChange={set("longitude")} required />
                </label>
                <label>
                  Allowed radius (m)
                  <input type="number" min="10" max="2000" value={form.radius_m} onChange={set("radius_m")} required />
                </label>
              </div>
              <button type="button" className="btn btn-secondary btn-sm" onClick={fillMyLocation} disabled={locating}>
                {locating ? "Locating…" : "Use my current location"}
              </button>
              <p className="muted small">Stand in the classroom and press the button, or type the coordinates.</p>
            </fieldset>
            <label>
              QR code changes every (seconds)
              <input
                type="number"
                min="10"
                max="300"
                value={form.qr_interval_seconds}
                onChange={set("qr_interval_seconds")}
                required
              />
            </label>
            <div>
              <button className="btn">Create session</button>
            </div>
          </form>
        </Card>
      )}

      {sessions.loading ? (
        <Spinner />
      ) : sessions.error ? (
        <Alert>{sessions.error}</Alert>
      ) : sessions.data.length === 0 ? (
        <Card>
          <p className="muted">No sessions yet.</p>
        </Card>
      ) : (
        <Card>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Starts</th>
                  <th>Status</th>
                  <th className="num">Present</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {sessions.data.map((s) => (
                  <tr key={s.id}>
                    <td>{s.title}</td>
                    <td>{fmtDateTime(s.starts_at)}</td>
                    <td>
                      {s.is_accepting ? (
                        <span className="badge badge-live">open</span>
                      ) : s.opened_at ? (
                        <span className="badge">closed</span>
                      ) : (
                        <span className="badge badge-muted">not started</span>
                      )}
                    </td>
                    <td className="num">
                      {s.present_count} / {s.enrolled_count}
                    </td>
                    <td className="num">
                      <Link className="btn btn-sm btn-secondary" to={`/sessions/${s.id}`}>
                        {s.is_accepting ? "Show QR" : "Open"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ students */

function StudentsTab({ courseId }) {
  const students = useLoad(() => api.get(`/courses/${courseId}/students/`), [courseId]);
  const [codes, setCodes] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function enrol(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    const list = codes
      .split(/[\s,;]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    if (!list.length) return;
    try {
      const result = await api.post(`/courses/${courseId}/students/`, { neptun_codes: list });
      const parts = [`${result.added} student(s) added.`];
      if (result.already_enrolled.length) parts.push(`Already enrolled: ${result.already_enrolled.join(", ")}.`);
      if (result.unknown.length) parts.push(`Unknown codes: ${result.unknown.join(", ")}.`);
      setMessage(parts.join(" "));
      setCodes("");
      students.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove(student) {
    if (!window.confirm(`Remove ${student.name} from this course?`)) return;
    try {
      await api.del(`/courses/${courseId}/students/${student.id}/`);
      students.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div>
      <Card title="Enrol students">
        <form className="form" onSubmit={enrol}>
          <Alert>{error}</Alert>
          <Alert kind="success">{message}</Alert>
          <label>
            Student codes (separated by spaces, commas or new lines)
            <textarea rows={3} value={codes} onChange={(e) => setCodes(e.target.value)} placeholder="STU001, STU002, …" />
          </label>
          <div>
            <button className="btn" disabled={!codes.trim()}>
              Add students
            </button>
          </div>
        </form>
      </Card>

      <Card title={`Enrolled students${students.data ? ` (${students.data.length})` : ""}`}>
        {students.loading ? (
          <Spinner />
        ) : students.error ? (
          <Alert>{students.error}</Alert>
        ) : students.data.length === 0 ? (
          <p className="muted">Nobody is enrolled yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Username</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {students.data.map((s) => (
                  <tr key={s.id}>
                    <td>{s.neptun_code}</td>
                    <td>{s.name}</td>
                    <td>{s.username}</td>
                    <td className="num">
                      <button className="btn btn-ghost btn-sm" onClick={() => remove(s)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ----------------------------------------------------------------- analytics */

function AnalyticsTab({ courseId }) {
  const stats = useLoad(() => api.get(`/courses/${courseId}/analytics/`), [courseId]);

  if (stats.loading) return <Spinner />;
  if (stats.error) return <Alert>{stats.error}</Alert>;
  const d = stats.data;

  if (d.sessions_held === 0) {
    return (
      <Card>
        <p className="muted">Analytics appear after the first session has been opened.</p>
      </Card>
    );
  }

  const atRisk = d.students.filter((s) => s.at_risk).length;
  const rejected = Object.entries(d.rejected_attempts)
    .filter(([reason]) => reason !== "ALREADY_RECORDED")
    .map(([reason, value]) => ({ label: REASON_LABELS[reason] || reason, value }));

  return (
    <div>
      <div className="stats">
        <Stat label="Sessions held" value={d.sessions_held} />
        <Stat label="Enrolled students" value={d.enrolled} />
        <Stat label="Average attendance" value={fmtPct(d.average_rate)} />
        <Stat label="At risk" value={atRisk} hint={`below ${d.at_risk_threshold}%`} />
      </div>

      <Card title="Attendance per session (%)">
        <Columns
          max={100}
          unit="%"
          items={d.sessions.map((s, i) => ({ label: `#${i + 1}`, value: Math.round(s.rate) }))}
        />
      </Card>

      <Card title="Students">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th className="num">Present</th>
                <th style={{ width: "32%" }}>Rate</th>
              </tr>
            </thead>
            <tbody>
              {d.students.map((s) => (
                <tr key={s.id}>
                  <td>{s.neptun_code}</td>
                  <td>
                    {s.name} {s.at_risk && <span className="badge badge-warn">at risk</span>}
                  </td>
                  <td className="num">
                    {s.present} / {s.held}
                  </td>
                  <td>
                    <div className="rate-cell">
                      <ProgressBar value={s.rate} />
                      <span>{fmtPct(s.rate)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Rejected check-in attempts">
        <BarList items={rejected} emptyText="No suspicious attempts recorded." />
      </Card>
    </div>
  );
}
