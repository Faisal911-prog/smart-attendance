import { useState } from "react";
import { api, errorMessage } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Card, Spinner, useLoad } from "../components/ui.jsx";

const EMPTY = {
  username: "",
  first_name: "",
  last_name: "",
  email: "",
  role: "STUDENT",
  neptun_code: "",
  password: "",
  is_active: true,
};

export default function Users() {
  const { user: me } = useAuth();
  const [role, setRole] = useState("");
  const [query, setQuery] = useState("");
  const users = useLoad(
    () => api.get(`/users/?${new URLSearchParams({ ...(role && { role }), ...(query && { q: query }) })}`),
    [role, query],
  );

  const [editing, setEditing] = useState(null); // null | "new" | user object
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  function startNew() {
    setForm(EMPTY);
    setEditing("new");
    setError("");
  }

  function startEdit(user) {
    setForm({ ...EMPTY, ...user, neptun_code: user.neptun_code || "", email: user.email || "", password: "" });
    setEditing(user);
    setError("");
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    const body = {
      username: form.username.trim(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      role: form.role,
      neptun_code: form.role === "STUDENT" ? form.neptun_code.trim() : null,
      is_active: form.is_active,
    };
    if (form.password) body.password = form.password;
    try {
      if (editing === "new") await api.post("/users/", body);
      else await api.patch(`/users/${editing.id}/`, body);
      setEditing(null);
      users.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove(user) {
    if (!window.confirm(`Delete ${user.full_name} (${user.username})? Their attendance records are deleted too.`)) return;
    try {
      await api.del(`/users/${user.id}/`);
      users.reload();
    } catch (err) {
      window.alert(errorMessage(err));
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Users</h1>
        <button className="btn" onClick={startNew}>
          New user
        </button>
      </div>

      {editing && (
        <Card title={editing === "new" ? "New user" : `Edit ${editing.username}`}>
          <form className="form" onSubmit={save}>
            <Alert>{error}</Alert>
            <div className="grid-2">
              <label>
                Username
                <input value={form.username} onChange={set("username")} required />
              </label>
              <label>
                Role
                <select value={form.role} onChange={set("role")}>
                  <option value="STUDENT">Student</option>
                  <option value="LECTURER">Lecturer</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </label>
              <label>
                First name
                <input value={form.first_name} onChange={set("first_name")} />
              </label>
              <label>
                Last name
                <input value={form.last_name} onChange={set("last_name")} />
              </label>
              <label>
                Email
                <input type="email" value={form.email} onChange={set("email")} />
              </label>
              {form.role === "STUDENT" && (
                <label>
                  Student code (6 characters)
                  <input value={form.neptun_code} onChange={set("neptun_code")} maxLength={6} required />
                </label>
              )}
              <label>
                {editing === "new" ? "Password" : "New password (leave empty to keep)"}
                <input
                  type="password"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={set("password")}
                  required={editing === "new"}
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                Account is active
              </label>
            </div>
            <div className="row">
              <button className="btn">Save</button>
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <div className="filters">
          <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter by role">
            <option value="">All roles</option>
            <option value="STUDENT">Students</option>
            <option value="LECTURER">Lecturers</option>
            <option value="ADMIN">Admins</option>
          </select>
          <input
            type="search"
            placeholder="Search name, username or code…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {users.loading && !users.data ? (
          <Spinner />
        ) : users.error ? (
          <Alert>{users.error}</Alert>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Code</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id}>
                    <td>{u.full_name}</td>
                    <td>{u.username}</td>
                    <td>
                      <span className={`badge role-${u.role.toLowerCase()}`}>{u.role.toLowerCase()}</span>
                    </td>
                    <td>{u.neptun_code || "–"}</td>
                    <td>{u.is_active ? "active" : <span className="muted">inactive</span>}</td>
                    <td className="num">
                      <button className="btn btn-ghost btn-sm" onClick={() => startEdit(u)}>
                        Edit
                      </button>
                      {u.id !== me.id && (
                        <button className="btn btn-ghost btn-sm" onClick={() => remove(u)}>
                          Delete
                        </button>
                      )}
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
