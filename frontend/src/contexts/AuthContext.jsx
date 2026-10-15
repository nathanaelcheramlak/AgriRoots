import { createContext, useContext, useEffect, useMemo, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isHydrated, setIsHydrated] = useState(false);
  const [accessToken, setAccessToken] = useState(null);

  useEffect(() => {
    setAccessToken(localStorage.getItem("agriroots_access_token"));
    setIsHydrated(true);
  }, []);

  const value = useMemo(
    () => ({
      accessToken,
      isAuthenticated: Boolean(accessToken),
      isHydrated,
      setToken: (token) => {
        localStorage.setItem("agriroots_access_token", token);
        setAccessToken(token);
      },
      clearToken: () => {
        localStorage.removeItem("agriroots_access_token");
        setAccessToken(null);
      },
    }),
    [accessToken, isHydrated]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
