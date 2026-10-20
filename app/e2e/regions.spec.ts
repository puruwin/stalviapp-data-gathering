import { test, expect, login, apiURL } from './fixtures';

test('Alicante filtra catálogo y ficha, y conserva la provincia al recargar', async ({page,account,request},testInfo)=>{
  const summary=await request.get(`${apiURL}/catalogue/summary?province=03`,{headers:{Authorization:`Bearer ${account.token}`}});
  expect(summary.status()).toBe(200);
  const regional=await summary.json();
  expect(regional.total).toBeGreaterThan(0);
  await login(page,account);
  await page.getByRole('button',{name:'Abrir backoffice',exact:true}).click();
  const selector=page.getByLabel('Seleccionar provincia',{exact:true});
  await expect(selector.locator('option[value="03"]')).toBeAttached();
  const response=page.waitForResponse(r=>r.url().includes('/catalogue/products?')&&r.url().includes('province=03')&&r.status()===200);
  await selector.selectOption('03');
  const data=await(await response).json();
  expect(data.total).toBe(regional.total);
  expect(new Set(data.items.map((p:{id:string})=>p.id)).size).toBe(data.items.length);
  expect(data.items.every((p:{price_scope:{province:string}})=>p.price_scope?.province==='Alicante')).toBe(true);
  await expect(page.getByTestId('catalogue-total')).toHaveText(regional.total.toLocaleString('es-ES'));
  await page.getByTestId(`catalogue-product-${data.items[0].id}`).click();
  await expect(page.getByRole('heading',{name:data.items[0].name,exact:true})).toBeVisible();
  await expect(page.getByText(/Catálogo observado en Alicante\./)).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:testInfo.outputPath('alicante.png'),fullPage:false});
  await page.reload();
  await expect(selector).toHaveValue('03');
  await expect(page.getByTestId('catalogue-total')).toHaveText(regional.total.toLocaleString('es-ES'));
  await selector.selectOption('');
  await expect(selector).toHaveValue('');
});
