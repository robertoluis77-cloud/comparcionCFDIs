"""
Módulo de comparación exhaustiva de archivos XML (CFDIs del SAT México).

Compara archivos de texto plano (diff línea por línea) y estructura XML (DOM)
para detectar diferencias semánticas y sintácticas entre dos carpetas.
"""

import difflib
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from lxml import etree  # pylint: disable=c-extension-no-member


class EstadoArchivo(Enum):
    """Estados posibles de un archivo durante la comparación."""

    IGUAL = "IGUAL"
    DIFERENTE = "DIFERENTE"
    AUSENTE_EN_ERP = "AUSENTE EN ERP"
    AUSENTE_EN_SAT = "AUSENTE EN SAT"


@dataclass
class DiferenciaDetalle:
    """Representa una diferencia específica encontrada entre dos archivos."""

    numero_linea_erp: Optional[int]
    numero_linea_sat: Optional[int]
    contenido_erp: str
    contenido_sat: str
    tipo: str
    opcodes_inline: List[Tuple] = field(default_factory=list)

    def __str__(self) -> str:
        """Retorna representación legible de la diferencia."""
        linea_erp = str(self.numero_linea_erp) if self.numero_linea_erp else "N/A"
        linea_sat = str(self.numero_linea_sat) if self.numero_linea_sat else "N/A"
        return (
            f"Línea ERP={linea_erp} / SAT={linea_sat} | "
            f"Tipo={self.tipo} | "
            f"ERP: '{self.contenido_erp[:80]}' | "
            f"SAT: '{self.contenido_sat[:80]}'"
        )


@dataclass
class ResultadoArchivo:
    """Contiene el resultado de la comparación de un par de archivos."""

    nombre_archivo: str
    estado: EstadoArchivo
    diferencias: List[DiferenciaDetalle] = field(default_factory=list)
    lineas_erp: List[str] = field(default_factory=list)
    lineas_sat: List[str] = field(default_factory=list)
    opcodes_diff: List[Tuple] = field(default_factory=list)

    @property
    def cantidad_diferencias(self) -> int:
        """Retorna el total de diferencias encontradas."""
        return len(self.diferencias)


@dataclass
class ResultadoComparacion:
    """Agrupa todos los resultados de la comparación entre las dos carpetas."""

    ruta_erp: str
    ruta_sat: str
    resultados: List[ResultadoArchivo] = field(default_factory=list)

    @property
    def total_iguales(self) -> int:
        """Retorna la cantidad de archivos idénticos."""
        return sum(1 for r in self.resultados if r.estado == EstadoArchivo.IGUAL)

    @property
    def total_diferentes(self) -> int:
        """Retorna la cantidad de archivos con diferencias."""
        return sum(1 for r in self.resultados if r.estado == EstadoArchivo.DIFERENTE)

    @property
    def total_ausentes_erp(self) -> int:
        """Retorna la cantidad de archivos ausentes en ERP."""
        return sum(
            1 for r in self.resultados if r.estado == EstadoArchivo.AUSENTE_EN_ERP
        )

    @property
    def total_ausentes_sat(self) -> int:
        """Retorna la cantidad de archivos ausentes en SAT."""
        return sum(
            1 for r in self.resultados if r.estado == EstadoArchivo.AUSENTE_EN_SAT
        )


def _leer_archivo(ruta: str) -> Tuple[str, List[str]]:
    """
    Lee un archivo XML con soporte para UTF-8 y ISO-8859-1.

    Args:
        ruta: Ruta absoluta o relativa al archivo XML.

    Returns:
        Tupla con (contenido_completo, lista_de_líneas).

    Raises:
        ValueError: Si el encoding no puede ser detectado.
    """
    for encoding in ("utf-8-sig", "utf-8", "iso-8859-1", "latin-1"):
        try:
            with open(ruta, "r", encoding=encoding) as archivo:
                contenido = archivo.read()
            lineas = contenido.splitlines(keepends=True)
            return contenido, lineas
        except UnicodeDecodeError:
            continue

    raise ValueError(
        f"No se pudo leer el archivo '{ruta}' con los encodings soportados "
        "(UTF-8, ISO-8859-1). Verifique que el archivo sea un XML válido."
    )


