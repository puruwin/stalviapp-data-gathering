/** Tipos compartidos con el API (ver api/schemas.py). */

export type User = {
  id: string;
  email: string;
  display_name?: string | null;
};

export type AuthResponse = {
  token: string;
  user: User;
};

export type Product = {
  id: string;
  name: string;
  price: number | null;
  price_per_unit: number | null;
  unit: string | null;
  brand: string | null;
  image_url: string | null;
  master_category_id: string | null;
  similarity: number;
};

export type ShoppingList = {
  id: string;
  name: string;
};

/** Resumen de lista para la pantalla índice: incluye nº de items y gasto estimado. */
export type ShoppingListSummary = ShoppingList & {
  item_count: number;
  total: number;
};

export type ListItem = {
  id: string;
  product_id: string;
  quantity: number;
  checked: boolean;
  name: string;
  price: number | null;
  price_per_unit: number | null;
  unit: string | null;
  brand: string | null;
  image_url: string | null;
};

export type ListDetail = ShoppingList & { items: ListItem[] };


/** Catálogo público: se consulta a través de la sesión del API. */
export type CatalogueProduct = Omit<Product, 'similarity'> & {
  image_candidates?: string[] | null;
  price_scope?: { label: string; zone_id?: string; province?: string | null } | null;
  supermarket: string;
  category: string | null;
  category_group: string;
  url: string | null;
  created_at: string;
  last_seen: string;
  previous_price: number | null;
  change_percent: number | null;
};
export type CatalogueFilters = {
  province?: string; q?: string; category?: string; brand?: string; supermarket?: string;
  change?: 'all' | 'down' | 'up' | 'unknown';
  group_by?: 'category' | 'brand' | 'supermarket' | 'none';
  sort?: 'name' | 'price_asc' | 'price_desc' | 'updated' | 'drop';
  page?: number; page_size?: number; ids?: string[];
};
export type CataloguePage = {
  items: CatalogueProduct[]; total: number; page: number; page_size: number;
};
export type CatalogueFacet = { name: string; count: number };
export type CatalogueSummary = {
  province: string | null; provinces: { code: string; name: string }[];
  total: number; category_count: number; supermarket_count: number;
  price_drops: number; price_rises: number; last_seen: string | null;
  categories: CatalogueFacet[]; brands: CatalogueFacet[]; supermarkets: CatalogueFacet[];
};
export type PricePoint = { price: number | null; price_per_unit: number | null; changed_at: string };
export type ProductPriceHistory = {
  product_id: string; days: number; start: string; end: string;
  last_seen: string; observation_count: number; points: PricePoint[];
};
