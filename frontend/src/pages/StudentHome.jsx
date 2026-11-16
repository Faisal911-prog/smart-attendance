import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Card, ProgressBar, Spinner, fmtDateTime, fmtPct, useLoad } from "../components/ui.jsx";

export default function StudentHome() {
  const { data, error, loading } = useLoad(() => api.get("/attendance/my/"));

  if (loading) return <Spinner />;
  if (error) return <Alert>{error}</Alert>;

  const open = data.open_sessions.filter((s) => !s.checked_in);

  return (
    <div>
      <h1>My attendance</h1>

      {open.length > 0 && (
        <Card title="Open now" className="highlight">
          <ul className="plain-list">
            {open.map((s) => (
              <li key={s.id}>
                <div>
                  <strong>{s.course_code}</strong> · {s.title}
                  <div className="muted small">Open until {fmtDateTime(s.ends_at)}</div>
                </div>
                <Link className="btn btn-sm" to="/scan">
                  Check in
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Courses">
        {data.courses.length === 0 ? (
          <p className="muted">You are not enrolled in any course yet. Ask your lecturer to add you.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Lecturer</th>
                  <th className="num">Attended</th>
                  <th style={{ width: "30%" }}>Attendance rate</th>
                </tr>
              </thead>
              <tbody>
                {data.courses.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.code}</strong>
                      <div className="muted small">{c.name}</div>
                    </td>
                    <td>{c.lecturer_name}</td>
                    <td className="num">
                      {c.attended} / {c.sessions_held}
                    </td>
                    <td>
                      {c.rate === null ? (
                        <span className="muted">No sessions yet</span>
                      ) : (
                        <div className="rate-cell">
                          <ProgressBar value={c.rate} />
                          <span>{fmtPct(c.rate)}</span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Recent check-ins">
        {data.recent.length === 0 ? (
          <p className="muted">No check-ins yet.</p>
        ) : (
          <ul className="plain-list">
            {data.recent.map((r, i) => (
              <li key={i}>
                <span>
                  <strong>{r.course_code}</strong> · {r.session}
                </span>
                <span className="muted small">{fmtDateTime(r.scanned_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
