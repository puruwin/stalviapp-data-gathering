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
