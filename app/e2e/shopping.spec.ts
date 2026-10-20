import { test, expect, login, createList, menu } from './fixtures';

test('recorrido principal con productos reales, cantidades y total', async ({ page, account }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page, account);
  await createList(page, 'Compra principal');
  const total = page.getByLabel('Total estimado de la lista', { exact: true });
  await expect(total).toHaveText('0.00 €');
  await page.getByRole('button', { name: 'Añadir productos', exact: true }).click();
  const response = page.waitForResponse((r) => r.url().includes('/search?') && r.status() === 200);
  await page.getByLabel('Buscar productos', { exact: true }).fill('leche');
  const products = await (await response).json();
  expect(products.length).toBeGreaterThan(0);
  const product = products[0];
  const add = page.getByRole('button', { name: `Añadir ${product.name}`, exact: true }).first();
  await expect(add).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await add.click();
  await page.getByRole('button', { name: 'Ver lista', exact: true }).click();
  await expect(total).toHaveText(`${product.price.toFixed(2)} €`);
  await page.getByRole('button', { name: `Aumentar cantidad de ${product.name}`, exact: true }).click();
  await expect(total).toHaveText(`${(product.price * 2).toFixed(2)} €`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: `Reducir cantidad de ${product.name}`, exact: true }).click();
  await expect(total).toHaveText(`${product.price.toFixed(2)} €`);
  const checked = page.getByRole('checkbox', { name: `Comprado: ${product.name}`, exact: true });
  await checked.click();
  await expect(checked).toBeChecked();
  await expect(total).toHaveText(`${product.price.toFixed(2)} €`);
  await page.getByRole('button', { name: `Quitar ${product.name}`, exact: true }).click();
  await expect(total).toHaveText('0.00 €');

  await menu(page, 'Renombrar');
  await page.getByLabel('Nombre de la lista', { exact: true }).fill('Compra renombrada');
  await page.getByRole('button', { name: 'Guardar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Compra renombrada', exact: true })).toBeVisible();
  await expect(page.getByLabel('Nombre de la lista', { exact: true })).toBeHidden();

  // Vuelve a añadir para comprobar que Vaciar elimina items y recalcula el total.
  await page.getByRole('button', { name: 'Añadir productos', exact: true }).click();
  await page.getByLabel('Buscar productos', { exact: true }).fill('leche');
  await page.getByRole('button', { name: `Añadir ${product.name}`, exact: true }).first().click();
  await page.getByRole('button', { name: 'Ver lista', exact: true }).click();
  await expect(total).toHaveText(`${product.price.toFixed(2)} €`);
  await menu(page, 'Vaciar lista');
  await page.getByRole('button', { name: 'Vaciar', exact: true }).click();
  await expect(total).toHaveText('0.00 €');
  await expect(page.getByRole('button', { name: 'Vaciar', exact: true })).toBeHidden();
  await menu(page, 'Borrar lista');
  await page.getByRole('button', { name: 'Borrar', exact: true }).click();
  await expect(page.getByText('Aún no tienes listas', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
