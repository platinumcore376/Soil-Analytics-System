'use client';

/* Auth state for the PWA.
 *
 * A stored token is validated against /auth/me on startup rather than trusted: it may have
 * expired while the app was closed, and discovering that on the first data request would
 * dump the farmer onto an error screen instead of the sign-in form.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, getToken, logout as clearSession, me, type AuthUser } from './api';

interface AuthContextValue {
  user: AuthUser | null;
  /** False until the stored token has been checked — screens must wait on this. */
  ready: boolean;
  setUser: (user: AuthUser | null) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    me()
      .then(setUser)
      .catch((err) => {
        // request() already cleared the token on a 401; anything else (offline) leaves it
        // in place so the session survives a temporary loss of connectivity.
        if (!(err instanceof ApiError) || err.status !== 401) {
          /* keep the token */
        }
        setUser(null);
      })
      .finally(() => setReady(true));
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, ready, setUser, signOut }),
    [user, ready, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
