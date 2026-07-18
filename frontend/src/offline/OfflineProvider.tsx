import { createContext, useContext, useEffect, useMemo, useState } from "react";

type OfflineState = { offline: boolean; stale: boolean };
const OfflineContext = createContext<OfflineState>({ offline: false, stale: false });

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [stale, setStale] = useState(false);
  useEffect(() => {
    const online = () => { setOffline(false); setStale(false); };
    const offlineEvent = () => setOffline(true);
    const fallback = () => { setOffline(true); setStale(true); };
    window.addEventListener("online", online);
    window.addEventListener("offline", offlineEvent);
    window.addEventListener("hermes-cache-fallback", fallback);
    return () => { window.removeEventListener("online", online); window.removeEventListener("offline", offlineEvent); window.removeEventListener("hermes-cache-fallback", fallback); };
  }, []);
  useEffect(() => { document.body.dataset.offline = String(offline); }, [offline]);
  const value = useMemo(() => ({ offline, stale }), [offline, stale]);
  return <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useOffline() { return useContext(OfflineContext); }
