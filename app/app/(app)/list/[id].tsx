/**
 * Detalle de una lista: items con cantidad ajustable, marcar comprado, quitar,
 * y el GASTO TOTAL en vivo (se recalcula al cambiar cantidades).
 *
 * Tramo B añadirá aquí la búsqueda de productos para añadir a la lista; de
 * momento se gestionan los items ya presentes.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, useLocalSearchParams } from 'expo-router';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Checkbox,
  Divider,
  IconButton,
  List,
  Surface,
  Text,
} from 'react-native-paper';

import { api } from '../../../src/api/client';
import type { ListItem } from '../../../src/api/types';

const euros = (n: number | null | undefined) =>
  n == null ? '—' : `${n.toFixed(2)} €`;

export default function ListDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const qc = useQueryClient();

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
      description={`${euros(item.price)} · ${item.quantity} ud`}
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
            disabled={item.quantity <= 1}
            onPress={() =>
              setQty.mutate({ itemId: item.id, quantity: item.quantity - 1 })
            }
          />
          <Text>{item.quantity}</Text>
          <IconButton
            icon="plus"
            size={18}
            onPress={() =>
              setQty.mutate({ itemId: item.id, quantity: item.quantity + 1 })
            }
          />
          <IconButton icon="delete" size={18} onPress={() => remove.mutate(item.id)} />
        </View>
      )}
    />
  );

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: list.data.name }} />
      <FlatList
        data={list.data.items}
        keyExtractor={(i) => i.id}
        renderItem={renderItem}
        ItemSeparatorComponent={Divider}
        ListEmptyComponent={
          <Text style={styles.empty}>
            Lista vacía. La búsqueda para añadir productos llega en el tramo B.
          </Text>
        }
      />
      <Surface style={styles.totalBar} elevation={4}>
        <Text variant="titleMedium">Total estimado</Text>
        <Text variant="titleLarge" style={styles.totalValue}>
          {total.isLoading ? '…' : euros(total.data?.total)}
        </Text>
      </Surface>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  qtyRow: { flexDirection: 'row', alignItems: 'center' },
  empty: { textAlign: 'center', marginTop: 48, opacity: 0.6, paddingHorizontal: 24 },
  totalBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  totalValue: { fontWeight: 'bold' },
});
