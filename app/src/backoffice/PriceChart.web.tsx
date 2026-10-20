import { useState } from 'react';
import { APP_FONT_SCALE } from '../theme';
import type { ProductPriceHistory } from '../api/types';
import { euros, shortDate, dateTime } from './format';

/** Serie escalonada: el precio persiste entre observaciones, no se interpola. */
export default function PriceChart({ data }: { data: ProductPriceHistory }) {
  const [active, setActive] = useState<number | null>(null);
  const start = new Date(data.start).getTime();
  const end = new Date(data.end).getTime();
  const observedEnd = Math.min(end, new Date(data.last_seen).getTime());
  const points = data.points.filter(p => new Date(p.changed_at).getTime() <= observedEnd);
  const known = points.filter(p => p.price !== null);
  if (!known.length || observedEnd < start) return <div className="bo-chart-empty">No hay precios registrados en este periodo.</div>;
  const prices = known.map(p => p.price as number);
  const minimum = Math.min(...prices), maximum = Math.max(...prices);
  const margin = Math.max((maximum - minimum) * .25, .1);
  const low = Math.max(0, minimum - margin), high = maximum + margin;
  const x = (time: number) => 59 + Math.max(0, Math.min(1, (time - start) / (end - start))) * 289;
  const y = (price: number) => 20 + (high - price) / (high - low) * 140;
  let path = '', open = false;
  points.forEach((p, i) => {
    const xx = x(new Date(p.changed_at).getTime());
    if (p.price == null) { if (open) path += ` H${xx}`; open = false; return; }
    path += `${open ? ' H' : ' M'}${xx}${open ? ' V' : ','}${y(p.price)}`;
    open = true;
    const next = points[i + 1];
    if (!next) path += ` H${x(observedEnd)}`;
  });
  const selected = active == null ? null : points[active];
  return <>
    <div className="bo-chart">
      <svg viewBox="0 0 360 200" role="img" aria-label={`Histórico de precios: ${known.length} registros, entre ${euros(minimum)} y ${euros(maximum)}`}>
        {[0, .5, 1].map(t => <g key={t}><line x1="59" y1={20+t*140} x2="348" y2={20+t*140} stroke="#e4e9df" strokeDasharray="4 5"/><text x="0" y={24+t*140} fill="#7d8c73" fontSize={11 * APP_FONT_SCALE}>{euros(high-t*(high-low))}</text></g>)}
        <path d={path} fill="none" stroke="#64834e" strokeWidth="2.5" strokeLinejoin="round"/>
        {[0, .5, 1].map(t => <text key={t} x={59+t*289} y="188" textAnchor={t===0?'start':t===1?'end':'middle'} fontSize={11 * APP_FONT_SCALE} fill="#7d8c73">{shortDate(start+t*(end-start))}</text>)}
        {points.map((p,i)=> p.price==null ? null : <circle key={p.changed_at} cx={x(new Date(p.changed_at).getTime())} cy={y(p.price)} r={active===i?5:3.5} fill="#64834e" stroke="white" strokeWidth="1.5" tabIndex={0} aria-label={`${dateTime(p.changed_at)}: ${euros(p.price)}`} onMouseEnter={()=>setActive(i)} onMouseLeave={()=>setActive(null)} onFocus={()=>setActive(i)} onBlur={()=>setActive(null)}><title>{dateTime(p.changed_at)} · {euros(p.price)}</title></circle>)}
      </svg>
      {selected && <div className="bo-chart-tip" role="status">{dateTime(selected.changed_at)} · <strong>{euros(selected.price)}</strong></div>}
    </div>
    <p className="bo-chart-note"><span/>Precio registrado en {shortDate(data.last_seen)} · hasta la última observación</p>
    <div className="bo-price-stats"><div>Mínimo<strong>{euros(minimum)}</strong></div><div>Máximo<strong>{euros(maximum)}</strong></div><div>Registros del periodo<strong>{points.filter(p=>new Date(p.changed_at).getTime()>=start).length}</strong></div></div>
    {data.observation_count === 1 && <p className="bo-note">Solo hay un precio registrado. Aún no se han observado cambios.</p>}
    <details className="bo-history-records"><summary>Ver registros y fechas</summary><table><thead><tr><th>Fecha observada</th><th>Precio</th></tr></thead><tbody>{points.map(p=><tr key={p.changed_at}><td>{dateTime(p.changed_at)}{new Date(p.changed_at).getTime()<start?' · precio inicial':''}</td><td>{euros(p.price)}</td></tr>)}</tbody></table></details>
  </>;
}
