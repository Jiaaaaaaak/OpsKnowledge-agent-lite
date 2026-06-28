import { FormEvent, useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';
import { getAuthStatus } from '../services/api';

export default function LoginPage() {
  const { administrator, loading, bootstrap, login } = useAuth();
  const navigate = useNavigate();
  const [bootstrapRequired, setBootstrapRequired] = useState(false);
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const status = await getAuthStatus();
        // 首次安裝（尚無管理員）→ 切換成「建立管理員」模式。
        if (active) setBootstrapRequired(!!status?.bootstrap_required);
      } catch {
        // 取不到狀態時預設為一般登入模式。
      } finally {
        // 等狀態確定後才渲染表單，避免登入↔建立管理員的閃動，也讓按鈕文字一次到位。
        if (active) setStatusLoaded(true);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // 已登入者不該停留在登入頁。
  if (!loading && administrator) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (bootstrapRequired) {
        await bootstrap(username, password);
      } else {
        await login(username, password);
      }
      navigate('/', { replace: true });
    } catch {
      setError(
        bootstrapRequired
          ? '建立管理員失敗，請確認密碼至少 8 碼'
          // 通用錯誤：後端對未知帳號與錯誤密碼回同一組 401，前端也不細分原因。
          : '帳號或密碼錯誤',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const heading = bootstrapRequired ? '建立 OpsWeave 管理員' : '登入 OpsWeave';
  const submitLabel = bootstrapRequired ? '建立管理員' : '登入';

  // 狀態未定前先不渲染表單，確保標題/按鈕一次顯示最終模式（無閃動、e2e 可穩定定位）。
  if (!statusLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
        載入中…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-slate-900">{heading}</h1>
        {bootstrapRequired && (
          <p className="mb-4 text-center text-sm text-slate-500">
            尚未建立管理員，請設定第一組管理員帳號（密碼至少 8 碼）。
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="mb-1 block text-sm font-medium text-slate-700">
              使用者名稱
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
              密碼
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={bootstrapRequired ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {error && (
            <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-error">
              {error}
            </div>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={submitting}>
            {submitting ? '處理中…' : submitLabel}
          </Button>
        </form>
      </div>
    </div>
  );
}
