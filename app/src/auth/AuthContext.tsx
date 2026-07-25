/**
 * Estado de sesión: token JWT + usuario, persistidos con AsyncStorage.
 * Al arrancar rehidrata la sesión; login/register la guardan; logout la limpia.
 * El token se inyecta en el cliente HTTP (setAuthToken) para el header Bearer.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, setAuthToken } from '../api/client';
import type { User } from '../api/types';

const STORAGE_KEY = 'stalvi.session';

type Session = { token: string; user: User };

type AuthContextValue = {
  user: User | null;
  loading: boolean; // true mientras rehidrata la sesión al arrancar
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Rehidrata al montar.
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const session: Session = JSON.parse(raw);
          setAuthToken(session.token);
          setUser(session.user);
        }
      } catch {
        // sesión corrupta: se ignora y se pedirá login
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const persist = useCallback(async (session: Session) => {
    setAuthToken(session.token);
    setUser(session.user);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }, []);

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

  const logout = useCallback(async () => {
    setAuthToken(null);
    setUser(null);
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  return ctx;
}
