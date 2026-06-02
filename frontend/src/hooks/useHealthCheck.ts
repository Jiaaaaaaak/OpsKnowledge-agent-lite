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
        // Assuming the health endpoint is /health or similar. 
        // Based on the prompt: { "status": "ok", "version": "0.1.0", "db": "connected", "chroma": "connected" }
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