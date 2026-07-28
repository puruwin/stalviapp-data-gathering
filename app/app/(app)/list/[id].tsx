/**
 * Detalle de una lista: items con cantidad ajustable, marcar comprado, quitar,
 * y el GASTO TOTAL en vivo (se recalcula al cambiar cantidades). El botón "+"
 * abre la búsqueda de productos para añadir a esta lista.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Checkbox,
  Divider,
  FAB,
  IconButton,
  List,
  Surface,
  Text,
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

  const list = useQuery({ queryKey: ['list', id], queryFn: () => api.getList(id) });
  const total = useQuery({
    queryKey: ['list', id, 'total'],
    queryFn: () => api.listTotal(id),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['list', id] });
    qc.invalidateQueries({ queryKey: ['list', id, 'total'] });
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
    onSuccess: refresh,
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

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: list.data.name }} />
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
