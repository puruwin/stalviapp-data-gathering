/**
 * Configuración de la app. La URL del API se toma de la variable de entorno
 * pública de Expo `EXPO_PUBLIC_API_URL` (definir en app/.env), con un valor por
 * defecto para desarrollo web.
 *
 * Notas para móvil:
 *  - Emulador Android: usar http://10.0.2.2:8000 (alias del host).
 *  - Dispositivo físico: usar la IP LAN del ordenador (p.ej. http://192.168.1.X:8000).
 */
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
