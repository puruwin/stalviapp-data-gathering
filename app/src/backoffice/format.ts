/** Presentación compartida: los valores ausentes nunca se convierten en cero. */
export const euros = (n: number | null | undefined) =>
  n == null ? 'Sin precio' : new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(n);
export const dateTime = (s: string) => new Date(s).toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' });
export const shortDate = (s: string | number) => new Date(s).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
export const market = (s: string) => s ? s[0].toUpperCase() + s.slice(1) : 'Sin tienda';
export const changeLabel = (n: number | null) => n == null ? 'Sin comparación' : `${n > 0 ? '↗ +' : n < 0 ? '↘ ' : ''}${n.toLocaleString('es-ES', { maximumFractionDigits: 1 })} %`;
export function safeURL(value: string | null): string | undefined {
  if (!value) return undefined;
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}
