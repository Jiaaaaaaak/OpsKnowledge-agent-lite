import { useState, useEffect } from 'react';
import api from '../services/api';

export function useHealthCheck() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true);
        const response = await api.get('/health');
        setStatus(response);
        setError(null);
      } catch (err: any) {
        setError(err.message || '無法取得系統狀態');
        setStatus(null);
      } finally {
        setLoading(false);
      }
    };

    fetchHealth();
  }, []);

  return { status, loading, error };
}
