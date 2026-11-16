import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Card, Spinner, useLoad } from "../components/ui.jsx";

export default function Courses() {
  const { user } = useAuth();
  const isAdmin = user.role === "ADMIN";
  const courses = useLoad(() => api.get("/courses/"));
  const lecturers = useLoad(() => (isAdmin ? api.get("/users/?role=LECTURER") : Promise.resolve([])), [isAdmin]);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", description: "", lecturer: "" });
  const [error, setError] = useState("");

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function create(event) {
    event.preventDefault();
    setError("");
    try {
      const body = { code: form.code.trim(), name: form.name.trim(), description: form.description };
      if (isAdmin) body.lecturer = Number(form.lecturer);
      await api.post("/courses/", body);
      setForm({ code: "", name: "", description: "", lecturer: "" });
      setShowForm(false);
      courses.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Courses</h1>
        <button className="btn" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New course"}
        </button>
      </div>

      {showForm && (
        <Card title="New course">
          <form className="form" onSubmit={create}>
            <Alert>{error}</Alert>
            <div className="grid-2">
              <label>
                Course code
                <input value={form.code} onChange={set("code")} placeholder="INF101" required maxLength={20} />
              </label>
              <label>
                Name
                <input value={form.name} onChange={set("name")} placeholder="Programming Fundamentals" required />
              </label>
            </div>
            {isAdmin && (
              <label>
                Lecturer
                <select value={form.lecturer} onChange={set("lecturer")} required>
                  <option value="">Choose…</option>
                  {(lecturers.data || []).map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.full_name} ({l.username})
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Description (optional)
              <textarea rows={2} value={form.description} onChange={set("description")} />
            </label>
            <div>
              <button className="btn">Create course</button>
            </div>
          </form>
        </Card>
      )}

      {courses.loading ? (
        <Spinner />
      ) : courses.error ? (
        <Alert>{courses.error}</Alert>
      ) : courses.data.length === 0 ? (
        <Card>
          <p className="muted">No courses yet. Create the first one.</p>
        </Card>
      ) : (
        <div className="grid-cards">
          {courses.data.map((c) => (
            <Link key={c.id} to={`/courses/${c.id}`} className="card course-card">
              <div className="course-code">{c.code}</div>
              <h3>{c.name}</h3>
              <p className="muted small">{c.lecturer_name}</p>
              <div className="course-meta">
                <span>{c.student_count} students</span>
                <span>{c.session_count} sessions</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
