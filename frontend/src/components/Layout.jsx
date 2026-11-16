import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const NAV = {
  STUDENT: [
    ["/student", "My attendance"],
    ["/scan", "Check in"],
  ],
  LECTURER: [["/courses", "Courses"]],
  ADMIN: [
    ["/admin", "Overview"],
    ["/courses", "Courses"],
    ["/admin/users", "Users"],
  ],
};

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              ✓
            </span>
            Smart Attendance
          </div>
          <nav className="nav" aria-label="Main">
            {(NAV[user.role] || []).map(([to, label]) => (
              <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? "active" : "")}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="user">
            <NavLink to="/account" className="user-name">
              {user.full_name}
            </NavLink>
            <span className={`badge role-${user.role.toLowerCase()}`}>{user.role.toLowerCase()}</span>
            <button className="btn btn-ghost btn-sm" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
