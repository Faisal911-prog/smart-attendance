import { useState } from "react";
import { api, errorMessage } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Card } from "../components/ui.jsx";

export default function Account() {
  const { user } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      await api.post("/auth/change-password/", { old_password: oldPassword, new_password: newPassword });
      setMessage("Your password has been changed.");
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="narrow">
      <h1>My account</h1>
      <Card title="Profile">
        <dl className="dl">
          <dt>Name</dt>
          <dd>{user.full_name}</dd>
          <dt>Username</dt>
          <dd>{user.username}</dd>
          <dt>Role</dt>
          <dd>{user.role.toLowerCase()}</dd>
          {user.neptun_code && (
            <>
              <dt>Student code</dt>
              <dd>{user.neptun_code}</dd>
            </>
          )}
        </dl>
      </Card>
      <Card title="Change password">
        <form onSubmit={submit} className="form">
          <Alert>{error}</Alert>
          <Alert kind="success">{message}</Alert>
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </label>
          <button className="btn">Change password</button>
        </form>
      </Card>
    </div>
  );
}
