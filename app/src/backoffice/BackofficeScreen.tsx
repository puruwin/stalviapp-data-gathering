/** Versión nativa del catálogo. Metro usa el backoffice completo en la web. */
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Image, ScrollView, View } from 'react-native';
import { ActivityIndicator, Appbar, Button, Card, SegmentedButtons, Text, TextInput } from 'react-native-paper';
import { api } from '../api/client';
import { changeLabel, euros, safeURL } from './format';
import PriceChart from './PriceChart';
export default function BackofficeScreen(){
  const router=useRouter();
  const [q,setQ]=useState('');
  const [search,setSearch]=useState('');
  const [page,setPage]=useState(1);
  const [selected,setSelected]=useState<string|null>(null);
  const [days,setDays]=useState('90');
  const catalogue=useQuery({queryKey:['catalogue-native',search,page],queryFn:()=>api.getCatalogue({q:search,page,page_size:25})});
  const detail=useQuery({queryKey:['catalogue-product',selected],queryFn:()=>api.getCatalogueProduct(selected!),enabled:!!selected});
  const history=useQuery({queryKey:['price-history',selected,Number(days)],queryFn:()=>api.getProductHistory(selected!,Number(days)),enabled:!!selected});
  return <View style={{flex:1}}><Appbar.Header><Appbar.BackAction accessibilityLabel="Volver a mis listas" onPress={()=>router.back()}/><Appbar.Content title="Catálogo de productos"/></Appbar.Header><ScrollView contentContainerStyle={{padding:16,gap:14,width:'100%',maxWidth:800,alignSelf:'center'}}>{selected?<><Button onPress={()=>setSelected(null)}>Volver al catálogo</Button>{detail.isLoading?<ActivityIndicator/>:detail.isError?<Button onPress={()=>void detail.refetch()}>Reintentar ficha</Button>:detail.data&&<Card><Card.Title title={detail.data.name} subtitle={detail.data.category_group}/><Card.Content>{safeURL(detail.data.image_url)&&<Image source={{uri:safeURL(detail.data.image_url)}} style={{width:100,height:100,alignSelf:'center'}} resizeMode="contain"/>}<Text variant="headlineMedium">{euros(detail.data.price)}</Text><Text>{changeLabel(detail.data.change_percent)}</Text><Text>Ref. {detail.data.id}</Text><Text variant="titleMedium" style={{marginVertical:16}}>Histórico de precios</Text><SegmentedButtons value={days} onValueChange={setDays} buttons={[{value:'30',label:'30 días'},{value:'90',label:'90 días'},{value:'365',label:'1 año'}]}/>{history.isLoading?<ActivityIndicator/>:history.isError?<Button onPress={()=>void history.refetch()}>Reintentar histórico</Button>:history.data&&<PriceChart data={history.data}/>}</Card.Content></Card>}</>:<><TextInput label="Buscar productos" accessibilityLabel="Buscar productos" value={q} onChangeText={setQ} onSubmitEditing={()=>{setSearch(q);setPage(1);}}/><Button onPress={()=>{setSearch(q);setPage(1);}}>Buscar</Button>{catalogue.isLoading?<ActivityIndicator/>:catalogue.isError?<Button onPress={()=>void catalogue.refetch()}>Reintentar catálogo</Button>:<>{!catalogue.data?.items.length&&<Text>No se encontraron productos.</Text>}{catalogue.data?.items.map(p=><Card key={p.id} onPress={()=>setSelected(p.id)}><Card.Title title={p.name} subtitle={`${p.category_group} · ${euros(p.price)}`}/></Card>)}<View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center'}}><Button disabled={page===1} onPress={()=>setPage(page-1)}>Anterior</Button><Text>Página {page}</Text><Button disabled={page*25>=(catalogue.data?.total??0)} onPress={()=>setPage(page+1)}>Siguiente</Button></View></>}</>}</ScrollView></View>;
}
