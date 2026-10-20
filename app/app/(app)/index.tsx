/**
 * Home autenticada: listas de la compra del usuario. Permite crear, renombrar y
 * borrar listas, abrir su detalle y cerrar sesión. Cada card tiene un menú (⋮)
 * con Renombrar / Borrar; el borrado pide confirmación.
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
  Icon,
  IconButton,
  Menu,
  Portal,
  Text,
  TextInput,
  useTheme,
} from 'react-native-paper';

import { api } from '../../src/api/client';
import { useAuth } from '../../src/auth/AuthContext';
import { contentMaxWidth } from '../../src/components/Screen';
import type { ShoppingListSummary } from '../../src/api/types';

const euros = (n: number) => `${n.toFixed(2)} €`;

const listSubtitle = (l: ShoppingListSummary) => {
  const productos = `${l.item_count} ${l.item_count === 1 ? 'producto' : 'productos'}`;
  return l.item_count > 0 ? `${productos} · ${euros(l.total)}` : 'Lista vacía';
};

type Dialog = { mode: 'create' | 'rename'; id?: string };

export default function HomeScreen() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const theme = useTheme();

  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [name, setName] = useState('');
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ShoppingListSummary | null>(null);

  const lists = useQuery({ queryKey: ['lists'], queryFn: api.getLists });
  const closeDialog = () => {
    setDialog(null);
    setName('');
  };

  const createList = useMutation({
    mutationFn: (n: string) => api.createList(n),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] });
      closeDialog();
    },
  });
  const renameList = useMutation({
    mutationFn: ({ id, name: n }: { id: string; name: string }) =>
      api.renameList(id, n),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] });
      closeDialog();
    },
  });
  const removeList = useMutation({
    mutationFn: (id: string) => api.deleteList(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] });
      setConfirmDelete(null);
    },
  });

  const openCreate = () => {
    setName('');
    setDialog({ mode: 'create' });
  };
  const openRename = (l: ShoppingListSummary) => {
    setName(l.name);
    setDialog({ mode: 'rename', id: l.id });
  };
  const submitDialog = () => {
    const n = name.trim();
    if (!n) return;
    if (dialog?.mode === 'rename' && dialog.id) {
      renameList.mutate({ id: dialog.id, name: n });
    } else {
      createList.mutate(n);
    }
  };

  const saving = createList.isPending || renameList.isPending;

  return (
    <View style={styles.container}>
      <Appbar.Header mode="small" elevated>
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
            <View style={styles.emptyBox}>
              <Icon source="playlist-plus" size={56} color="#9aa79a" />
              <Text variant="titleMedium" style={styles.emptyTitle}>
                Aún no tienes listas
              </Text>
              <Text style={styles.empty}>
                Crea tu primera lista con el botón +.
              </Text>
            </View>
          }
          renderItem={({ item }: { item: ShoppingListSummary }) => (
            <Card
              mode="contained"
              style={styles.card}
              onPress={() => router.push(`/(app)/list/${item.id}`)}
            >
              <Card.Title
                title={item.name}
                titleVariant="titleMedium"
                subtitle={listSubtitle(item)}
                left={(props) => <Icon {...props} source="cart-outline" />}
                right={() => (
                  <Menu
                    visible={menuFor === item.id}
                    onDismiss={() => setMenuFor(null)}
                    anchor={
                      <IconButton
                        icon="dots-vertical"
                        onPress={() => setMenuFor(item.id)}
                      />
                    }
                  >
                    <Menu.Item
                      leadingIcon="pencil-outline"
                      title="Renombrar"
                      onPress={() => {
                        setMenuFor(null);
                        openRename(item);
                      }}
                    />
                    <Menu.Item
                      leadingIcon="delete-outline"
                      title="Borrar"
                      onPress={() => {
                        setMenuFor(null);
                        setConfirmDelete(item);
                      }}
                    />
                  </Menu>
                )}
              />
            </Card>
          )}
        />
      )}

      <FAB icon="plus" style={styles.fab} onPress={openCreate} />

      <Portal>
        <Dialog visible={!!dialog} onDismiss={closeDialog}>
          <Dialog.Title>
            {dialog?.mode === 'rename' ? 'Renombrar lista' : 'Nueva lista'}
          </Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Nombre"
              value={name}
              onChangeText={setName}
              mode="outlined"
              autoFocus
              onSubmitEditing={submitDialog}
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={closeDialog}>Cancelar</Button>
            <Button
              onPress={submitDialog}
              disabled={!name.trim() || saving}
              loading={saving}
            >
              {dialog?.mode === 'rename' ? 'Guardar' : 'Crear'}
            </Button>
          </Dialog.Actions>
        </Dialog>

        <Dialog visible={!!confirmDelete} onDismiss={() => setConfirmDelete(null)}>
          <Dialog.Title>Borrar lista</Dialog.Title>
          <Dialog.Content>
            <Text>
              ¿Seguro que quieres borrar «{confirmDelete?.name}»? Se perderán sus
              productos.
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setConfirmDelete(null)}>Cancelar</Button>
            <Button
              textColor={theme.colors.error}
              loading={removeList.isPending}
              onPress={() => confirmDelete && removeList.mutate(confirmDelete.id)}
            >
              Borrar
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
  listContent: { ...contentMaxWidth, paddingVertical: 16, gap: 10 },
  card: { borderRadius: 14 },
  emptyBox: { alignItems: 'center', marginTop: 72, gap: 8, paddingHorizontal: 24 },
  emptyTitle: { marginTop: 4 },
  empty: { textAlign: 'center', opacity: 0.6 },
  fab: { position: 'absolute', right: 16, bottom: 16 },
});
