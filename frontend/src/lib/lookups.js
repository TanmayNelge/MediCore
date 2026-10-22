import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";

// Module-level cache keyed by path. Entries are evicted when the token
// changes (i.e. a different user logs in) so roles can't see each
// other's cached doctor/patient lists.
const cache = new Map();
let cachedToken = null;

function clearCacheIfTokenChanged(token) {
  if (cachedToken !== null && cachedToken !== token) {
    cache.clear();
  }
  cachedToken = token;
}

export function useLookup(path, { token, enabled = true, labelFn } = {}) {
  const [options, setOptions] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (!enabled || !token || !path) return;

    // Evict stale cache when a different user logs in
    clearCacheIfTokenChanged(token);

    if (cache.has(path)) {
      setOptions(cache.get(path));
      setUnavailable(false);
      return;
    }

    let cancelled = false;
    apiFetch(path, { token })
      .then((res) => {
        const rows = res?.results || [];
        const opts = rows.map((r) => {
          // Prefer the conventional PK field names; fall back to first value.
          const idValue =
            r.patient_id ?? r.doctor_id ?? r.medicine_id ??
            r.lab_test_id ?? r.room_bed_id ?? r.id ?? r.value ??
            Object.values(r)[0];
          return {
            value: String(idValue),
            label: labelFn ? labelFn(r) : String(Object.values(r)[0]),
            raw: r,
          };
        });
        cache.set(path, opts);
        if (!cancelled && mountedRef.current) setOptions(opts);
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) {
          setUnavailable(true);
          setOptions([]);
        }
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, token, enabled]);

  return { options, unavailable, loading: options === null && !unavailable };
}