# Memorias Web

Prototipo local para elaborar, revisar y aprobar memorias de cálculo. Implementación autónoma con FastAPI, Pydantic 2, asyncpg, PostgreSQL 18.4 y Next.js 16.4.6. Usa su propio contenedor, base, credenciales y puertos.

## Edición portátil

La versión de un solo ejecutable para Windows está descrita en la [guía portátil](portable/README.md).

## Abrir

Aplicación local en [127.0.0.1:14500](http://127.0.0.1:14500). Cada contraseña coincide con su usuario, `elaborador`, `revisor` o `responsable`. El listado de accesos está en `.runtime/accesos.txt`.

Para iniciar o reiniciar, desde esta carpeta:

```powershell
python -m pip install -r requirements.txt
pwsh -NoProfile -File ./iniciar.ps1
```

Requiere Docker Desktop, Python y Node.js. La primera ejecución usa el contenedor `memorias-web-pg18` en el puerto 15484, FastAPI en 14801 y Next.js en 14500, todos en loopback. La configuración creada en `.runtime` es local.

## Recorrido

1. Elaborador técnico. Generar memoria, elegir categoría y cálculo, crear el borrador, completar valores y fuentes, guardar y verificar. Se puede generar el Word y descargar el Excel de la revisión.
2. Revisor técnico. Consultar la memoria y el reporte, derivar a aprobación o escalar una discrepancia. Si el responsable envía observaciones, registrar la devolución y el motivo.
3. Responsable técnico. Resolver discrepancia, enviar observaciones o aprobar. La aprobación figura en la bandeja y en el historial.
4. Elaborador técnico. Crear una nueva revisión después de la devolución, corregir y repetir la verificación. Las versiones enviadas permanecen consultables.

La verificación de esta demo comprende campos y fuentes. El veredicto técnico, el reporte de verificación y la aprobación humana tienen estados propios. El Word contiene control documental, alcance, variables, resultados y conclusión. Las notificaciones se muestran dentro de la bandeja. [Cobertura del catálogo](docs/REFERENCIAS.md).

## Datos

`memoria` conserva el código por tipo y correlativo, el generador y el estado actual. `revision` registra cada versión y su verificación. `variable_revision` asigna cada código de variable a un valor numérico, una unidad y una fuente para esa revisión. `movimiento` registra actor, perfil, fecha y motivo. Las transiciones se ejecutan en transacción y comprueban la versión vigente. La API deriva el perfil y el generador de la sesión local. El rol de PostgreSQL de la API tiene permisos acotados por tabla y el acceso a expedientes se comprueba en la API.

## Verificación

```powershell
python -m pytest -q
node tests/flujo.mjs
npm.cmd --prefix frontend run build
python -m backend.exportar_plantillas entregables/Plantillas-calculo.zip
```

La prueba del flujo deja una memoria académica aprobada en la base local para ver el historial. El ZIP contiene las 19 plantillas por categoría. Los expedientes conservan su versión del catálogo. Los ejemplos públicos utilizan valores sintéticos.
