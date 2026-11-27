"use client";

import { useEffect, useState } from "react";

const estados = {
  borrador: "Borrador", revision: "En revisión", discrepancia: "Discrepancia técnica",
  aprobacion: "Por aprobar", observada: "Con observaciones", devuelta: "Devuelta", aprobada: "Aprobada",
};
const reportes = { apto: "Apto", apto_alerta: "Apto con alerta", corregir: "Corregir" };
const movimientos = {
  crear: "Memoria creada", verificar: "Verificación previa", enviar: "Envío a revisión",
  derivar: "Envío a aprobación", escalar: "Discrepancia escalada", resolver: "Discrepancia resuelta",
  observar: "Observaciones del responsable", devolver: "Devolución al elaborador",
  nueva_revision: "Nueva revisión", aprobar: "Aprobación final",
};
const acciones = {
  enviar: "Enviar a revisión", derivar: "Enviar para aprobación", escalar: "Escalar discrepancia",
  resolver: "Resolver discrepancia", observar: "Enviar observaciones", devolver: "Registrar devolución",
  nueva_revision: "Crear nueva revisión", aprobar: "Aprobar memoria",
};
const requiereMotivo = ["escalar", "resolver", "observar", "devolver"];
const cobertura = { referencia: "Campos de referencia", parcial: "Referencia parcial", preliminar: "Ficha preliminar" };
const perfiles = { elaborador: "Elaborador técnico", revisor: "Revisor técnico", responsable: "Responsable técnico" };
const fecha = (value) => new Intl.DateTimeFormat("es-CL", {
  dateStyle: "short", timeStyle: "short", timeZone: "America/Santiago",
}).format(new Date(value));

async function api(path, method = "GET", payload) {
  const res = await fetch("/api" + path, {
    method, cache: "no-store",
    ...(payload !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {}),
  });
  if (res.ok) return res.json();
  const body = await res.json().catch(() => ({}));
  const error = new Error(typeof body.detail === "string" ? body.detail :
    body.detail?.map?.((item) => item.loc.slice(1).join(".") + ": " + item.msg).join(" · ") ||
    "No se pudo completar la operación.");
  error.status = res.status;
  throw error;
}

function Badge({ estado }) {
  return <span className={"status status-" + estado}>{estados[estado] || reportes[estado] || estado}</span>;
}

function Fuentes({ tipo }) {
  if (!tipo.fuentes?.length) return null;
  return <details className="sources">
    <summary>Fuentes relacionadas ({tipo.fuentes.length})</summary>
    <ul>{tipo.fuentes.map((item) => <li key={item.ruta} title={item.ruta}>
      <strong>{item.nombre}</strong>
      {item.hojas.length > 0 && <small>{item.hojas.join(", ")}</small>}
    </li>)}</ul>
  </details>;
}

function draft(revision) {
  const { alcance, desviacion, conclusion, veredicto, variables } = revision;
  return { alcance, desviacion, conclusion, veredicto: veredicto || "",
    variables: Object.fromEntries(variables.map((v) => [v.variable, { valor: v.valor, fuente: v.fuente }])) };
}

