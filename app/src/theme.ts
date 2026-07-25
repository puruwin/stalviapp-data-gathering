/** Tema de React Native Paper (Material 3). Paleta simple para el MVP. */
import { MD3LightTheme } from 'react-native-paper';

export const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#2e7d32', // verde "supermercado"
    secondary: '#00796b',
  },
};