def calcular_opcodes_inline(texto_erp: str, texto_sat: str) -> List[Tuple]:
    """
    Calcula los opcodes de diferencias a nivel de caracteres entre dos cadenas.

    Utiliza ``difflib.SequenceMatcher`` con ``autojunk=False`` para obtener
    la granularidad más fina posible.  El resultado puede usarse directamente
    para construir marcado HTML con resaltado inline.

    Solo produce opcodes útiles cuando ambas cadenas son no vacías y distintas;
    en cualquier otro caso devuelve una lista vacía.

    Args:
        texto_erp: Cadena original (lado ERP).
        texto_sat: Cadena nueva (lado SAT).

    Returns:
        Lista de tuplas ``(tag, i1, i2, j1, j2)`` tal como devuelve
        ``SequenceMatcher.get_opcodes()``.  Lista vacía si alguna cadena
        está vacía o si ambas son idénticas.
    """
    if not texto_erp or not texto_sat or texto_erp == texto_sat:
        return []
    matcher = difflib.SequenceMatcher(None, texto_erp, texto_sat, autojunk=False)
    return matcher.get_opcodes()


def _construir_diferencia_texto(
    tag: str,
    bloque_erp: List[str],
    bloque_sat: List[str],
    offset_erp: int,
    offset_sat: int,
) -> List[DiferenciaDetalle]:
    """
    Construye las diferencias de texto para un bloque de cambio del diff.

    Args:
        tag: Tipo de cambio: 'replace', 'delete' o 'insert'.
        bloque_erp: Líneas del ERP afectadas.
        bloque_sat: Líneas del SAT afectadas.
        offset_erp: Índice de línea base en ERP (1-basado).
        offset_sat: Índice de línea base en SAT (1-basado).

    Returns:
        Lista de DiferenciaDetalle generadas.
    """
    diferencias: List[DiferenciaDetalle] = []
    max_lineas = max(len(bloque_erp), len(bloque_sat))

    tipo_mapa = {
        "replace": "modificación",
        "delete": "línea eliminada",
        "insert": "línea agregada",
    }
    tipo = tipo_mapa.get(tag, tag)

    for idx in range(max_lineas):
        linea_erp = bloque_erp[idx].rstrip("\n\r") if idx < len(bloque_erp) else ""
        linea_sat = bloque_sat[idx].rstrip("\n\r") if idx < len(bloque_sat) else ""
        num_erp: Optional[int] = offset_erp + idx if idx < len(bloque_erp) else None
        num_sat: Optional[int] = offset_sat + idx if idx < len(bloque_sat) else None
        diferencias.append(
            DiferenciaDetalle(
                numero_linea_erp=num_erp,
                numero_linea_sat=num_sat,
                contenido_erp=linea_erp,
                contenido_sat=linea_sat,
                tipo=tipo,
                opcodes_inline=calcular_opcodes_inline(linea_erp, linea_sat),
            )
        )

    return diferencias


def _comparar_texto(
    lineas_erp: List[str],
    lineas_sat: List[str],
) -> Tuple[List[DiferenciaDetalle], List[Tuple]]:
    """
    Compara dos listas de líneas a nivel de texto plano (diff línea por línea).

    Args:
        lineas_erp: Líneas del archivo ERP.
        lineas_sat: Líneas del archivo SAT.

    Returns:
        Tupla con (lista_de_diferencias, lista_de_opcodes_para_HTML).
    """
    diferencias: List[DiferenciaDetalle] = []
    matcher = difflib.SequenceMatcher(None, lineas_erp, lineas_sat, autojunk=False)
    opcodes = matcher.get_opcodes()

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue

        bloque_erp = lineas_erp[i1:i2]
        bloque_sat = lineas_sat[j1:j2]
        diferencias.extend(
            _construir_diferencia_texto(tag, bloque_erp, bloque_sat, i1 + 1, j1 + 1)
        )

    return diferencias, opcodes


