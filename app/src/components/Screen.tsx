/**
 * Contenedor de pantalla responsive. Pinta el fondo del tema a pantalla completa
 * y centra el contenido con un ancho máximo legible en web (en móvil ocupa todo
 * el ancho de forma natural).
 *
 * Uso:
 * - Pantallas SIN FlatList (login, detalle): envuelve el contenido en <Screen>.
 * - Pantallas CON FlatList: usa <Screen> para el fondo y aplica el centrado en el
 *   `contentContainerStyle` de la lista con `contentMaxWidth` (ver export), para no
 *   romper el scroll envolviendo la lista en un View con flex.
 */
import type { ReactNode } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';
import { useTheme } from 'react-native-paper';

/** Ancho máximo del contenido centrado en pantallas anchas. */
export const MAX_WIDTH = 720;

/**
 * Estilo listo para el `contentContainerStyle` de un FlatList: centra el
 * contenido y le da padding horizontal, manteniendo el scroll a pantalla completa.
 */
export const contentMaxWidth: ViewStyle = {
  width: '100%',
  maxWidth: MAX_WIDTH,
  alignSelf: 'center',
  paddingHorizontal: 16,
};

type Props = {
  children: ReactNode;
  /** Ancho máximo del bloque centrado (por defecto MAX_WIDTH). */
  maxWidth?: number;
  /** Centra vertical y horizontalmente (p. ej. login). */
  center?: boolean;
  style?: ViewStyle;
};

export function Screen({ children, maxWidth = MAX_WIDTH, center, style }: Props) {
  const theme = useTheme();
  return (
    <View style={[styles.root, { backgroundColor: theme.colors.background }]}>
      <View
        style={[
          styles.content,
          { maxWidth },
          center && styles.centered,
          style,
        ]}
      >
        {children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: {
    flex: 1,
    width: '100%',
    alignSelf: 'center',
    paddingHorizontal: 16,
  },
  centered: { justifyContent: 'center' },
});
