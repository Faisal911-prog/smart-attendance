import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import { homePathFor, useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import StudentHome from "./pages/StudentHome.jsx";
import Scan from "./pages/Scan.jsx";
import Courses from "./pages/Courses.jsx";
import CourseDetail from "./pages/CourseDetail.jsx";
import SessionLive from "./pages/SessionLive.jsx";
import AdminOverview from "./pages/AdminOverview.jsx";
import Users from "./pages/Users.jsx";
import Account from "./pages/Account.jsx";

const STAFF = ["ADMIN", "LECTURER"];

function Home() {
  const { user } = useAuth();
  return <Navigate to={homePathFor(user)} replace />;
}

function page(roles, element) {
  return (
    <ProtectedRoute roles={roles}>
      <Layout>{element}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={page(null, <Home />)} />
      <Route path="/student" element={page(["STUDENT"], <StudentHome />)} />
      <Route path="/scan" element={page(["STUDENT"], <Scan />)} />
      <Route path="/courses" element={page(STAFF, <Courses />)} />
      <Route path="/courses/:id" element={page(STAFF, <CourseDetail />)} />
      <Route path="/sessions/:id" element={page(STAFF, <SessionLive />)} />
      <Route path="/admin" element={page(["ADMIN"], <AdminOverview />)} />
      <Route path="/admin/users" element={page(["ADMIN"], <Users />)} />
      <Route path="/account" element={page(null, <Account />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