def _comparar_atributos_nodo(
    nodo_erp: etree._Element,  # type: ignore[name-defined]
    nodo_sat: etree._Element,  # type: ignore[name-defined]
    ruta_actual: str,
) -> List[DiferenciaDetalle]:
    """
    Compara los atributos de dos nodos XML equivalentes.

    Args:
        nodo_erp: Nodo del árbol DOM del ERP.
        nodo_sat: Nodo del árbol DOM del SAT.
        ruta_actual: Ruta XPath acumulada del nodo.

    Returns:
        Lista de diferencias en atributos.
    """
    diferencias: List[DiferenciaDetalle] = []
    attrs_erp = dict(nodo_erp.attrib)
    attrs_sat = dict(nodo_sat.attrib)
    todas_attrs = sorted(set(attrs_erp.keys()) | set(attrs_sat.keys()))

    for attr in todas_attrs:
        val_erp = attrs_erp.get(attr, "<ausente>")
        val_sat = attrs_sat.get(attr, "<ausente>")
        if val_erp != val_sat:
            diferencias.append(
                DiferenciaDetalle(
                    numero_linea_erp=nodo_erp.sourceline,
                    numero_linea_sat=nodo_sat.sourceline,
                    contenido_erp=f"@{attr}='{val_erp}'",
                    contenido_sat=f"@{attr}='{val_sat}'",
                    tipo=f"atributo diferente en {ruta_actual}",
                )
            )
    return diferencias


def _comparar_nodos(
    nodo_erp: etree._Element,  # type: ignore[name-defined]
    nodo_sat: etree._Element,  # type: ignore[name-defined]
    ruta_xpath: str,
) -> List[DiferenciaDetalle]:
    """
    Compara recursivamente dos nodos XML y sus descendientes.

    Args:
        nodo_erp: Nodo del árbol DOM del archivo ERP.
        nodo_sat: Nodo del árbol DOM del archivo SAT.
        ruta_xpath: Ruta XPath acumulada para identificar la posición.

    Returns:
        Lista de diferencias encontradas en los nodos y sus hijos.
    """
    diferencias: List[DiferenciaDetalle] = []
    etiqueta = nodo_erp.tag.split("}")[-1] if "}" in nodo_erp.tag else nodo_erp.tag
    ruta_actual = f"{ruta_xpath}/{etiqueta}" if ruta_xpath else etiqueta

    diferencias.extend(_comparar_atributos_nodo(nodo_erp, nodo_sat, ruta_actual))

    texto_erp = (nodo_erp.text or "").strip()
    texto_sat = (nodo_sat.text or "").strip()
    if texto_erp != texto_sat:
        diferencias.append(
            DiferenciaDetalle(
                numero_linea_erp=nodo_erp.sourceline,
                numero_linea_sat=nodo_sat.sourceline,
                contenido_erp=texto_erp[:120],
                contenido_sat=texto_sat[:120],
                tipo=f"texto de nodo diferente en {ruta_actual}",
            )
        )

    hijos_erp = list(nodo_erp)
    hijos_sat = list(nodo_sat)

    for idx, (hijo_erp, hijo_sat) in enumerate(zip(hijos_erp, hijos_sat)):
        diferencias.extend(
            _comparar_nodos(hijo_erp, hijo_sat, f"{ruta_actual}[{idx}]")
        )

    for idx in range(len(hijos_sat), len(hijos_erp)):
        tag = hijos_erp[idx].tag.split("}")[-1]
        diferencias.append(
            DiferenciaDetalle(
                numero_linea_erp=hijos_erp[idx].sourceline,
                numero_linea_sat=None,
                contenido_erp=f"<{tag}> (extra en ERP)",
                contenido_sat="<ausente>",
                tipo=f"nodo extra en ERP en {ruta_actual}",
            )
        )

    for idx in range(len(hijos_erp), len(hijos_sat)):
        tag = hijos_sat[idx].tag.split("}")[-1]
        diferencias.append(
            DiferenciaDetalle(
                numero_linea_erp=None,
                numero_linea_sat=hijos_sat[idx].sourceline,
                contenido_erp="<ausente>",
                contenido_sat=f"<{tag}> (extra en SAT)",
                tipo=f"nodo extra en SAT en {ruta_actual}",
            )
        )

    return diferencias


