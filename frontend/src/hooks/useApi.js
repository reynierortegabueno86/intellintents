import { useState, useEffect, useCallback } from 'react';

export function useApi(apiFn, deps = [], immediate = true) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFn(...args);
      setData(result);
      return result;
    } catch (err) {
      setError(err.message || 'An error occurred');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFn]);

  useEffect(() => {
    if (immediate) {
      execute().catch(() => {});
    }
  }, deps);

  return { data, loading, error, execute, setData };
}

export function useLazyApi(apiFn) {
  return useApi(apiFn, [], false);
}
