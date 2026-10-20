/**
 * Búsqueda de productos para añadir a una lista. Recibe `listId` (y `listName`
 * para el título) por parámetros. La consulta se lanza con debounce contra
 * /search (búsqueda semántica); al tocar un producto se añade a la lista y se
 * invalidan las queries del detalle para que el total se actualice al volver.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Avatar,
  Button,
  Divider,
  IconButton,
  Searchbar,
  Snackbar,
  Text,
  useTheme,
} from 'react-native-paper';

import { RegionSelector } from '../../src/region/RegionSelector';
import { useRegion } from '../../src/region/RegionContext';
import { api } from '../../src/api/client';
import { contentMaxWidth } from '../../src/components/Screen';
import { ProductRow } from '../../src/components/ProductRow';
import type { Product } from '../../src/api/types';

const euros = (n: number | null) => (n == null ? '' : `${n.toFixed(2)} €`);

export default function SearchScreen() {
  const { listId, listName } = useLocalSearchParams<{
    listId: string;
    listName?: string;
  }>();
  const qc = useQueryClient();
  const {province,ready:regionReady} = useRegion();
  const theme = useTheme();
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [snack, setSnack] = useState<string | null>(null);

  // Debounce de 350 ms para no embeber en cada pulsación.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 350);
    return () => clearTimeout(t);
  }, [query]);

  const results = useQuery({
    queryKey: ['search', debounced, province],
    queryFn: () => api.search(debounced,20,province),
    enabled: regionReady && debounced.length > 0,
  });

  const add = useMutation({
    mutationFn: (product: Product) => api.addItem(listId, product.id, 1),
    onSuccess: (_data, product) => {
      qc.invalidateQueries({ queryKey: ['list', listId] });
      qc.invalidateQueries({ queryKey: ['list', listId, 'total'] });
      qc.invalidateQueries({ queryKey: ['lists'] });
      setSnack(`Añadido: ${product.name}`);
    },
    onError: () => setSnack('No se pudo añadir el producto'),
  });

  const subtitle = useMemo(
    () => (listName ? `Añadir a "${listName}"` : 'Añadir a la lista'),
    [listName],
  );

  const renderItem = ({ item }: { item: Product }) => (
    <ProductRow
      name={item.name}
      description={(
        <Text style={styles.itemDesc}>
          <Text style={[styles.price, { color: theme.colors.primary }]}>
            {euros(item.price)}
          </Text>
          {item.brand ? `  ·  ${item.brand}` : ''}
        </Text>
      )}
      left={(
        <View style={styles.avatar}>
          {item.image_url ? (
            <Avatar.Image size={44} source={{ uri: item.image_url }} />
          ) : (
            <Avatar.Icon size={44} icon="food" />
          )}
        </View>
      )}
      controls={(
        <IconButton
          icon="plus-circle"
          accessibilityLabel={`Añadir ${item.name}`}
          iconColor={theme.colors.primary}
          onPress={() => add.mutate(item)}
          disabled={add.isPending}
        />
      )}
    />
  );

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: subtitle }} />
      <View style={styles.searchWrap}>
        <RegionSelector/>
        <Searchbar
          placeholder="Buscar productos…"
          accessibilityLabel="Buscar productos"
          value={query}
          onChangeText={setQuery}
          autoFocus
          elevation={1}
        />
      </View>

      {debounced.length === 0 ? (
        <Text style={styles.hint}>Escribe para buscar (p. ej. «leche»).</Text>
      ) : results.isLoading ? (
        <ActivityIndicator style={styles.center} size="large" />
      ) : results.isError ? (
        <View style={styles.hint}>
          <Text accessibilityRole="alert">Error al buscar. Inténtalo de nuevo.</Text>
          <Button onPress={() => results.refetch()}>Reintentar búsqueda</Button>
        </View>
      ) : (
        <FlatList
          data={results.data ?? []}
          keyExtractor={(p) => p.id}
          renderItem={renderItem}
          ItemSeparatorComponent={Divider}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            <Text style={styles.hint}>Sin resultados para «{debounced}».</Text>
          }
        />
      )}

      <Snackbar
        visible={!!snack}
        onDismiss={() => setSnack(null)}
        duration={2500}
        action={{ label: 'Ver lista', onPress: () => router.back() }}
      >
        {snack}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  searchWrap: { ...contentMaxWidth, paddingVertical: 12 },
  listContent: { ...contentMaxWidth, paddingVertical: 4 },
  avatar: { justifyContent: 'center', marginLeft: 8 },
  itemDesc: { marginTop: 2, opacity: 0.8 },
  price: { fontWeight: '700' },
  center: { marginTop: 48 },
  hint: { textAlign: 'center', marginTop: 32, opacity: 0.6, paddingHorizontal: 24 },
});
