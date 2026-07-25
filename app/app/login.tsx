/**
 * Pantalla de login / registro. Alterna entre ambos modos. Si ya hay sesión,
 * redirige a la zona autenticada.
 */
import { Redirect, useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import {
  Button,
  HelperText,
  SegmentedButtons,
  Text,
  TextInput,
} from 'react-native-paper';

import { ApiError } from '../src/api/client';
import { useAuth } from '../src/auth/AuthContext';

export default function LoginScreen() {
  const { user, login, register } = useAuth();
  const router = useRouter();

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
      if (e instanceof ApiError) setError(e.message);
      else setError('No se pudo conectar con el servidor');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = email.length > 3 && password.length >= 6 && !submitting;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.form}>
        <Text variant="headlineMedium" style={styles.title}>
          Stalvi
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Tu lista de la compra con el gasto estimado
        </Text>

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
            value={displayName}
            onChangeText={setDisplayName}
            mode="outlined"
            style={styles.input}
          />
        )}
        <TextInput
          label="Email"
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
          value={password}
          onChangeText={setPassword}
          mode="outlined"
          secureTextEntry
          style={styles.input}
        />

        <HelperText type="error" visible={!!error}>
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
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center' },
  form: { padding: 24, maxWidth: 440, width: '100%', alignSelf: 'center' },
  title: { textAlign: 'center', fontWeight: 'bold' },
  subtitle: { textAlign: 'center', marginBottom: 24, opacity: 0.7 },
  segment: { marginBottom: 16 },
  input: { marginBottom: 8 },
  button: { marginTop: 8 },
});
