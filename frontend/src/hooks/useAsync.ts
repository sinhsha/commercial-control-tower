import { useState, useEffect, useCallback } from 'react';
import type { ApiState } from '@/types/api';

/**
 * Generic async data-fetching hook with loading / error / data state.
 * Re-fetches whenever `deps` change.
 */
export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): ApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: 'loading' });

  const execute = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const data = await fetcher();
      setState({ status: 'success', data });
    } catch (err) {
      setState({
        status: 'error',
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void execute();
  }, [execute]);

  return { ...state, refetch: execute };
}
