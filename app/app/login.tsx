/**
 * Pantalla de login / registro. Alterna entre ambos modos. Si ya hay sesión,
 * redirige a la zona autenticada.
 */
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { Redirect, useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import {
  Button,
  HelperText,
  SegmentedButtons,
  Surface,
  Text,
  TextInput,
  useTheme,
} from 'react-native-paper';

import { ApiError } from '../src/api/client';
import { useAuth } from '../src/auth/AuthContext';
import { Screen } from '../src/components/Screen';

export default function LoginScreen() {
  const { user, login, register, sessionNotice } = useAuth();
  const router = useRouter();
  const theme = useTheme();

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Redirect href="/(app)" />;

  const onSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, displayName.trim() || undefined);
      }
      router.replace('/(app)');
    } catch (e) {
      if (e instanceof ApiError) setError(e.status >= 500
        ? 'El servidor no está disponible. Inténtalo de nuevo.' : e.message);
      else setError('No se pudo conectar con el servidor');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = email.length > 3 && password.length >= 6 && !submitting;

  return (
    <Screen center maxWidth={440}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.brand}>
          <View style={[styles.logo, { backgroundColor: theme.colors.primaryContainer }]}>
            <MaterialCommunityIcons
              name="cart-outline"
              size={34}
              color={theme.colors.primary}
            />
          </View>
          <Text variant="headlineMedium" style={styles.title}>
            Stalvi
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            Tu lista de la compra con el gasto estimado
          </Text>
        </View>

        <Surface style={styles.form} elevation={1}>
          <SegmentedButtons
            value={mode}
            onValueChange={(v) => {
              setMode(v as 'login' | 'register');
              setError(null);
            }}
            buttons={[
              { value: 'login', label: 'Entrar' },
              { value: 'register', label: 'Crear cuenta' },
            ]}
            style={styles.segment}
          />

          {mode === 'register' && (
            <TextInput
              label="Nombre (opcional)"
              accessibilityLabel="Nombre (opcional)"
              value={displayName}
              onChangeText={setDisplayName}
              mode="outlined"
              style={styles.input}
            />
          )}
          <TextInput
            label="Email"
            accessibilityLabel="Email"
            value={email}
            onChangeText={setEmail}
            mode="outlined"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            style={styles.input}
          />
          <TextInput
            label="Contraseña"
            accessibilityLabel="Contraseña"
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            value={password}
            onChangeText={setPassword}
            mode="outlined"
            secureTextEntry
            style={styles.input}
          />

          {sessionNotice && <Text accessibilityRole="alert">{sessionNotice}</Text>}
          <HelperText type="error" visible={!!error} accessibilityRole={error ? 'alert' : undefined}>
            {error}
          </HelperText>

          <Button
            mode="contained"
            onPress={onSubmit}
            loading={submitting}
            disabled={!canSubmit}
            style={styles.button}
          >
            {mode === 'login' ? 'Entrar' : 'Crear cuenta'}
          </Button>
        </Surface>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brand: { alignItems: 'center', marginBottom: 24 },
  logo: {
    width: 64,
    height: 64,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  form: { padding: 20, borderRadius: 16, gap: 4 },
  title: { textAlign: 'center', fontWeight: 'bold' },
  subtitle: { textAlign: 'center', marginTop: 4, opacity: 0.7 },
  segment: { marginBottom: 16 },
  input: { marginBottom: 8 },
  button: { marginTop: 12 },
});
