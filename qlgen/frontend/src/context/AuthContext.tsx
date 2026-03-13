import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { refreshToken as refreshTokenApi, logout as logoutApi, type AuthUser } from '../api/authApi';

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => Promise<void>;
  getAccessToken: () => string | null;
}

const AuthCtx = createContext<AuthContextValue>({
  user: null,
  accessToken: null,
  isLoading: true,
  isAuthenticated: false,
  login: () => {},
  logout: async () => {},
  getAccessToken: () => null,
});

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthCtx);
}

// Module-level token reference for use by interceptors (avoids stale closures)
let _accessToken: string | null = null;

export function getAccessToken(): string | null {  // eslint-disable-line react-refresh/only-export-components
  return _accessToken;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshAttempted = useRef(false);

  const login = useCallback((token: string, userData: AuthUser) => {
    _accessToken = token;
    setAccessToken(token);
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Ignore errors during logout
    }
    _accessToken = null;
    setAccessToken(null);
    setUser(null);
  }, []);

  // Try silent refresh on mount
  useEffect(() => {
    if (refreshAttempted.current) return;
    refreshAttempted.current = true;

    const tryRefresh = async () => {
      try {
        const resp = await refreshTokenApi();
        const { access_token, user: userData } = resp.data;
        _accessToken = access_token;
        setAccessToken(access_token);
        setUser(userData);
      } catch {
        // No valid refresh token — user needs to log in
      } finally {
        setIsLoading(false);
      }
    };

    tryRefresh();
  }, []);

  const getToken = useCallback(() => _accessToken, []);

  const value: AuthContextValue = {
    user,
    accessToken,
    isLoading,
    isAuthenticated: !!accessToken && !!user,
    login,
    logout,
    getAccessToken: getToken,
  };

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
};
