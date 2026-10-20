/**
 * Layout de la zona autenticada. Si no hay sesión, redirige a /login.
 * Aquí cuelgan las pantallas protegidas (home, y en el tramo B búsqueda y
 * detalle de lista).
 */
import { Redirect, Stack } from 'expo-router';

import { useAuth } from '../../src/auth/AuthContext';
import { RegionProvider } from '../../src/region/RegionContext';
import { theme } from '../../src/theme';

export default function AppLayout() {
  const { user } = useAuth();

  if (!user) return <Redirect href="/login" />;

  return (
    <RegionProvider key={user.id} userId={user.id}><Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.primary },
        headerTintColor: '#fff',
        headerTitleStyle: { fontWeight: '600' },
        headerShadowVisible: false,
        contentStyle: { backgroundColor: theme.colors.background },
      }}
    >
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="backoffice" options={{ headerShown: false, title: 'Catálogo de productos' }} />
    </Stack></RegionProvider>
  );
}
