import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { login as apiLogin, endSession as apiEndSession } from "../api/client";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("session_token"));
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("session_id"));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (username, password) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiLogin(username, password);
      localStorage.setItem("session_token", data.session_token);
      localStorage.setItem("session_id", data.session_id);
      setToken(data.session_token);
      setSessionId(data.session_id);
      return true;
    } catch (err) {
      setError(err?.response?.data?.detail || "Login failed");
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      if (token) await apiEndSession();
    } catch {
      // best-effort; clear local state regardless
    }
    localStorage.removeItem("session_token");
    localStorage.removeItem("session_id");
    setToken(null);
    setSessionId(null);
  }, [token]);

  const value = useMemo(
    () => ({ token, sessionId, isAuthenticated: Boolean(token), login, logout, error, loading }),
    [token, sessionId, login, logout, error, loading]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
