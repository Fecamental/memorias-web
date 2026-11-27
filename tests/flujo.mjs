import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const base = process.env.MEMORIAS_TEST_URL || "http://127.0.0.1:14500/api";
if (!/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(base)) throw new Error("Usa únicamente una demo local");
const archivoAccesos = process.env.MEMORIAS_TEST_CREDENCIALES || new URL("../.runtime/accesos.txt", import.meta.url);
const credentials = Object.fromEntries((await readFile(
  archivoAccesos, "utf8"
)).trim().split(/\r?\n/).map((line) => line.split(": ")));

async function api(method, path, body, cookie = "", expected = 200) {
  const res = await fetch(base + path, {
    method, headers: { Cookie: cookie, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const type = res.headers.get("content-type") || "";
  const data = type.includes("json") ? await res.json() : new Uint8Array(await res.arrayBuffer());
  assert.equal(res.status, expected, method + " " + path + ": " + JSON.stringify(data).slice(0, 400));
  return { cookie: res.headers.get("set-cookie")?.split(";")[0], data };
}

const users = {};
for (const [usuario, clave] of Object.entries(credentials)) {
  users[usuario] = (await api("POST", "/sesion", { usuario, clave })).cookie;
}
const run = (role, path, method = "GET", body, expected) => api(method, path, body, users[role], expected);
const { data: catalog } = await run("elaborador", "/catalogo");
assert.equal(catalog.length, 39);
assert.deepEqual(catalog.filter((item) => !item.complementario).reduce((groups, t) => ({ ...groups, [t.category]: (groups[t.category] || 0) + 1 }), {}), {
  Estructuras: 8, Geotecnia: 8, Hidráulica: 3,
});
await api("GET", "/memorias", undefined, "", 401);
await run("revisor", "/memorias", "POST", { tipo: "viga", titulo: "Prueba negativa" }, 403);
for (const item of catalog) {
  const { data } = await run("elaborador", "/catalogo/" + item.code + "/plantilla");
  assert.deepEqual(Array.from(data.slice(0, 2)), [80, 75], item.code);
}
const { data: memoria } = await run("elaborador", "/memorias", "POST", {
  tipo: "viga", titulo: "Demo académica · Viga de hormigón",
}, 201);
const path = "/memorias/" + memoria.id;
let version = memoria.version;
const get = async (role = "elaborador", query = "") => (await run(role, path + query)).data;
const step = async (role, action, motivo = "", expected = 200) => {
  const result = (await run(role, path + "/" + action, "POST", { version, motivo }, expected)).data;
  if (expected === 200) version = (await get()).memoria.version;
  return result;
};

await run("revisor", path, "GET", undefined, 404);
await step("elaborador", "enviar", "", 409);
assert.equal((await step("elaborador", "verificar")).estado, "corregir");

const inputs = { d: 385, bw: 275, fc: 32, fy: 465, es: 195000, ecu: 0.0028, et: 0.0065, wu: 18, l: 8, phi: 0.8 };
const variables = Object.fromEntries(Object.entries(inputs).map(([key, valor]) =>
  [key, { valor, fuente: "Datos sintéticos de viga" }]));
const draft = { alcance: "Mostrar el flujo de revisión de una viga simplemente apoyada.",
  conclusion: "El caso de demostración registra momento último y momento nominal requerido.",
  veredicto: "no_cumple", variables };
const save = async (changes = {}) => {
  const result = (await run("elaborador", path + "/borrador", "PUT", { ...draft, ...changes, version })).data;
  version = result.version;
};
await save();
assert.equal((await step("elaborador", "verificar")).estado, "apto");
const before = await get();
assert.equal(before.revision.modelo, 2);
assert.equal(before.tipo.modelo, 2);
assert.equal(Number(before.revision.variables.find((v) => v.variable === "mu").valor), 144);
assert.equal(Number(before.revision.variables.find((v) => v.variable === "mn").valor), 180);
await step("elaborador", "enviar");
await run("revisor", path + "/borrador", "PUT", { ...draft, version }, 403);
await step("elaborador", "aprobar", "", 403);
await step("revisor", "escalar", "", 422);
await step("revisor", "escalar", "Revisar criterio de diseño con el responsable.");
await step("responsable", "observar", "Precisar la fuente de los resultados.");
await step("revisor", "devolver", "Añadir justificación y trazabilidad de la carga.");
await step("elaborador", "nueva_revision");
assert.equal((await get("revisor")).revision.numero, 1);
await run("revisor", path + "?numero=2", "GET", undefined, 404);
await save({ desviacion: "El caso usa cargas ficticias para comprobar el flujo." });
assert.equal((await step("elaborador", "verificar")).estado, "apto_alerta");
await step("elaborador", "enviar");
await step("revisor", "escalar", "Confirmar alcance de la desviación.");
await step("responsable", "resolver", "Se acepta la desviación declarada para la demo.");
await step("responsable", "aprobar", "Revisión técnica final registrada.");
const end = await get();
assert.equal(end.memoria.estado, "aprobada");
assert.equal(end.revision.numero, 2);
assert.equal(end.revisiones.length, 2);
assert.equal((await get("revisor", "?numero=1")).revision.desviacion, "");
assert.equal(end.movimientos[0].actor, "responsable");
for (const format of ["xlsx", "docx"]) {
  const { data } = await run("responsable", path + "/revision/2/" + format);
  assert.deepEqual(Array.from(data.slice(0, 2)), [80, 75]);
}
const { data: canal } = await run("elaborador", "/memorias", "POST", {
  tipo: "canales", titulo: "Demostración · Canal trapezoidal",
}, 201);
const canalPath = "/memorias/" + canal.id;
const datosCanal = { q: 4.1, b: 3, z: 1.2, y: 0.85, s: 0.0016, n: 0.021 };
const guardado = (await run("elaborador", canalPath + "/borrador", "PUT", {
  version: canal.version,
  alcance: "Comprobar el cálculo con la geometría sintética del canal.",
  conclusion: "Resultados para el tirante adoptado.",
  veredicto: "cumple",
  variables: Object.fromEntries(Object.entries(datosCanal).map(([clave, valor]) =>
    [clave, { valor, fuente: "Caso sintético de canal trapezoidal" }])),
})).data;
assert.equal((await run("elaborador", canalPath + "/verificar", "POST", {
  version: guardado.version,
})).data.estado, "apto");
const canalRecargado = (await run("elaborador", canalPath)).data;
assert.equal(canalRecargado.tipo.modelo, 2);
assert.ok(Math.abs(Number(canalRecargado.revision.variables.find((v) => v.variable === "cap").valor)
  - 4.65160073) < 0.000001);

console.log(memoria.codigo + " · 39 plantillas verificadas · flujo con devolución, alerta y aprobación · permisos, cálculo de canal y exportaciones aprobados.");
