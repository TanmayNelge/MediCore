import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";

/**
 * Fetches data on mount and whenever `fetcher` changes (stable identity via
 * useCallback at call site).  Pass a new `fetcher` reference to re-fetch.
 *
 * FIX: the original code spread a variable-length `deps` array directly into
 * useCallback's dependency array, which violates React's rules of hooks
 * (hooks must have a fixed number of deps across renders).  The correct
 * pattern is: let the caller control re-fetching by passing a new `fetcher`
 * reference — which is exactly what every call-site does with useCallback
 * and [active.path] etc.  Removed the rogue deps spread.
 */
export function useApi(fetcher) {
  const { auth, logout } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!!fetcher);
  const [error, setError] = useState(null);
  const reqId = useRef(0);

  const run = useCallback(async () => {
    if (!fetcher) return;
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetcher(auth.token);
      if (id === reqId.current) setData(res);
    } catch (e) {
      if (id === reqId.current) {
        if (e.status === 401) { logout(); return; }
        setError(e.message);
      }
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  // fetcher is the only dep: callers pass a stable useCallback ref;
  // changing fetcher (new identity) triggers a re-fetch automatically.
  // auth.token is intentionally omitted — the fetcher closure captures
  // the token at creation time from the call-site's own useCallback.
  }, [fetcher]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { run(); }, [run]);
  return { data, loading, error, reload: run };
}