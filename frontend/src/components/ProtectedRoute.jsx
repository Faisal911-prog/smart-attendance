import { Navigate, useLocation } from "react-router-dom";
import { homePathFor, useAuth } from "../auth.jsx";

// Redirects to the login page when nobody is signed in, and to the user's own
// home page when the role is not allowed to see the route. (The server enforces
// the same rules; this only keeps the interface tidy.)
export default function ProtectedRoute({ roles, children }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={homePathFor(user)} replace />;
  }
  return children;
}