export default function Home() {
  const [user, setUser] = useState(undefined);
  const [catalog, setCatalog] = useState([]);
  const [items, setItems] = useState([]);
  const [view, setView] = useState("lista");
  const [detail, setDetail] = useState(null);
  const [data, setData] = useState(null);
  const [category, setCategory] = useState("");
  const [type, setType] = useState("");
  const [filter, setFilter] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");

  async function reload() {
    const [types, memories] = await Promise.all([api("/catalogo"), api("/memorias")]);
    setCatalog(types);
    setItems(memories);
  }

  useEffect(() => {
    api("/sesion").then(async (session) => { setUser(session); await reload(); })
      .catch((e) => { setUser(null); if (e.status !== 401) setError(e.message); });
  }, []);

  async function run(callback) {
    setBusy(true); setError(""); setNotice("");
    try { await callback(); }
    catch (e) { setError(e.message); if (e.status === 401) setUser(null); }
    finally { setBusy(false); }
  }

  async function open(id, number) {
    const record = await api("/memorias/" + id + (number ? "?numero=" + number : ""));
    setDetail(record); setData(draft(record.revision)); setView("detalle");
    setDirty(false); setAction(""); setReason("");
  }

  function go(where) {
    if (dirty && !window.confirm("¿Salir de la ficha con cambios sin guardar?")) return;
    setView(where); setError(""); setNotice(""); setDirty(false);
  }

  function update(key, value) { setData({ ...data, [key]: value }); setDirty(true); }
  function variable(key, part, value) {
    update("variables", { ...data.variables, [key]: { valor: "", fuente: "", ...data.variables[key], [part]: value } });
  }

  async function saveDraft() {
    const values = Object.fromEntries(Object.entries(data.variables).filter(([key, v]) =>
      !currentType.fields.find((field) => field.key === key)?.automatic && v.valor !== ""));
    const body = { ...data, variables: values, veredicto: data.veredicto || null, version: detail.memoria.version };
    return api("/memorias/" + detail.memoria.id + "/borrador", "PUT", body);
  }

  const currentType = detail?.tipo;
  const chosen = catalog.find((item) => item.code === type);
  const revision = detail?.revision;
  const editable = detail?.acciones.includes("guardar");
  const needsAction = { elaborador: ["borrador", "devuelta"], revisor: ["revision", "observada"], responsable: ["discrepancia", "aprobacion"] };
  const relevant = (item) => needsAction[user?.rol]?.includes(item.estado);
  const rows = items.filter((item) => (!pendingOnly || relevant(item)) &&
    [item.codigo, item.titulo, estados[item.estado]].some((v) =>
      v.toLocaleLowerCase("es").includes(filter.trim().toLocaleLowerCase("es"))));

  if (user === undefined) return <main className="loading" aria-live="polite">Cargando aplicación…</main>;

  if (!user) return <main className="signin">
    <div className="signin-card">
      <div className="brand"><span className="brand-icon" aria-hidden="true">M</span><span>Memorias de cálculo</span></div>
      <h1>Iniciar sesión</h1>
      <form onSubmit={(event) => {
        event.preventDefault(); const form = new FormData(event.currentTarget);
        run(async () => {
          const session = await api("/sesion", "POST", Object.fromEntries(form));
          await reload(); setUser(session); setView("lista"); setPendingOnly(false); setFilter("");
        });
      }}>
        <label>Usuario<input autoComplete="username" name="usuario" required /></label>
        <label>Contraseña<input autoComplete="current-password" name="clave" type="password" required /></label>
        {error && <p className="message error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>Ingresar</button>
      </form>
    </div>
  </main>;

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon" aria-hidden="true">M</span><span>Memorias de cálculo</span></div>
      <nav aria-label="Principal">
        <button className={view !== "nueva" ? "nav-active" : ""} onClick={() => go("lista")}>▤ <span>Bandeja de memorias</span></button>
        {user.rol === "elaborador" && <button className={view === "nueva" ? "nav-active" : ""} onClick={() => go("nueva")}>＋ <span>Generar memoria</span></button>}
      </nav>
      <div className="profile"><span className="avatar" aria-hidden="true">{user.usuario[0].toUpperCase()}</span><div><strong>{user.usuario}</strong><small>{user.nombre}</small></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><span>{user.nombre}</span><button className="secondary" onClick={() =>
        run(async () => { await api("/sesion", "DELETE"); setUser(null); setDirty(false); setDetail(null); })}>Cerrar sesión</button></header>
      <main className="container" aria-busy={busy}>
        {error && <p className="message error" role="alert">{error}</p>}
        {notice && <p className="message notice" role="status">{notice}</p>}
        {view === "lista" && <>
          <div className="page-title"><div><h1>Bandeja de memorias</h1><p>Consulta el estado y la revisión vigente de cada memoria.</p></div>
            {user.rol === "elaborador" && <button className="primary" onClick={() => go("nueva")}>＋ Generar memoria</button>}
          </div>
          <div className="metrics">
            <div><small>Memorias visibles</small><strong>{items.length}</strong></div>
            <div><small>Requieren mi acción</small><strong>{items.filter(relevant).length}</strong></div>
            <div><small>Aprobadas</small><strong>{items.filter((item) => item.estado === "aprobada").length}</strong></div>
          </div>
          <section className="panel">
            <div className="toolbar">
              <input aria-label="Buscar memorias" placeholder="Buscar por código, título o estado" value={filter} onChange={(e) => setFilter(e.target.value)} />
              <label className="check"><input type="checkbox" checked={pendingOnly} onChange={(e) => setPendingOnly(e.target.checked)} /> Requieren mi acción</label>
              <button className="secondary" disabled={busy} onClick={() => run(reload)}>Actualizar</button>
            </div>
            <div className="table-scroll"><table>
              <thead><tr><th>Memoria</th><th>Tipo de cálculo</th><th>Estado</th><th>Revisión</th></tr></thead>
              <tbody>{rows.map((item) => <tr key={item.id}>
                <td><button className="link" disabled={busy} onClick={() => run(() => open(item.id))}>{item.titulo}</button><small>{item.codigo}</small></td>
                <td>{catalog.find((t) => t.code === item.tipo)?.name}</td><td><Badge estado={item.estado} /></td><td>R{item.actual}</td>
              </tr>)}</tbody>
            </table></div>
            {rows.length === 0 && <p className="empty">No hay memorias para esta vista.</p>}
          </section>
        </>}
        {view === "nueva" && <>
          <button className="link back" onClick={() => go("lista")}>← Volver a la bandeja</button>
          <div className="page-title"><div><h1>Generar memoria</h1><p>Selecciona una categoría y un tipo de cálculo.</p></div></div>
          <form className="panel form" onSubmit={(event) => {
            event.preventDefault(); const titulo = new FormData(event.currentTarget).get("titulo");
            run(async () => {
              const item = await api("/memorias", "POST", { titulo, tipo: type }); await reload(); await open(item.id);
            });
          }}>
            <div className="form-grid">
              <label>Categoría<select required value={category} onChange={(event) => { setCategory(event.target.value); setType(""); }}>
                <option value="">Seleccionar categoría</option>
                {[...new Set(catalog.map((item) => item.category))].map((name) => <option key={name}>{name}</option>)}
              </select></label>
              <label>Tipo de cálculo<select required value={type} disabled={!category} onChange={(event) => setType(event.target.value)}>
                <option value="">Seleccionar cálculo</option>
                {["Principales", "Complementarios"].map((group, index) => {
                  const types = catalog.filter((item) => item.category === category && Boolean(item.complementario) === Boolean(index));
                  return types.length > 0 && <optgroup key={group} label={group}>{types.map((item) =>
                    <option key={item.code} value={item.code}>{item.name}</option>)}</optgroup>;
                })}
              </select></label>
            </div>
            {chosen && <div className="reference"><strong>{cobertura[chosen.coverage]}</strong>
              <span>{chosen.source || "Pendiente de una planilla de referencia"}</span>
              <a className="link" href={"/api/catalogo/" + type + "/plantilla"}>Descargar plantilla Excel</a>
              <Fuentes tipo={chosen} />
            </div>}
            <label>Título de la memoria<input name="titulo" maxLength={160} required /></label>
            <div><button className="primary" disabled={busy || !type}>Crear borrador</button></div>
          </form>
        </>}
        {view === "detalle" && revision && currentType && <>
          <button className="link back" onClick={() => go("lista")}>← Volver a la bandeja</button>
          <div className="page-title"><div><p className="code">{detail.memoria.codigo} · {currentType.name}</p>
            <h1>{detail.memoria.titulo}</h1><p>Generador: {revision.generador} · Modelo {revision.modelo}</p></div><Badge estado={detail.memoria.estado} />
          </div>
          <div className="detail-grid">
            <section className="panel form">
              <div className="revision-tools">
                <label>Revisión<select value={revision.numero} onChange={(e) => {
                  const number = Number(e.target.value);
                  if (dirty && !window.confirm("¿Cambiar de revisión con cambios sin guardar?")) return;
                  run(() => open(detail.memoria.id, number));
                }}>{detail.revisiones.map((item) => <option key={item.numero} value={item.numero}>R{item.numero}</option>)}</select></label>
                <div className="downloads">
                  {["xlsx", "docx"].map((extension) => <a className="secondary" key={extension}
                    href={"/api/memorias/" + detail.memoria.id + "/revision/" + revision.numero + "/" + extension}>
                    {extension === "xlsx" ? "Descargar Excel" : "Generar memoria Word"}</a>)}
                </div>
              </div>
              <div className="reference"><strong>{cobertura[currentType.coverage]}</strong><span>{currentType.source || "Pendiente de una planilla de referencia"}</span><Fuentes tipo={currentType} /></div>
              <label>Objetivo y alcance<textarea value={data.alcance} maxLength={5000} readOnly={!editable} onChange={(e) => update("alcance", e.target.value)} /></label>
              {["entrada", "resultado"].map((group) => <div key={group} className="field-group">
                <h2>{group === "entrada" ? "Datos de entrada" : "Resultados"}</h2>
                <div className="field-head"><span>Variable</span><span>Valor</span><span>Unidad</span><span>Fuente</span></div>
                {currentType.fields.filter((field) => field.group === group).map((field) => {
                  const value = data.variables[field.key] || {};
                  return <div className="field-row" key={field.key}>
                    <div><strong>{field.label}</strong><small>{field.key}{field.automatic ? " · Calculado" : ""}</small></div>
                    <input aria-label={"Valor de " + field.label} type="number" step="any" readOnly={!editable || field.automatic} value={value.valor ?? ""} onChange={(e) => variable(field.key, "valor", e.target.value)} />
                    <span className="unit">{field.unit}</span>
                    <input aria-label={"Fuente de " + field.label} maxLength={300} readOnly={!editable || field.automatic} value={value.fuente ?? ""} onChange={(e) => variable(field.key, "fuente", e.target.value)} />
                  </div>;
                })}
              </div>)}
              <label>Desviación y justificación<textarea value={data.desviacion} maxLength={2000} readOnly={!editable} onChange={(e) => update("desviacion", e.target.value)} /></label>
              <label>Conclusión<textarea value={data.conclusion} maxLength={5000} readOnly={!editable} onChange={(e) => update("conclusion", e.target.value)} /></label>
              <label>Veredicto del cálculo<select value={data.veredicto} disabled={!editable} onChange={(e) => update("veredicto", e.target.value)}>
                <option value="">Pendiente</option><option value="cumple">Cumple</option><option value="no_cumple">No cumple</option>
              </select></label>
              {editable && <div className="buttons">
                <button className="secondary" disabled={busy} onClick={() => run(async () => {
                  await saveDraft(); await open(detail.memoria.id); setNotice("Borrador guardado.");
                })}>Guardar borrador</button>
                <button className="primary" disabled={busy} onClick={() => run(async () => {
                  const saved = dirty ? await saveDraft() : detail.memoria;
                  await api("/memorias/" + detail.memoria.id + "/verificar", "POST", { version: saved.version });
                  await open(detail.memoria.id);
                })}>Verificar memoria</button>
              </div>}
            </section>
            <aside className="detail-side">
              <section className="panel form">
                <h2>Verificación previa</h2>
                {revision.reporte && !dirty ? <>
                  <div><Badge estado={revision.reporte.estado} /></div>
                  <p className="muted">{revision.reporte.alcance}</p>
                  {[...revision.reporte.hallazgos, ...revision.reporte.alertas].map((msg, i) => <p key={i}>{msg}</p>)}
                </> : <p className="muted">{dirty ? "Guarda y verifica los cambios." : "Pendiente de verificación."}</p>}
                <div className="buttons">
                  {detail.acciones.filter((key) => acciones[key]).map((key) =>
                    <button key={key} className="secondary" disabled={busy || (key === "enviar" && dirty)} onClick={() => { setAction(key); setReason(""); }}>{acciones[key]}</button>)}
                </div>
                {action && <form className="action-form" onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    await api("/memorias/" + detail.memoria.id + "/" + action, "POST", { version: detail.memoria.version, motivo: reason });
                    await reload(); await open(detail.memoria.id); setNotice("Movimiento registrado.");
                  });
                }}>
                  <h3>{acciones[action]}</h3>
                  <label>Motivo{requiereMotivo.includes(action) ? " (obligatorio)" : " (opcional)"}
                    <textarea value={reason} onChange={(e) => setReason(e.target.value)} required={requiereMotivo.includes(action)} maxLength={2500} />
                  </label>
                  <div className="buttons"><button className="primary" disabled={busy || (action === "enviar" && dirty)}>Confirmar</button><button type="button" className="link" onClick={() => setAction("")}>Cancelar</button></div>
                </form>}
              </section>
              <section className="panel form">
                <h2>Historial</h2>
                <ol className="timeline">{detail.movimientos.map((item) => <li key={item.id}>
                  <strong>{movimientos[item.accion]}</strong>
                  <small>{perfiles[item.rol]} · R{item.revision} · {fecha(item.fecha)}</small>
                  {item.motivo && <p>{item.accion === "verificar" ? reportes[item.motivo] : item.motivo}</p>}
                </li>)}</ol>
              </section>
            </aside>
          </div>
        </>}
      </main>
    </div>
  </div>;
}
