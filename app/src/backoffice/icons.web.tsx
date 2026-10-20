const paths = {
  layers: 'm12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5',
  heart: 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  grid: 'M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z',
  cart: 'M2 3h3l3 13h11l3-9H6M9 21h.1M18 21h.1',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  package: 'm3 7 9-5 9 5v10l-9 5-9-5V7Zm0 0 9 5 9-5M12 12v10M7 4l10 5',
  down: 'm3 6 7 7 4-4 7 7M15 16h6v-6',
  store: 'M3 9h18l-2-6H5L3 9Zm1 0v12h16V9M9 21v-8h6v8',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  filter: 'M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M1 14h6m2-6h6m2 8h6',
  close: 'm6 6 12 12M6 18 18 6',
  logout: 'M9 4H3v16h6M10 12h12m-5-5 5 5-5 5',
  refresh: 'M3 11a9 9 0 1 1 2 7M3 4v7h7',
  external: 'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',
};
export type IconName = keyof typeof paths;
export function Icon({name}: {name:IconName}) {return <svg viewBox="0 0 24 24" className="bo-icon" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;}
