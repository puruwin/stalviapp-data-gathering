import { execFileSync } from 'node:child_process';
import { randomBytes, randomUUID } from 'node:crypto';
import { resolve } from 'node:path';
import { test as base, expect, type Page } from '@playwright/test';

export const apiURL = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000';
type Account = { email: string; password: string; token: string; user: { id: string; email: string } };

export const test = base.extend<{ accounts: Account[]; account: Account }>({
  accounts: async ({ request }, use) => {
    const accounts: Account[] = [];
    try {
      for (let i = 0; i < 2; i++) {
        const email = `e2e-${randomUUID()}@example.com`;
        const password = randomBytes(24).toString('hex');
        const response = await request.post(`${apiURL}/auth/register`, { data: { email, password } });
        expect(response.status()).toBe(201);
        accounts.push({ email, password, ...await response.json() });
      }
      await use(accounts);
    } finally {
      // Solo borra las cuentas creadas por este test, con cascada sobre sus listas.
      const root = resolve(__dirname, '../..');
      execFileSync(process.env.E2E_PYTHON ?? resolve(root, '.venv/bin/python'), [
        '-c',
        [
          'import sys, json',
          'sys.path.insert(0, sys.argv[1])',
          'from api.db import owner_conn',
          'with owner_conn() as conn:',
          "    conn.execute('DELETE FROM profiles WHERE email = ANY(%s)', (json.loads(sys.argv[2]),))",
        ].join('\n'),
        root, JSON.stringify(accounts.map((a) => a.email)),
      ], { cwd: root, stdio: 'pipe' });
    }
  },
  account: async ({ accounts }, use) => { await use(accounts[0]); },
});

export { expect };

export async function login(page: Page, account: Account) {
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill(account.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Entrar', exact: true }).last().click();
  await expect(page.getByText('Mis listas', { exact: true })).toBeVisible();
}

export async function createList(page: Page, name: string) {
  await page.getByRole('button', { name: 'Crear lista', exact: true }).click();
  await page.getByLabel('Nombre de la lista', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Crear', exact: true }).click();
  await page.getByText(name, { exact: true }).click();
  await expect(page.getByText('Total estimado', { exact: true })).toBeVisible();
}

export async function menu(page: Page, name: string) {
  await page.getByRole('button', { name: 'Opciones de la lista', exact: true }).click();
  await page.getByRole('menuitem', { name, exact: true }).click();
}
