/**
 * Tema de React Native Paper (Material 3). Paleta verde "supermercado" afinada
 * para un look web sencillo y moderno: primario más fresco, fondo gris cálido
 * muy claro y superficies blancas. Solo modo claro por ahora.
 */
import { MD3LightTheme } from 'react-native-paper';

/** Escala común para texto y altura de línea en todas las pantallas. */
export const APP_FONT_SCALE = 1.3;
const scaledFonts = Object.fromEntries(
  Object.entries(MD3LightTheme.fonts).map(([variant, font]) => [variant, {
    ...font,
    ...('fontSize' in font ? { fontSize: font.fontSize * APP_FONT_SCALE } : {}),
    ...('lineHeight' in font ? { lineHeight: font.lineHeight * APP_FONT_SCALE } : {}),
  }]),
) as typeof MD3LightTheme.fonts;

export const theme = {
  ...MD3LightTheme,
  fonts: scaledFonts,
  roundness: 3, // Paper multiplica por 4 → esquinas de ~12
  colors: {
    ...MD3LightTheme.colors,
    primary: '#16a34a', // verde fresco
    onPrimary: '#ffffff',
    primaryContainer: '#c8f0d2',
    onPrimaryContainer: '#04240f',
    secondary: '#00796b',
    background: '#f6f7f5', // gris cálido claro
    onBackground: '#1a1c19',
    surface: '#ffffff',
    onSurface: '#1a1c19',
    surfaceVariant: '#eef0ec',
    onSurfaceVariant: '#43483f',
    outline: '#d5dad2',
    outlineVariant: '#e6e9e3',
    elevation: {
      ...MD3LightTheme.colors.elevation,
      level1: '#ffffff',
      level2: '#ffffff',
    },
  },
};
