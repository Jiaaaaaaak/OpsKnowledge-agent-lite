import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { administrator, loading } = useAuth();

  // bootstrap 尚未完成前先等待，避免已登入者在 cookie 驗證回來前被閃導到登入頁。
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        載入中…
      </div>
    );
  }

  if (!administrator) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
