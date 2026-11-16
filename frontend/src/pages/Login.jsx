import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api.js";
import { homePathFor, useAuth } from "../auth.jsx";
import { Alert } from "../components/ui.jsx";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || homePathFor(user)} replace />;

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const loggedIn = await login(username.trim(), password);
      navigate(location.state?.from || homePathFor(loggedIn), { replace: true });
    } catch (err) {
      setError(err.status === 401 ? "Wrong username or password." : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand brand-lg">
          <span className="brand-mark" aria-hidden="true">
            ✓
          </span>
          Smart Attendance
        </div>
        <p className="muted">Sign in with your university account.</p>
        <Alert>{error}</Alert>
        <label>
          Username
          <input
            autoFocus
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button className="btn btn-block" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
