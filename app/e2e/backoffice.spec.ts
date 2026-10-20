import { test, expect, login, apiURL } from './fixtures';

test('catálogo real agrupado, búsqueda, ficha e histórico', async ({page,account,request})=>{
  const summary=await request.get(`${apiURL}/catalogue/summary`,{headers:{Authorization:`Bearer ${account.token}`}});
  expect(summary.status()).toBe(200);
  expect((await summary.json()).total).toBeGreaterThan(0);
  await login(page,account);
  await page.getByRole('button',{name:'Abrir backoffice',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Productos',exact:true})).toBeVisible();
  const results=page.waitForResponse(r=>r.url().includes('/catalogue/products?')&&r.url().includes('q=leche')&&r.status()===200);
  await page.getByLabel('Buscar productos',{exact:true}).fill('leche');
  const data=await(await results).json();
  expect(data.items.length).toBeGreaterThan(0);
  const product=data.items[0];
  await page.getByTestId(`catalogue-product-${product.id}`).click();
  await expect(page.getByRole('heading',{name:product.name,exact:true})).toBeVisible();
  const history=page.waitForResponse(r=>r.url().includes(`/catalogue/products/${product.id}/history?days=365`)&&r.status()===200);
  await page.getByRole('button',{name:'1 año',exact:true}).click();
  const series=await(await history).json();
  expect(series.observation_count).toBeGreaterThan(0);
  await expect(page.getByRole('img',{name:/Histórico de precios:/})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Crear alerta de precio',exact:true}).click();
  await page.getByLabel('Precio objetivo en euros',{exact:true}).fill('0.5');
  await page.getByRole('button',{name:'Guardar alerta',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Alerta guardada'})).toBeVisible();
});

test('ruta protegida y recuperación del error de catálogo',async({page,account})=>{
  await page.goto('/backoffice');
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  await login(page,account);
  await page.route('**/catalogue/products?**',route=>route.abort());
  await page.getByRole('button',{name:'Abrir backoffice',exact:true}).click();
  await expect(page.getByRole('heading',{name:'No se pudieron cargar los productos',exact:true})).toBeVisible();
  await page.unroute('**/catalogue/products?**');
  await page.getByRole('button',{name:'Reintentar',exact:true}).click();
  await expect(page.getByTestId('catalogue-total')).not.toHaveText('0');
  await page.getByLabel('Agrupar productos',{exact:true}).selectOption('brand');
  await expect(page.getByLabel('Agrupar productos',{exact:true})).toHaveValue('brand');
});
