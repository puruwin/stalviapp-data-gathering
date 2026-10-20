import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useRef, useState } from 'react';
export type PriceAlert = { productId: string; target: number };
type Preferences = { favorites: string[]; alerts: PriceAlert[] };
const empty: Preferences = {favorites:[],alerts:[]};
/** Preferencias locales aisladas por cuenta, nunca compartidas entre sesiones. */
export function usePreferences(userId: string) {
  const key = `stalvi.backoffice.${userId}`;
  const [state,setState] = useState<{key:string; value:Preferences; ready:boolean}>({key,value:empty,ready:false});
  const [error,setError] = useState('');
  const pendingWrite = useRef(Promise.resolve());
  useEffect(()=>{
    let cancelled=false;
    setState({key,value:empty,ready:false});
    AsyncStorage.getItem(key).then(raw=>{
      let value=empty;
      if(raw){const parsed=JSON.parse(raw);value={favorites:Array.isArray(parsed.favorites)?parsed.favorites.filter((x:unknown)=>typeof x==='string').slice(0,500):[],alerts:Array.isArray(parsed.alerts)?parsed.alerts.filter((a:PriceAlert)=>a&&typeof a.productId==='string'&&Number.isFinite(a.target)&&a.target>0).slice(0,500):[]};}
      if(!cancelled)setState({key,value,ready:true});
    }).catch(()=>{if(!cancelled){setError('No se pudieron cargar las preferencias de este navegador.');setState({key,value:empty,ready:true});}});
    return()=>{cancelled=true;};
  },[key]);
  const value=state.key===key?state.value:empty;
  const ready=state.key===key&&state.ready;
  function update(next:Preferences){
    if(!ready)return;
    setState({key,value:next,ready:true});
    // Serializa las escrituras para no perder clics rápidos al guardar.
    pendingWrite.current=pendingWrite.current.catch(()=>{}).then(()=>AsyncStorage.setItem(key,JSON.stringify(next))).catch(()=>setError('No se pudieron guardar las preferencias en este navegador.'));
  }
  return {value,ready,error,
    toggleFavorite:(id:string)=>update({...value,favorites:value.favorites.includes(id)?value.favorites.filter(x=>x!==id):[...value.favorites,id].slice(-500)}),
    saveAlert:(alert:PriceAlert)=>update({...value,alerts:[...value.alerts.filter(a=>a.productId!==alert.productId),alert].slice(-500)}),
    removeAlert:(id:string)=>update({...value,alerts:value.alerts.filter(a=>a.productId!==id)})};
}