def _comparar_xml_dom(
    contenido_erp: str,
    contenido_sat: str,
    diferencias_existentes: List[DiferenciaDetalle],
) -> List[DiferenciaDetalle]:
    """
    Compara la estructura XML a nivel de DOM para detectar diferencias semánticas.

    Detecta diferencias en atributos y valores de nodos que el diff de texto
    podría no capturar (por ejemplo, atributos en distinto orden).

    Args:
        contenido_erp: Contenido completo del XML del ERP.
        contenido_sat: Contenido completo del XML del SAT.
        diferencias_existentes: Diferencias ya encontradas en la comparación de texto.

    Returns:
        Lista ampliada de diferencias con hallazgos del análisis DOM.
    """
    nuevas_diferencias: List[DiferenciaDetalle] = list(diferencias_existentes)

    try:  # pylint: disable=c-extension-no-member
        raiz_erp = etree.fromstring(contenido_erp.encode("utf-8"))
        raiz_sat = etree.fromstring(contenido_sat.encode("utf-8"))
    except etree.XMLSyntaxError as exc:  # pylint: disable=c-extension-no-member
        nuevas_diferencias.append(
            DiferenciaDetalle(
                numero_linea_erp=None,
                numero_linea_sat=None,
                contenido_erp="",
                contenido_sat="",
                tipo=f"Error de sintaxis XML: {exc}",
            )
        )
        return nuevas_diferencias

    diferencias_dom = _comparar_nodos(raiz_erp, raiz_sat, "")

    if not diferencias_existentes and diferencias_dom:
        nuevas_diferencias.extend(diferencias_dom)

    return nuevas_diferencias


def comparar_archivos(
    nombre_archivo: str,
    ruta_erp: str,
    ruta_sat: str,
) -> ResultadoArchivo:
    """
    Compara un par de archivos XML usando diff de texto y análisis DOM.

    Args:
        nombre_archivo: Nombre del archivo (sin ruta) para identificación.
        ruta_erp: Ruta completa al archivo XML en la carpeta ERP.
        ruta_sat: Ruta completa al archivo XML en la carpeta SAT.

    Returns:
        ResultadoArchivo con el estado y todas las diferencias encontradas.
    """
    contenido_erp, lineas_erp = _leer_archivo(ruta_erp)
    contenido_sat, lineas_sat = _leer_archivo(ruta_sat)

    diferencias_texto, opcodes = _comparar_texto(lineas_erp, lineas_sat)
    diferencias_finales = _comparar_xml_dom(
        contenido_erp, contenido_sat, diferencias_texto
    )

    estado = EstadoArchivo.IGUAL if not diferencias_finales else EstadoArchivo.DIFERENTE

    return ResultadoArchivo(
        nombre_archivo=nombre_archivo,
        estado=estado,
        diferencias=diferencias_finales,
        lineas_erp=lineas_erp,
        lineas_sat=lineas_sat,
        opcodes_diff=opcodes,
    )


def _imprimir_cabecera(
    ruta_erp: str,
    ruta_sat: str,
    cant_erp: int,
    cant_sat: int,
    total: int,
) -> None:
    """
    Imprime en consola el encabezado del proceso de comparación.

    Args:
        ruta_erp: Ruta a la carpeta ERP.
        ruta_sat: Ruta a la carpeta SAT.
        cant_erp: Número de archivos XML en ERP.
        cant_sat: Número de archivos XML en SAT.
        total: Total de archivos a procesar.
    """
    separador = "=" * 60
    print(f"\n{separador}")
    print("  Comparador de CFDIs — ERP vs SAT")
    print(separador)
    print(f"  Carpeta ERP : {os.path.abspath(ruta_erp)}")
    print(f"  Carpeta SAT : {os.path.abspath(ruta_sat)}")
    print(f"  Archivos ERP: {cant_erp}")
    print(f"  Archivos SAT: {cant_sat}")
    print(f"  Total a procesar: {total}")
    print(f"{separador}\n")


def _imprimir_resumen(resultado_global: ResultadoComparacion) -> None:
    """
    Imprime en consola el resumen final de la comparación.

    Args:
        resultado_global: Objeto con todos los resultados de la comparación.
    """
    separador = "=" * 60
    print(f"\n{separador}")
    print("  RESUMEN FINAL")
    print(separador)
    print(f"  ✔  Iguales          : {resultado_global.total_iguales}")
    print(f"  ✘  Diferentes       : {resultado_global.total_diferentes}")
    print(f"  ⚠  Ausentes en ERP : {resultado_global.total_ausentes_erp}")
    print(f"  ⚠  Ausentes en SAT : {resultado_global.total_ausentes_sat}")
    print(f"{separador}\n")


