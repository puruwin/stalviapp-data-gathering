/**
 * Estado de sesión: token JWT + usuario, persistidos con AsyncStorage.
 * Al arrancar rehidrata la sesión; login/register la guardan; logout la limpia.
 * El token se inyecta en el cliente HTTP (setAuthToken) para el header Bearer.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, ApiError, setAuthToken, setUnauthorizedHandler } from '../api/client';
import type { User } from '../api/types';

const STORAGE_KEY = 'stalvi.session';

type Session = { token: string; user: User };

type AuthContextValue = {
  user: User | null;
  loading: boolean; // true mientras rehidrata la sesión al arrancar
  sessionNotice: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  const clearSession = useCallback(async (expired = false) => {
    setAuthToken(null);
    setUser(null);
    setSessionNotice(expired ? 'Tu sesión ha caducado. Vuelve a entrar.' : null);
    // Cancelar también impide que respuestas pendientes repueblen la caché.
    void qc.cancelQueries();
    qc.clear();
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, [qc]);

  useEffect(() => {
    setUnauthorizedHandler(() => { void clearSession(true).catch(() => {}); });
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Rehidrata al montar.
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const session: Session = JSON.parse(raw);
          if (!session.token || typeof session.token !== 'string' ||
              typeof session.user?.id !== 'string' || typeof session.user?.email !== 'string') {
            throw new Error('Sesión guardada inválida');
          }
          setAuthToken(session.token);
          setUser(session.user);
          try {
            const profile = await api.me();
            setUser(profile);
          } catch (e) {
            // Una caída de red no equivale a una sesión caducada.
            if (e instanceof ApiError && e.status === 401) await clearSession(true);
          }
        }
      } catch {
        await clearSession().catch(() => {});
      } finally {
        setLoading(false);
      }
    })();
  }, [clearSession]);

  const persist = useCallback(async (session: Session) => {
    void qc.cancelQueries();
    qc.clear();
    setAuthToken(session.token);
    setUser(session.user);
    setSessionNotice(null);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }, [qc]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.login(email, password);
      await persist(res);
    },
    [persist],
  );

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const res = await api.register(email, password, displayName);
      await persist(res);
    },
    [persist],
  );

  const logout = useCallback(() => clearSession(), [clearSession]);

  const value = useMemo(
    () => ({ user, loading, sessionNotice, login, register, logout }),
    [user, loading, sessionNotice, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  return ctx;
}
