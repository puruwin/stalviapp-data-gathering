/**
 * Layout de la zona autenticada. Si no hay sesión, redirige a /login.
 * Aquí cuelgan las pantallas protegidas (home, y en el tramo B búsqueda y
 * detalle de lista).
 */
import { Redirect, Stack } from 'expo-router';

import { useAuth } from '../../src/auth/AuthContext';
import { theme } from '../../src/theme';

export default function AppLayout() {
  const { user } = useAuth();

  if (!user) return <Redirect href="/login" />;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.primary },
        headerTintColor: '#fff',
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Mis listas' }} />
    </Stack>
  );
}
