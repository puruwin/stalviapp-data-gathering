/**
 * Home autenticada: listas de la compra del usuario. Permite crear listas y
 * cerrar sesión. La búsqueda de productos y el detalle con gasto total llegan
 * en el tramo B de F4.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Appbar,
  Button,
  Card,
  Dialog,
  FAB,
  Portal,
  Text,
  TextInput,
} from 'react-native-paper';

import { api } from '../../src/api/client';
import { useAuth } from '../../src/auth/AuthContext';
import type { ShoppingList } from '../../src/api/types';

export default function HomeScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState('');

  const lists = useQuery({ queryKey: ['lists'], queryFn: api.getLists });

  const createList = useMutation({
    mutationFn: (name: string) => api.createList(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] });
      setDialogOpen(false);
      setNewName('');
    },
  });

  return (
    <View style={styles.container}>
      <Appbar.Header>
        <Appbar.Content
          title="Mis listas"
          subtitle={user?.display_name ?? user?.email}
        />
        <Appbar.Action icon="logout" onPress={logout} />
      </Appbar.Header>

      {lists.isLoading ? (
        <ActivityIndicator style={styles.center} size="large" />
      ) : lists.isError ? (
        <View style={styles.center}>
          <Text>No se pudieron cargar las listas.</Text>
          <Button onPress={() => lists.refetch()}>Reintentar</Button>
        </View>
      ) : (
        <FlatList
          data={lists.data ?? []}
          keyExtractor={(l) => l.id}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            <Text style={styles.empty}>
              Aún no tienes listas. Crea una con el botón +.
            </Text>
          }
          renderItem={({ item }: { item: ShoppingList }) => (
            <Card style={styles.card} onPress={() => router.push(`/(app)/list/${item.id}`)}>
              <Card.Title title={item.name} />
            </Card>
          )}
        />
      )}

      <FAB icon="plus" style={styles.fab} onPress={() => setDialogOpen(true)} />

      <Portal>
        <Dialog visible={dialogOpen} onDismiss={() => setDialogOpen(false)}>
          <Dialog.Title>Nueva lista</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Nombre"
              value={newName}
              onChangeText={setNewName}
              mode="outlined"
              autoFocus
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDialogOpen(false)}>Cancelar</Button>
            <Button
              onPress={() => createList.mutate(newName.trim())}
              disabled={!newName.trim() || createList.isPending}
              loading={createList.isPending}
            >
              Crear
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 8 },
  listContent: { padding: 12, gap: 8 },
  card: { marginBottom: 4 },
  empty: { textAlign: 'center', marginTop: 48, opacity: 0.6 },
  fab: { position: 'absolute', right: 16, bottom: 16 },
});