def _procesar_archivo(
    nombre: str,
    indice: int,
    total: int,
    archivos_erp: set,
    archivos_sat: set,
    ruta_erp: str,
    ruta_sat: str,
) -> ResultadoArchivo:
    """
    Procesa e imprime el resultado de comparar un archivo individual.

    Args:
        nombre: Nombre del archivo XML a comparar.
        indice: Posición actual en la secuencia (1-basado).
        total: Total de archivos a procesar.
        archivos_erp: Conjunto de nombres de archivos en ERP.
        archivos_sat: Conjunto de nombres de archivos en SAT.
        ruta_erp: Ruta a la carpeta ERP.
        ruta_sat: Ruta a la carpeta SAT.

    Returns:
        ResultadoArchivo con el estado y diferencias del archivo procesado.
    """
    print(f"[{indice}/{total}] Comparando: {nombre}")
    en_erp = nombre in archivos_erp
    en_sat = nombre in archivos_sat

    if en_erp and not en_sat:
        print("  ⚠  AUSENTE EN SAT")
        return ResultadoArchivo(
            nombre_archivo=nombre, estado=EstadoArchivo.AUSENTE_EN_SAT
        )

    if en_sat and not en_erp:
        print("  ⚠  AUSENTE EN ERP")
        return ResultadoArchivo(
            nombre_archivo=nombre, estado=EstadoArchivo.AUSENTE_EN_ERP
        )

    ruta_archivo_erp = os.path.join(ruta_erp, nombre)
    ruta_archivo_sat = os.path.join(ruta_sat, nombre)
    resultado = comparar_archivos(nombre, ruta_archivo_erp, ruta_archivo_sat)

    if resultado.estado == EstadoArchivo.IGUAL:
        print("  ✔  IGUAL")
    else:
        print(f"  ✘  DIFERENTE ({resultado.cantidad_diferencias} diferencia(s))")
        for dif in resultado.diferencias[:5]:
            print(f"     → {dif}")
        if resultado.cantidad_diferencias > 5:
            restantes = resultado.cantidad_diferencias - 5
            print(
                f"     ... y {restantes} diferencia(s) más "
                "(ver reporte HTML para detalle completo)"
            )

    return resultado


def comparar_carpetas(
    ruta_erp: str,
    ruta_sat: str,
) -> ResultadoComparacion:
    """
    Compara todas las carpetas de CFDIs y retorna el resultado global.

    Itera sobre todos los archivos XML de ambas carpetas, emparejándolos
    por nombre de archivo, e imprime el progreso en tiempo real en consola.

    Args:
        ruta_erp: Ruta a la carpeta que contiene los XMLs del ERP.
        ruta_sat: Ruta a la carpeta que contiene los XMLs del SAT.

    Returns:
        ResultadoComparacion con todos los resultados por archivo.

    Raises:
        FileNotFoundError: Si alguna de las carpetas no existe.
        ValueError: Si ambas carpetas están vacías.
    """
    if not os.path.isdir(ruta_erp):
        raise FileNotFoundError(
            f"La carpeta ERP no existe o no es un directorio: '{ruta_erp}'"
        )
    if not os.path.isdir(ruta_sat):
        raise FileNotFoundError(
            f"La carpeta SAT no existe o no es un directorio: '{ruta_sat}'"
        )

    archivos_erp = {f.lower() for f in os.listdir(ruta_erp) if f.lower().endswith(".xml")}
    archivos_sat = {f.lower() for f in os.listdir(ruta_sat) if f.lower().endswith(".xml")}

    if not archivos_erp and not archivos_sat:
        raise ValueError(
            "Ambas carpetas están vacías. No hay archivos XML para comparar."
        )

    todos_los_archivos = sorted(archivos_erp | archivos_sat)
    total = len(todos_los_archivos)

    print(todos_los_archivos)

    _imprimir_cabecera(ruta_erp, ruta_sat, len(archivos_erp), len(archivos_sat), total)

    resultado_global = ResultadoComparacion(ruta_erp=ruta_erp, ruta_sat=ruta_sat)

    for indice, nombre in enumerate(todos_los_archivos, start=1):
        resultado = _procesar_archivo(
            nombre, indice, total, archivos_erp, archivos_sat, ruta_erp, ruta_sat
        )
        resultado_global.resultados.append(resultado)

    _imprimir_resumen(resultado_global)

    return resultado_global
