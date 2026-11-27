# Memorias Web para Windows

Ejecuta `MemoriasWeb-Windows-x64.exe` con doble clic. Se abrirá el navegador predeterminado. La primera vez también se abrirá el archivo de accesos para elaborador, revisor y responsable. La consola muestra el enlace, la ubicación del archivo de accesos y la opción de cerrar con Ctrl+C.

La edición portátil es para Windows de 64 bits en procesadores Intel o AMD. Se probó en Windows 11. Incluye la interfaz, Python, la API y PostgreSQL 18.7. Requiere el navegador del equipo y espacio para extraer los componentes temporales.

Los expedientes y accesos locales se conservan en `%LOCALAPPDATA%\MemoriasWebPortable`. Cada equipo y cuenta de Windows tiene su propia base. Copiar únicamente el ejecutable a otro equipo inicia una base vacía. En esta edición académica, cada contraseña coincide con su usuario, elaborador, revisor o responsable. Para abrir una carpeta de datos distinta, ejecuta `MemoriasWeb-Windows-x64.exe --datos "C:\Ruta\Datos"`.

## Compilar y verificar

En el repositorio MemoriasWeb, con Python 3.14, uv y Node.js disponibles:

```powershell
pwsh -NoProfile -File ./portable/construir.ps1
python ./portable/verificar.py "$env:LOCALAPPDATA/MemoriasWebBuild/dist/MemoriasWeb-Windows-x64.exe"
```

El compilador prepara todo en el perfil local, verifica el SHA-256 publicado de PostgreSQL, exporta la interfaz de Next.js y empaqueta los componentes con PyInstaller. `-CrtDir` permite indicar la ubicación de las DLL redistribuibles de Visual C++ x64. El archivo de accesos y la base local se preparan al arrancar.

- [Binarios de PostgreSQL de EDB](https://www.enterprisedb.com/download-postgresql-binaries)
- [Exportación estática de Next.js](https://nextjs.org/docs/app/guides/static-exports)
- [Empaquetado de PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html)
