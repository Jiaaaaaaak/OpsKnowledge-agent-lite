import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  getCurrentAdministrator,
  login as apiLogin,
  logout as apiLogout,
  Administrator,
} from '../services/api';

interface AuthContextType {
  administrator: Administrator | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [administrator, setAdministrator] = useState<Administrator | null>(null);
  // 初始 bootstrap 期間為 true：ProtectedRoute 必須等 /auth/me 有結果再決定導向，
  // 否則已登入者會在 cookie 驗證完成前被誤導到登入頁。
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentAdministrator()
      .then((admin) => setAdministrator(admin))
      .catch(() => setAdministrator(null)) // 401 等同未登入，靜默處理
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const admin = await apiLogin(username, password);
    setAdministrator(admin);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setAdministrator(null);
  }, []);

  return (
    <AuthContext.Provider value={{ administrator, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
