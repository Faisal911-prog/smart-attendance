import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, BarList, Card, Columns, ProgressBar, REASON_LABELS, Spinner, Stat, fmtPct, useLoad } from "../components/ui.jsx";

export default function AdminOverview() {
  const { data, error, loading } = useLoad(() => api.get("/analytics/overview/"));

  if (loading) return <Spinner />;
  if (error) return <Alert>{error}</Alert>;

  const rejected = Object.entries(data.rejected_attempts_30d).map(([reason, value]) => ({
    label: REASON_LABELS[reason] || reason,
    value,
  }));

  return (
    <div>
      <h1>Overview</h1>

      <div className="stats">
        <Stat label="Students" value={data.users.students} />
        <Stat label="Lecturers" value={data.users.lecturers} />
        <Stat label="Courses" value={data.courses} />
        <Stat label="Sessions held" value={data.sessions_held} />
        <Stat label="Check-ins" value={data.checkins} />
        <Stat label="Average attendance" value={fmtPct(data.average_rate)} />
      </div>

      <Card title="Check-ins in the last 14 days">
        <Columns items={data.daily_checkins.map((d) => ({ label: d.day.slice(5), value: d.count }))} />
      </Card>

      <div className="grid-2">
        <Card title="Courses by attendance rate">
          {data.courses_table.length === 0 ? (
            <p className="muted">No courses yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Course</th>
                    <th className="num">Sessions</th>
                    <th style={{ width: "40%" }}>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.courses_table.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/courses/${c.id}`}>
                          <strong>{c.code}</strong>
                        </Link>
                        <div className="muted small">{c.lecturer}</div>
                      </td>
                      <td className="num">{c.sessions_held}</td>
                      <td>
                        <div className="rate-cell">
                          <ProgressBar value={c.rate} />
                          <span>{fmtPct(c.rate)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Rejected check-ins (30 days)">
          <BarList items={rejected} emptyText="No rejected attempts." />
        </Card>
      </div>
    </div>
  );
}
