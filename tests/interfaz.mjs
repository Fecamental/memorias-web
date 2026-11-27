import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.MEMORIAS_PLAYWRIGHT || "playwright");
const archivoAccesos = process.env.MEMORIAS_TEST_CREDENCIALES || new URL("../.runtime/accesos.txt", import.meta.url);
const url = process.env.MEMORIAS_TEST_WEB || "http://127.0.0.1:14500";
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(url)) throw new Error("Usa únicamente una demo local");
const creds = Object.fromEntries((await readFile(archivoAccesos,
  "utf8")).trim().split(/\r?\n/).map((line) => line.split(": ")));
const browser = await chromium.launch({
  executablePath: process.env.MEMORIAS_BROWSER, headless: true,
  args: ["--disable-extensions", "--disable-background-networking"],
});
try {
  const page = await browser.newPage({ viewport: { width: 1365, height: 850 } });
  await page.goto(url);
  async function login(user) {
    await page.getByLabel("Usuario").fill(user);
    await page.getByLabel("Contraseña").fill(creds[user]);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await page.getByRole("heading", { name: "Bandeja de memorias" }).waitFor();
  }
  await login("elaborador");
  await page.getByRole("button", { name: "Generar memoria" }).last().click();
  await page.getByLabel("Categoría").selectOption("Hidráulica");
  const menu = page.getByLabel("Tipo de cálculo");
  const types = await menu.locator('optgroup[label="Principales"] option').allTextContents();
  assert.deepEqual(types, ["Canales", "Tuberías de Impulsión", "Tuberías por gravedad"]);
  assert.equal(await menu.locator('optgroup[label="Complementarios"] option').count(), 10);
  await menu.selectOption("canales");
  await page.getByText(/Fuentes relacionadas/).waitFor();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Descargar plantilla Excel" }).click();
  assert.equal((await download).suggestedFilename(), "canales.xlsx");
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await login("revisor");
  assert.equal(await page.getByRole("button", { name: "Generar memoria" }).count(), 0);
  await page.getByRole("button", { name: "Demo académica · Viga de hormigón" }).first().click();
  await page.getByRole("heading", { name: "Historial" }).waitFor();
  await page.getByText("Aprobación final", { exact: true }).waitFor();
  await page.getByText("Aprobada", { exact: true }).waitFor();
  await page.screenshot({ path: process.env.MEMORIAS_TEST_CAPTURA || ".runtime/ficha-aprobada.png" });
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await login("responsable");
  await page.getByRole("button", { name: "Demo académica · Viga de hormigón" }).first().click();
  await page.getByRole("heading", { name: "Historial" }).waitFor();
  console.log("Navegador: 3 sesiones, menú Hidráulica, descarga XLSX y memoria aprobada.");
} finally {
  await browser.close();
}
