import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getSession, login, logout, type Session } from "../api/auth";
import { ApiError, setCsrfToken } from "../api/client";
import { clearBusinessCache } from "../offline/cache";

type SessionState = {
  session: Session | null;
  isLoading: boolean;
  error: string | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void getSession(controller.signal)
      .then((restored) => {
        setCsrfToken(restored.csrf_token ?? null);
        setSession(restored);
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof ApiError && reason.status === 401) && !controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "无法检查登录状态");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const result = await login(username, password);
    setCsrfToken(result.csrf_token);
    setSession({ actor_type: "user", actor_id: result.username });
    setError(null);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      setCsrfToken(null);
      setSession(null);
      queryClient.clear();
      await clearBusinessCache();
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ session, isLoading, error, signIn, signOut }),
    [session, isLoading, error, signIn, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

// The provider and hook intentionally share this small session module.
// eslint-disable-next-line react-refresh/only-export-components
export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
