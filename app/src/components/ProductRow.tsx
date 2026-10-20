import type { ReactNode } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { Text } from 'react-native-paper';

// Una fila informativa no es un botón deshabilitado: sus controles son independientes.
export function ProductRow({ name, description, left, controls, compactControls = false }: {
  name: string;
  description: ReactNode;
  left?: ReactNode;
  controls: ReactNode;
  compactControls?: boolean;
}) {
  const { width } = useWindowDimensions();
  return (
    <View style={styles.row}>
      {left}
      <View style={styles.content}>
        <Text variant="bodyLarge">{name}</Text>
        {description}
      </View>
      <View style={compactControls && width < 500 ? styles.mobileControls : undefined}>
        {controls}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, paddingVertical: 12 },
  content: { flex: 1, minWidth: 0 },
  mobileControls: { width: '100%', alignItems: 'flex-end' },
});
