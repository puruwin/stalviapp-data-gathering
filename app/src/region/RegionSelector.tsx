import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { Button, Menu, Text } from 'react-native-paper';
import { api } from '../api/client';
import { useRegion } from './RegionContext';

export function RegionSelector() {
  const { province, setProvince, ready, error } = useRegion();
  const [open, setOpen] = useState(false);
  const regions = useQuery({queryKey:['catalogue-summary',''],queryFn:()=>api.getCatalogueSummary(),enabled:ready,staleTime:60000});
  const label = regions.data?.provinces.find(p=>p.code===province)?.name || (province ? `Provincia ${province}` : 'Todas las provincias');
  return <View><Menu visible={open} onDismiss={()=>setOpen(false)} anchor={<Button icon="map-marker-outline" disabled={!ready} onPress={()=>setOpen(true)} accessibilityLabel="Seleccionar provincia">{label}</Button>}>
    <ScrollView style={{maxHeight:350}}><Menu.Item title="Todas las provincias" onPress={()=>{setProvince('');setOpen(false);}}/>{regions.data?.provinces.map(p=><Menu.Item key={p.code} title={p.name} onPress={()=>{setProvince(p.code);setOpen(false);}}/>)}</ScrollView>
  </Menu>{!!province&&<Text variant="bodySmall">Catálogo observado en la provincia. La entrega depende de tu código postal.</Text>}{regions.isError&&<Button onPress={()=>void regions.refetch()}>Reintentar provincias</Button>}{!!error&&<Text accessibilityRole="alert">{error}</Text>}</View>;
}
