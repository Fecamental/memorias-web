from io import BytesIO

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .formulas import FORMULAS

COBERTURA = {"referencia": "Campos seleccionados de una referencia",
             "parcial": "Referencia parcial", "preliminar": "Formato preliminar"}


def planilla(tipo, memoria=None, revision=None):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Ficha de cálculo"
    hoja.append([tipo["name"], None, None, None, None])
    hoja.append([COBERTURA[tipo["coverage"]], tipo["source"] or "Pendiente de referencia"])
    hoja.append(["Planilla", memoria["codigo"] if memoria else None,
                 "Generador", revision["generador"] if revision else None,
                 f"Revisión {revision['numero']}" if revision else f"Modelo {tipo['modelo']}"])
    hoja.append(["Código", "Variable", "Valor", "Unidad", "Fuente"])
    valores = {v["variable"]: v for v in revision["variables"]} if revision else {}
    filas = {f["key"]: i for i, f in enumerate(tipo["fields"], 5)}
    for campo in tipo["fields"]:
        key = campo["key"]
        dato = valores.get(key)
        valor = float(dato["valor"]) if dato else None
        fuente = dato["fuente"] if dato else None
        hoja.append([key, campo["label"], valor, campo["unit"], fuente])
        fila = hoja[filas[key]]
        fila[2].fill = PatternFill("solid", fgColor="E8EDF4" if campo["automatic"] else "EAF3FF")
        if fuente:
            fila[4].data_type = "s"
        if campo["automatic"] and not revision:
            hoja.cell(filas[key], 3, FORMULAS[tipo["code"]][key].excel(filas))
            hoja.cell(filas[key], 5, tipo["source"])
    for columna in hoja[4]:
        columna.fill = PatternFill("solid", fgColor="1D3853")
        columna.font = Font(color="FFFFFF", bold=True)
    for columna, ancho in zip("ABCDE", (18, 62, 25, 18, 68)):
        hoja.column_dimensions[columna].width = ancho
    hoja.cell(1, 1).font = Font(size=15, bold=True, color="1D3853")
    hoja.merge_cells("A1:E1")
    hoja.merge_cells("B2:E2")
    hoja.row_dimensions[2].height = 32
    hoja["B2"].alignment = Alignment(wrap_text=True)
    hoja.freeze_panes = "C5"
    hoja.auto_filter.ref = f"A4:E{hoja.max_row}"
    if tipo.get("fuentes"):
        fuentes = libro.create_sheet("Fuentes")
        fuentes.append(["Archivo", "Ruta en carpeta de referencia", "Hojas"])
        for item in tipo["fuentes"]:
            fuentes.append([item["nombre"], item["ruta"], ", ".join(item["hojas"])])
            for celda in fuentes[fuentes.max_row]:
                celda.data_type = "s"
                celda.alignment = Alignment(wrap_text=True, vertical="top")
            fuentes.row_dimensions[fuentes.max_row].height = 36
        for col, ancho in zip("ABC", (47, 78, 60)):
            fuentes.column_dimensions[col].width = ancho
        for celda in fuentes[1]:
            celda.fill = PatternFill("solid", fgColor="1D3853")
            celda.font = Font(color="FFFFFF", bold=True)
        fuentes.freeze_panes = "A2"
    archivo = BytesIO()
    libro.save(archivo)
    return archivo.getvalue()


def memoria_word(tipo, item, revision):
    documento = Document()
    documento.add_heading(item["titulo"], 0)
    documento.add_paragraph(tipo["name"])
    documento.add_heading("0. Control del documento", 1)
    documento.add_paragraph(f"{item['codigo']} · Revisión {revision['numero']} · Modelo {revision['modelo']} · {revision['generador']}")
    documento.add_heading("1. Objetivo y alcance", 1)
    documento.add_paragraph(revision["alcance"])
    documento.add_heading("2. Referencias", 1)
    documento.add_paragraph(tipo["source"] or "Sin referencia de plantilla")
    documento.add_heading("3. Bases de cálculo", 1)
    documento.add_paragraph("Ver las fuentes de las variables y resultados.")
    documento.add_heading("4. Supuestos y simplificaciones", 1)
    documento.add_paragraph(COBERTURA[tipo["coverage"]])
    valores = {v["variable"]: v for v in revision["variables"]}
    for grupo, titulo in (("entrada", "5. Datos de entrada"), ("resultado", "6. Resultados y verificación")):
        documento.add_heading(titulo, 1)
        tabla = documento.add_table(rows=1, cols=5)
        tabla.style = "Light Shading Accent 1"
        for celda, texto in zip(tabla.rows[0].cells, ("Código", "Variable", "Valor", "Unidad", "Fuente")):
            celda.text = texto
        for campo in tipo["fields"]:
            if campo["group"] != grupo:
                continue
            key = campo["key"]
            dato = valores.get(key)
            fila = tabla.add_row().cells
            for celda, valor in zip(fila, (key, campo["label"], dato["valor"] if dato else "",
                                           campo["unit"], dato["fuente"] if dato else "")):
                celda.text = str(valor)
    documento.add_heading("7. Desviaciones", 1)
    documento.add_paragraph(revision["desviacion"] or "Sin desviaciones declaradas.")
    documento.add_heading("8. Conclusión", 1)
    documento.add_paragraph(revision["conclusion"])
    if revision["veredicto"]:
        documento.add_paragraph({"cumple": "CUMPLE", "no_cumple": "NO CUMPLE"}[revision["veredicto"]])
    archivo = BytesIO()
    documento.save(archivo)
    return archivo.getvalue()
