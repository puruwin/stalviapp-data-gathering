/**
 * Detalle de una lista: items con cantidad ajustable, marcar comprado, quitar,
 * y el GASTO TOTAL en vivo (se recalcula al cambiar cantidades). El botón "+"
 * abre la búsqueda de productos para añadir a esta lista.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Button,
  Checkbox,
  Dialog,
  Divider,
  FAB,
  IconButton,
  List,
  Menu,
  Portal,
  Surface,
  Text,
  TextInput,
  useTheme,
} from 'react-native-paper';

import { api } from '../../../src/api/client';
import { contentMaxWidth } from '../../../src/components/Screen';
import type { ListItem } from '../../../src/api/types';

const euros = (n: number | null | undefined) =>
  n == null ? '—' : `${n.toFixed(2)} €`;

export default function ListDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const qc = useQueryClient();
  const router = useRouter();
  const theme = useTheme();

  const [menuOpen, setMenuOpen] = useState(false);
  const [renameName, setRenameName] = useState<string | null>(null);
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const list = useQuery({ queryKey: ['list', id], queryFn: () => api.getList(id) });
  const total = useQuery({
    queryKey: ['list', id, 'total'],
    queryFn: () => api.listTotal(id),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['list', id] });
    qc.invalidateQueries({ queryKey: ['list', id, 'total'] });
  };
  // Además del detalle, refresca el índice (nº items / total de la card).
  const refreshAll = () => {
    refresh();
    qc.invalidateQueries({ queryKey: ['lists'] });
  };

  const setQty = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: string; quantity: number }) =>
      api.updateItem(id, itemId, { quantity }),
    onSuccess: refresh,
  });
  const toggle = useMutation({
    mutationFn: ({ itemId, checked }: { itemId: string; checked: boolean }) =>
      api.updateItem(id, itemId, { checked }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (itemId: string) => api.deleteItem(id, itemId),
    onSuccess: refreshAll,
  });
  const rename = useMutation({
    mutationFn: (name: string) => api.renameList(id, name),
    onSuccess: () => {
      refreshAll();
      setRenameName(null);
    },
  });
  const emptyList = useMutation({
    mutationFn: () => api.emptyList(id),
    onSuccess: () => {
      refreshAll();
      setConfirmEmpty(false);
    },
  });
  const removeList = useMutation({
    mutationFn: () => api.deleteList(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lists'] });
      setConfirmDelete(false);
      router.back();
    },
  });

  if (list.isLoading) {
    return <ActivityIndicator style={styles.center} size="large" />;
  }
  if (list.isError || !list.data) {
    return (
      <View style={styles.center}>
        <Text>No se pudo cargar la lista.</Text>
      </View>
    );
  }

  const renderItem = ({ item }: { item: ListItem }) => (
    <List.Item
      title={item.name}
      titleNumberOfLines={2}
      description={() => (
        <Text style={styles.itemDesc}>
          <Text style={[styles.price, { color: theme.colors.primary }]}>
            {euros(item.price)}
          </Text>
          {`  ·  ${item.quantity} ud`}
        </Text>
      )}
      style={[item.checked && styles.itemChecked]}
      left={() => (
        <Checkbox
          status={item.checked ? 'checked' : 'unchecked'}
          onPress={() => toggle.mutate({ itemId: item.id, checked: !item.checked })}
        />
      )}
      right={() => (
        <View style={styles.qtyRow}>
          <IconButton
            icon="minus"
            size={18}
            mode="outlined"
            disabled={item.quantity <= 1}
            onPress={() =>
              setQty.mutate({ itemId: item.id, quantity: item.quantity - 1 })
            }
          />
          <Text style={styles.qty}>{item.quantity}</Text>
          <IconButton
            icon="plus"
            size={18}
            mode="outlined"
            onPress={() =>
              setQty.mutate({ itemId: item.id, quantity: item.quantity + 1 })
            }
          />
          <IconButton icon="delete-outline" size={18} onPress={() => remove.mutate(item.id)} />
        </View>
      )}
    />
  );

  const goToSearch = () =>
    router.push({
      pathname: '/(app)/search',
      params: { listId: id, listName: list.data.name },
    });

  const isEmpty = list.data.items.length === 0;

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          title: list.data.name,
          headerRight: () => (
            <Menu
              visible={menuOpen}
              onDismiss={() => setMenuOpen(false)}
              anchor={
                <IconButton
                  icon="dots-vertical"
                  iconColor="#fff"
                  onPress={() => setMenuOpen(true)}
                />
              }
            >
              <Menu.Item
                leadingIcon="pencil-outline"
                title="Renombrar"
                onPress={() => {
                  setMenuOpen(false);
                  setRenameName(list.data.name);
                }}
              />
              <Menu.Item
                leadingIcon="notification-clear-all"
                title="Vaciar lista"
                disabled={isEmpty}
                onPress={() => {
                  setMenuOpen(false);
                  setConfirmEmpty(true);
                }}
              />
              <Divider />
              <Menu.Item
                leadingIcon="delete-outline"
                title="Borrar lista"
                onPress={() => {
                  setMenuOpen(false);
                  setConfirmDelete(true);
                }}
              />
            </Menu>
          ),
        }}
      />
      <FlatList
        data={list.data.items}
        keyExtractor={(i) => i.id}
        renderItem={renderItem}
        ItemSeparatorComponent={Divider}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <Text style={styles.empty}>
            Lista vacía. Toca «Añadir productos» para buscar y añadir.
          </Text>
        }
      />
      <FAB
        icon="magnify"
        label="Añadir productos"
        style={styles.fab}
        onPress={goToSearch}
      />
      <Surface
        style={[styles.totalBar, { borderTopColor: theme.colors.outlineVariant }]}
        elevation={2}
      >
        <Text variant="titleMedium">Total estimado</Text>
        <Text
          variant="headlineSmall"
          style={[styles.totalValue, { color: theme.colors.primary }]}
        >
          {total.isLoading ? '…' : euros(total.data?.total)}
        </Text>
      </Surface>

      <Portal>
        <Dialog visible={renameName !== null} onDismiss={() => setRenameName(null)}>
          <Dialog.Title>Renombrar lista</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Nombre"
              value={renameName ?? ''}
              onChangeText={setRenameName}
              mode="outlined"
              autoFocus
              onSubmitEditing={() => {
                const n = renameName?.trim();
                if (n) rename.mutate(n);
              }}
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setRenameName(null)}>Cancelar</Button>
            <Button
              disabled={!renameName?.trim() || rename.isPending}
              loading={rename.isPending}
              onPress={() => rename.mutate((renameName ?? '').trim())}
            >
              Guardar
            </Button>
          </Dialog.Actions>
        </Dialog>

        <Dialog visible={confirmEmpty} onDismiss={() => setConfirmEmpty(false)}>
          <Dialog.Title>Vaciar lista</Dialog.Title>
          <Dialog.Content>
            <Text>Se quitarán todos los productos de «{list.data.name}».</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setConfirmEmpty(false)}>Cancelar</Button>
            <Button
              loading={emptyList.isPending}
              onPress={() => emptyList.mutate()}
            >
              Vaciar
            </Button>
          </Dialog.Actions>
        </Dialog>

        <Dialog visible={confirmDelete} onDismiss={() => setConfirmDelete(false)}>
          <Dialog.Title>Borrar lista</Dialog.Title>
          <Dialog.Content>
            <Text>
              ¿Seguro que quieres borrar «{list.data.name}»? Se perderán sus
              productos.
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setConfirmDelete(false)}>Cancelar</Button>
            <Button
              textColor={theme.colors.error}
              loading={removeList.isPending}
              onPress={() => removeList.mutate()}
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  qtyRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  qty: { minWidth: 20, textAlign: 'center', fontVariant: ['tabular-nums'] },
  itemDesc: { marginTop: 2, opacity: 0.8 },
  price: { fontWeight: '700' },
  itemChecked: { opacity: 0.55 },
  empty: { textAlign: 'center', marginTop: 48, opacity: 0.6, paddingHorizontal: 24 },
  listContent: { ...contentMaxWidth, paddingVertical: 8, paddingBottom: 96 },
  fab: { position: 'absolute', right: 16, bottom: 80 },
  totalBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  totalValue: { fontWeight: 'bold' },
});
