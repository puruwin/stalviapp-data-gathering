/**
 * Cliente HTTP fino sobre fetch. Mantiene el token JWT en memoria (lo fija el
 * AuthContext tras login/carga) y lo adjunta como Bearer en cada petición.
 */
import { API_URL } from '../config';
import type {
  AuthResponse,
  ListDetail,
  ListItem,
  Product,
  ShoppingList,
  ShoppingListSummary,
} from './types';

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // sin cuerpo JSON
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // --- Auth ---
  register: (email: string, password: string, display_name?: string) =>
    request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  // --- Búsqueda ---
  search: (q: string, k = 20) =>
    request<Product[]>(`/search?q=${encodeURIComponent(q)}&k=${k}`),

  // --- Listas ---
  getLists: () => request<ShoppingListSummary[]>('/lists'),
  createList: (name: string) =>
    request<ShoppingList>('/lists', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  getList: (id: string) => request<ListDetail>(`/lists/${id}`),
  renameList: (id: string, name: string) =>
    request<ShoppingList>(`/lists/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  deleteList: (id: string) =>
    request<void>(`/lists/${id}`, { method: 'DELETE' }),
  emptyList: (id: string) =>
    request<void>(`/lists/${id}/items`, { method: 'DELETE' }),

  // --- Items ---
  addItem: (listId: string, product_id: string, quantity = 1) =>
    request<ListItem>(`/lists/${listId}/items`, {
      method: 'POST',
      body: JSON.stringify({ product_id, quantity }),
    }),
  updateItem: (
    listId: string,
    itemId: string,
    patch: { quantity?: number; checked?: boolean },
  ) =>
    request<ListItem>(`/lists/${listId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  deleteItem: (listId: string, itemId: string) =>
    request<void>(`/lists/${listId}/items/${itemId}`, { method: 'DELETE' }),
  listTotal: (listId: string) =>
    request<{ total: number }>(`/lists/${listId}/total`),
};

export { ApiError };
