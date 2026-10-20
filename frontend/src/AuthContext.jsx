import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

function parseJwtExp(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch { return null; }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const saved = sessionStorage.getItem("medicore_auth");
    if (!saved) return null;
    const parsed = JSON.parse(saved);
    const exp = parseJwtExp(parsed.token);
    if (exp && Date.now() >= exp) {
      sessionStorage.removeItem("medicore_auth");
      return null;
    }
    return parsed;
  });

  const login = useCallback((token, role, username) => {
    const next = { token, role, username };
    setAuth(next);
    sessionStorage.setItem("medicore_auth", JSON.stringify(next));
  }, []);

  const logout = useCallback(() => {
    setAuth(null);
    sessionStorage.removeItem("medicore_auth");
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() { return useContext(AuthContext); }