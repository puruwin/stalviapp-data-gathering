import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

type Region = { province: string; ready: boolean; setProvince: (code: string) => void; error: string };
const RegionContext = createContext<Region | null>(null);

/** Provincia compartida entre catálogo y búsqueda, persistida por cuenta. */
export function RegionProvider({ userId, children }: { userId: string; children: ReactNode }) {
  const key = `stalvi.province.${userId}`;
  const [province, updateProvince] = useState('');
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(Promise.resolve());
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(key).then(value => {
      if (!cancelled) { updateProvince(value && /^\d{2}$/.test(value) ? value : ''); setReady(true); }
    }).catch(() => { if (!cancelled) { setReady(true); setError('No se pudo recuperar la provincia guardada.'); } });
    return () => { cancelled = true; };
  }, [key]);
  function setProvince(code: string) {
    if (!ready || !/^(\d{2})?$/.test(code)) return;
    updateProvince(code);
    pending.current = pending.current.catch(() => {}).then(() => AsyncStorage.setItem(key, code))
      .catch(() => setError('No se pudo guardar la provincia en este dispositivo.'));
  }
  return <RegionContext.Provider value={{ province, ready, setProvince, error }}>{children}</RegionContext.Provider>;
}

export function useRegion() {
  const value = useContext(RegionContext);
  if (!value) throw new Error('Falta RegionProvider');
  return value;
}
