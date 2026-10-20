import { test, expect, apiURL, login, createList } from './fixtures';

test('token inválido guardado: limpia sesión y vuelve al login incluso al volver atrás', async ({ page, account }) => {
  await login(page, account);
  await createList(page, 'Lista antes de caducar');
  await page.evaluate(() => {
    const session = JSON.parse(localStorage.getItem('stalvi.session')!);
    session.token = 'token-invalido';
    localStorage.setItem('stalvi.session', JSON.stringify(session));
  });
  await page.reload();
  await expect(page.getByText('Tu sesión ha caducado. Vuelve a entrar.', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('stalvi.session'))).toBeNull();
  await page.goBack();
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
});

test('401 durante una sesión: sale del área privada sin reintentar con el mismo token', async ({ page, account }) => {
  await login(page, account);
  let requests = 0;
  await page.route(`${apiURL}/lists`, async (route) => {
    requests++;
    await route.fulfill({ status: 401, json: { detail: 'Token inválido o expirado' } });
  });
  await page.reload();
  await expect(page.getByText('Tu sesión ha caducado. Vuelve a entrar.', { exact: true })).toBeVisible();
  expect(requests).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem('stalvi.session'))).toBeNull();
});

test('credenciales incorrectas y servidor caído en login permiten corregir y volver a entrar', async ({ page, account }) => {
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill(account.email);
  await page.getByLabel('Contraseña', { exact: true }).fill('password-incorrecto');
  const submit = page.getByRole('button', { name: 'Entrar', exact: true }).last();
  await submit.click();
  await expect(page.getByText('Credenciales inválidas', { exact: true })).toBeVisible();
  await page.getByLabel('Contraseña', { exact: true }).fill(account.password);
  await page.route(`${apiURL}/auth/login`, (route) => route.abort('connectionrefused'));
  await submit.click();
  await expect(page.getByText('No se pudo conectar con el servidor', { exact: true })).toBeVisible();
  await expect(submit).toBeEnabled();
  await page.unroute(`${apiURL}/auth/login`);
  await submit.click();
  await expect(page.getByText('Mis listas', { exact: true })).toBeVisible();
});

test('caída de servidor en listas, búsqueda y mutación: conserva sesión y permite reintentar', async ({ page, account }) => {
  await login(page, account);
  await page.route(`${apiURL}/**`, (route) => route.abort('connectionrefused'));
  await page.reload();
  await expect(page.getByText('No se pudieron cargar las listas.', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('stalvi.session'))).not.toBeNull();
  await page.unroute(`${apiURL}/**`);
  await page.getByRole('button', { name: 'Reintentar', exact: true }).click();
  await expect(page.getByText('Aún no tienes listas', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Crear lista', exact: true }).click();
  await page.getByLabel('Nombre de la lista', { exact: true }).fill('Lista recuperada');
  await page.route(`${apiURL}/lists`, (route) => route.abort('connectionrefused'));
  await page.getByRole('button', { name: 'Crear', exact: true }).click();
  await expect(page.getByText('No se pudo guardar la lista. Inténtalo de nuevo.', { exact: true })).toBeVisible();
  await page.unroute(`${apiURL}/lists`);
  await page.getByRole('button', { name: 'Crear', exact: true }).click();
  await page.getByText('Lista recuperada', { exact: true }).click();
  await page.getByRole('button', { name: 'Añadir productos', exact: true }).click();
  await page.route(`${apiURL}/search?*`, (route) => route.abort('connectionrefused'));
  await page.getByLabel('Buscar productos', { exact: true }).fill('leche');
  await expect(page.getByText('Error al buscar. Inténtalo de nuevo.', { exact: true })).toBeVisible();
  await page.unroute(`${apiURL}/search?*`);
  await page.getByRole('button', { name: 'Reintentar búsqueda', exact: true }).click();
  await expect(page.getByRole('button', { name: /^Añadir / }).first()).toBeVisible();
});

test('recarga, navegación atrás y cambio de cuenta no muestran listas ajenas', async ({ page, accounts }) => {
  await login(page, accounts[0]);
  await createList(page, 'Solo de la primera cuenta');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Solo de la primera cuenta', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Añadir productos', exact: true }).click();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Solo de la primera cuenta', exact: true })).toBeVisible();
  await page.goBack();
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible();
  // Se cambia de cuenta sin recargar el documento: la caché sigue en memoria.
  await page.getByLabel('Email', { exact: true }).fill(accounts[1].email);
  await page.getByLabel('Contraseña', { exact: true }).fill(accounts[1].password);
  await page.getByRole('button', { name: 'Entrar', exact: true }).last().click();
  await expect(page.getByText('Aún no tienes listas', { exact: true })).toBeVisible();
  await expect(page.getByText('Solo de la primera cuenta', { exact: true })).toBeHidden();
  await page.reload();
  await expect(page.getByText('Aún no tienes listas', { exact: true })).toBeVisible();
});

test('un 401 tardío de la cuenta anterior no cierra la nueva sesión', async ({ page, accounts }) => {
  await login(page, accounts[0]);
  await createList(page, 'Lista de la cuenta anterior');
  let release!: () => void;
  let seen!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const started = new Promise<void>((resolve) => { seen = resolve; });
  await page.route(`${apiURL}/search?*`, async (route) => {
    seen();
    await gate;
    await route.fulfill({ status: 401, json: { detail: 'Token expirado' } });
  });
  try {
    await page.getByRole('button', { name: 'Añadir productos', exact: true }).click();
    await page.getByLabel('Buscar productos', { exact: true }).fill('leche');
    await started;
    await page.goBack();
    await page.goBack();
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
    await page.getByLabel('Email', { exact: true }).fill(accounts[1].email);
    await page.getByLabel('Contraseña', { exact: true }).fill(accounts[1].password);
    await page.getByRole('button', { name: 'Entrar', exact: true }).last().click();
    await expect(page.getByText('Aún no tienes listas', { exact: true })).toBeVisible();
    const response = page.waitForResponse((r) => r.url().includes('/search?') && r.status() === 401);
    release();
    await response;
    await expect(page.getByText('Mis listas', { exact: true })).toBeVisible();
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('stalvi.session')!));
    expect(saved.user.id).toBe(accounts[1].user.id);
  } finally {
    release();
  }
});
