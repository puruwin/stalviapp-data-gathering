/** Respaldo nativo accesible; la visualización SVG interactiva se resuelve en web. */
import { View } from 'react-native';
import { Text } from 'react-native-paper';
import type { ProductPriceHistory } from '../api/types';
import { dateTime, euros } from './format';
export default function PriceChart({data}: {data:ProductPriceHistory}) {
  return <View style={{gap:10}}>{data.points.length ? data.points.map(p=><Text key={p.changed_at}>{dateTime(p.changed_at)} · {euros(p.price)}</Text>) : <Text>No hay precios registrados en este periodo.</Text>}</View>;
}
