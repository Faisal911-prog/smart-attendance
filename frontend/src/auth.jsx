import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, request, tokenStore } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (tokenStore.access ? tokenStore.user : null));

  // Validate the stored session once when the app starts.
  useEffect(() => {
    if (!tokenStore.access) return;
    api
      .get("/auth/me/")
      .then((me) => {
        tokenStore.setUser(me);
        setUser(me);
      })
      .catch(() => {});
  }, []);

  // The API layer fires this event when a refresh token is no longer valid.
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("sas:logout", onLogout);
    return () => window.removeEventListener("sas:logout", onLogout);
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await request("/auth/login/", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
    tokenStore.setTokens(data.access, data.refresh);
    tokenStore.setUser(data.user);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStore.refresh;
    try {
      if (refresh) await api.post("/auth/logout/", { refresh });
    } catch {
      /* the token is discarded locally in any case */
    }
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function homePathFor(user) {
  if (!user) return "/login";
  if (user.role === "STUDENT") return "/student";
  if (user.role === "ADMIN") return "/admin";
  return "/courses";
}
