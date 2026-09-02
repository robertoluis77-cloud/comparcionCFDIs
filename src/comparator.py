"""
Módulo de comparación exhaustiva de archivos XML (CFDIs del SAT México).

Compara la estructura XML nodo por nodo (DOM) para detectar diferencias
semánticas reales entre dos carpetas, independientemente del formato,
indentación o distribución en líneas de los archivos.
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



def _nodos_son_equivalentes(
    nodo_a: etree._Element,  # type: ignore[name-defined]
    nodo_b: etree._Element,  # type: ignore[name-defined]
) -> bool:
    """
    Compara estructuralmente dos nodos XML de forma recursiva (sin generar diferencias).

    Devuelve ``True`` si ambos nodos son idénticos en tag, atributos, texto directo
    y todos sus descendientes, sin importar el orden en que aparecen dentro del
    conjunto de nodos hermanos de su padre.  Se usa para el emparejamiento
    tolerante al orden en ``_comparar_nodos``.

    Args:
        nodo_a: Primer nodo a comparar.
        nodo_b: Segundo nodo a comparar.

    Returns:
        ``True`` si los nodos son estructuralmente equivalentes; ``False`` en caso contrario.
    """
    if nodo_a.tag != nodo_b.tag:
        return False
    if dict(nodo_a.attrib) != dict(nodo_b.attrib):
        return False
    if (nodo_a.text or "").strip() != (nodo_b.text or "").strip():
        return False
    hijos_a = list(nodo_a)
    hijos_b = list(nodo_b)
    if len(hijos_a) != len(hijos_b):
        return False
    return all(_nodos_son_equivalentes(ha, hb) for ha, hb in zip(hijos_a, hijos_b))


def _emparejar_hijos(
    hijos_erp: list,
    hijos_sat: list,
) -> List[Tuple]:
    """
    Empareja hijos ERP con hijos SAT tolerando diferencias de orden.

    Para cada hijo ERP busca, en orden, el primer hijo SAT no emparejado que sea
    estructuralmente equivalente (mismo tag, atributos, texto e hijos de forma
    recursiva).  Si lo encuentra, los empareja y ambos quedan "consumidos".
    Si no, empareja posicionalmente con el hijo SAT de la misma posición (si
    existe), para que las diferencias reales de contenido se reporten con
    normalidad.

    Returns:
        Lista de tuplas ``(hijo_erp | None, hijo_sat | None)`` listas para
        ser procesadas por ``_comparar_nodos``.
    """
    usados_sat: List[bool] = [False] * len(hijos_sat)
    pares: List[Tuple] = []

    # Primera pasada: emparejamiento por equivalencia estructural
    indices_erp_sin_par: List[int] = []
    for hijo_erp in hijos_erp:
        encontrado = False
        for j, hijo_sat in enumerate(hijos_sat):
            if not usados_sat[j] and _nodos_son_equivalentes(hijo_erp, hijo_sat):
                pares.append((hijo_erp, hijo_sat))
                usados_sat[j] = True
                encontrado = True
                break
        if not encontrado:
            indices_erp_sin_par.append(len(pares))
            pares.append((hijo_erp, None))  # placeholder; se resuelve abajo

    # Segunda pasada: asignar hijos SAT sobrantes a los ERP sin par (posicionalmente)
    hijos_sat_sobrantes = [h for idx, h in enumerate(hijos_sat) if not usados_sat[idx]]
    ptr = 0
    for idx_par in indices_erp_sin_par:
        hijo_erp_sin_par, _ = pares[idx_par]
        if ptr < len(hijos_sat_sobrantes):
            pares[idx_par] = (hijo_erp_sin_par, hijos_sat_sobrantes[ptr])
            ptr += 1

    # Hijos SAT sobrantes que no tuvieron par en ERP
    for hijo_sat in hijos_sat_sobrantes[ptr:]:
        pares.append((None, hijo_sat))

    return pares


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


def _tag_local(nodo: etree._Element) -> str:  # type: ignore[name-defined]
    """Devuelve el nombre local del tag sin namespace."""
    return nodo.tag.split("}")[-1] if "}" in nodo.tag else nodo.tag


def _diferencia_nodo_extra(
    nodo: etree._Element,  # type: ignore[name-defined]
    es_erp: bool,
    ruta_padre: str,
) -> DiferenciaDetalle:
    """
    Construye un ``DiferenciaDetalle`` para un nodo sin contraparte.

    Args:
        nodo: Nodo sin par en el árbol opuesto.
        es_erp: ``True`` si el nodo pertenece al árbol ERP; ``False`` si es SAT.
        ruta_padre: Ruta XPath del nodo padre.

    Returns:
        ``DiferenciaDetalle`` indicando el nodo extra.
    """
    tag = _tag_local(nodo)
    if es_erp:
        return DiferenciaDetalle(
            numero_linea_erp=nodo.sourceline,
            numero_linea_sat=None,
            contenido_erp=f"<{tag}> (extra en ERP)",
            contenido_sat="<ausente>",
            tipo=f"nodo extra en ERP en {ruta_padre}",
        )
    return DiferenciaDetalle(
        numero_linea_erp=None,
        numero_linea_sat=nodo.sourceline,
        contenido_erp="<ausente>",
        contenido_sat=f"<{tag}> (extra en SAT)",
        tipo=f"nodo extra en SAT en {ruta_padre}",
    )


def _comparar_nodos(
    nodo_erp: etree._Element,  # type: ignore[name-defined]
    nodo_sat: etree._Element,  # type: ignore[name-defined]
    ruta_xpath: str,
) -> List[DiferenciaDetalle]:
    """
    Compara recursivamente dos nodos XML y sus descendientes.

    El emparejamiento de nodos hijos es tolerante al orden: si un hijo ERP tiene
    un gemelo estructuralmente idéntico en SAT (mismo tag, atributos, texto e
    hijos de forma recursiva), se emparejan sin importar su posición relativa
    dentro del conjunto de hermanos.  Solo se reporta una diferencia cuando no
    existe ningún nodo equivalente con el cual emparejar.

    Args:
        nodo_erp: Nodo del árbol DOM del archivo ERP.
        nodo_sat: Nodo del árbol DOM del archivo SAT.
        ruta_xpath: Ruta XPath acumulada para identificar la posición.

    Returns:
        Lista de diferencias encontradas en los nodos y sus hijos.
    """
    diferencias: List[DiferenciaDetalle] = []
    ruta_actual = f"{ruta_xpath}/{_tag_local(nodo_erp)}" if ruta_xpath else _tag_local(nodo_erp)

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

    pares = _emparejar_hijos(list(nodo_erp), list(nodo_sat))
    for idx, (hijo_erp, hijo_sat) in enumerate(pares):
        if hijo_erp is not None and hijo_sat is not None:
            diferencias.extend(_comparar_nodos(hijo_erp, hijo_sat, f"{ruta_actual}[{idx}]"))
        elif hijo_erp is not None:
            diferencias.append(_diferencia_nodo_extra(hijo_erp, True, ruta_actual))
        else:
            diferencias.append(
                _diferencia_nodo_extra(hijo_sat, False, ruta_actual)  # type: ignore[arg-type]
            )

    return diferencias


def _limpiar_texto_blanco(nodo: etree._Element) -> None:  # type: ignore[name-defined]
    """
    Elimina texto que sea exclusivamente espacios en blanco en todos los nodos del árbol.

    Recorre el árbol completo y asigna ``None`` al atributo ``text`` y ``tail``
    de cualquier nodo cuyo valor sea solo espacios, tabuladores o saltos de línea.
    Esto garantiza que nodos hoja sin contenido real se serialicen como elementos
    auto-cerrados (``<Tag/>``) en lugar de ``<Tag>\\n</Tag>``, evitando falsos
    positivos en la vista diff cuando ERP y SAT usan distintos formatos de cierre.

    Args:
        nodo: Raíz del árbol DOM a normalizar (modificado en sitio).
    """
    for elemento in nodo.iter():
        if elemento.text is not None and not elemento.text.strip():
            elemento.text = None
        if elemento.tail is not None and not elemento.tail.strip():
            elemento.tail = None


def _serializar_xml(nodo: etree._Element) -> List[str]:  # type: ignore[name-defined]
    """
    Serializa un árbol DOM como texto formateado con indentación uniforme.

    Produce líneas normalizadas que pueden usarse para la vista diff lado a lado
    en el reporte HTML, con independencia del formato original del archivo.

    Args:
        nodo: Raíz del árbol DOM a serializar.

    Returns:
        Lista de líneas del XML serializado con indentación de 2 espacios.
    """
    _limpiar_texto_blanco(nodo)
    etree.indent(nodo, space="  ")  # pylint: disable=c-extension-no-member
    serializado = etree.tostring(  # pylint: disable=c-extension-no-member
        nodo, encoding="unicode", pretty_print=True
    )
    return serializado.splitlines(keepends=True)


def _comparar_xml_dom(
    contenido_erp: str,
    contenido_sat: str,
) -> Tuple[List[DiferenciaDetalle], List[str], List[str], List[Tuple]]:
    """
    Compara la estructura XML nodo por nodo (DOM) de forma agnóstica al formato.

    La decisión de igualdad o diferencia se basa únicamente en el contenido
    semántico del XML (nodos, atributos, valores), sin importar la distribución
    en líneas, indentación o espacios en blanco del archivo original.

    Para la vista diff del reporte HTML se generan representaciones normalizadas
    de ambos árboles con indentación uniforme.

    Args:
        contenido_erp: Contenido completo del XML del ERP (texto Unicode).
        contenido_sat: Contenido completo del XML del SAT (texto Unicode).

    Returns:
        Tupla con (diferencias_dom, lineas_erp_norm, lineas_sat_norm, opcodes_diff).
    """
    try:  # pylint: disable=c-extension-no-member
        raiz_erp = etree.fromstring(contenido_erp.encode("utf-8"))
        raiz_sat = etree.fromstring(contenido_sat.encode("utf-8"))
    except etree.XMLSyntaxError as exc:  # pylint: disable=c-extension-no-member
        error = DiferenciaDetalle(
            numero_linea_erp=None,
            numero_linea_sat=None,
            contenido_erp="",
            contenido_sat="",
            tipo=f"Error de sintaxis XML: {exc}",
        )
        return [error], [], [], []

    _limpiar_texto_blanco(raiz_erp)
    _limpiar_texto_blanco(raiz_sat)

    diferencias_dom = _comparar_nodos(raiz_erp, raiz_sat, "")

    lineas_erp_norm = _serializar_xml(raiz_erp)
    lineas_sat_norm = _serializar_xml(raiz_sat)

    matcher = difflib.SequenceMatcher(
        None, lineas_erp_norm, lineas_sat_norm, autojunk=False
    )
    opcodes = matcher.get_opcodes()

    return diferencias_dom, lineas_erp_norm, lineas_sat_norm, opcodes


def comparar_archivos(
    nombre_archivo: str,
    ruta_erp: str,
    ruta_sat: str,
) -> ResultadoArchivo:
    """
    Compara un par de archivos XML usando comparación nodo por nodo (DOM).

    La igualdad se determina exclusivamente por el contenido semántico del XML
    (nodos, atributos y valores), sin considerar el formato textual del archivo.
    Para la vista diff del reporte HTML se usan representaciones normalizadas.

    Args:
        nombre_archivo: Nombre del archivo (sin ruta) para identificación.
        ruta_erp: Ruta completa al archivo XML en la carpeta ERP.
        ruta_sat: Ruta completa al archivo XML en la carpeta SAT.

    Returns:
        ResultadoArchivo con el estado y todas las diferencias encontradas.
    """
    contenido_erp, _ = _leer_archivo(ruta_erp)
    contenido_sat, _ = _leer_archivo(ruta_sat)

    diferencias, lineas_erp_norm, lineas_sat_norm, opcodes = _comparar_xml_dom(
        contenido_erp, contenido_sat
    )

    estado = EstadoArchivo.IGUAL if not diferencias else EstadoArchivo.DIFERENTE

    return ResultadoArchivo(
        nombre_archivo=nombre_archivo,
        estado=estado,
        diferencias=diferencias,
        lineas_erp=lineas_erp_norm,
        lineas_sat=lineas_sat_norm,
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


def _escanear_xmls(ruta_carpeta: str) -> dict:
    """
    Escanea recursivamente una carpeta y construye un mapa de nombre→ruta completa.

    La clave del diccionario es el nombre del archivo en minúsculas para permitir
    comparaciones insensibles a mayúsculas entre ERP (minúsculas) y SAT (mayúsculas).

    Args:
        ruta_carpeta: Ruta a la carpeta raíz a escanear.

    Returns:
        Diccionario ``{nombre_archivo_lower: ruta_absoluta}`` para cada .xml encontrado.
    """
    mapa: dict = {}
    for directorio, _, archivos in os.walk(ruta_carpeta):
        for archivo in archivos:
            if archivo.lower().endswith(".xml"):
                mapa[archivo.lower()] = os.path.join(directorio, archivo)
    return mapa


def _procesar_archivo(
    nombre: str,
    indice: int,
    total: int,
    mapa_erp: dict,
    mapa_sat: dict,
) -> ResultadoArchivo:
    """
    Procesa e imprime el resultado de comparar un archivo individual.

    Args:
        nombre: Nombre del archivo XML (en minúsculas) a comparar.
        indice: Posición actual en la secuencia (1-basado).
        total: Total de archivos a procesar.
        mapa_erp: Mapa ``{nombre_lower: ruta_completa}`` de archivos ERP.
        mapa_sat: Mapa ``{nombre_lower: ruta_completa}`` de archivos SAT.

    Returns:
        ResultadoArchivo con el estado y diferencias del archivo procesado.
    """
    print(f"[{indice}/{total}] Comparando: {nombre}")
    en_erp = nombre in mapa_erp
    en_sat = nombre in mapa_sat

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

    ruta_archivo_erp = mapa_erp[nombre]
    ruta_archivo_sat = mapa_sat[nombre]
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

    Escanea recursivamente ambas carpetas para encontrar archivos XML en
    cualquier nivel de profundidad, los empareja por nombre de archivo
    (insensible a mayúsculas) e imprime el progreso en tiempo real en consola.

    Args:
        ruta_erp: Ruta a la carpeta raíz que contiene los XMLs del ERP.
        ruta_sat: Ruta a la carpeta raíz que contiene los XMLs del SAT.

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

    mapa_erp = _escanear_xmls(ruta_erp)
    mapa_sat = _escanear_xmls(ruta_sat)

    if not mapa_erp and not mapa_sat:
        raise ValueError(
            "Ambas carpetas están vacías. No hay archivos XML para comparar."
        )

    todos_los_archivos = sorted(set(mapa_erp.keys()) | set(mapa_sat.keys()))
    total = len(todos_los_archivos)

    _imprimir_cabecera(ruta_erp, ruta_sat, len(mapa_erp), len(mapa_sat), total)

    resultado_global = ResultadoComparacion(ruta_erp=ruta_erp, ruta_sat=ruta_sat)

    for indice, nombre in enumerate(todos_los_archivos, start=1):
        resultado = _procesar_archivo(nombre, indice, total, mapa_erp, mapa_sat)
        resultado_global.resultados.append(resultado)

    _imprimir_resumen(resultado_global)

    return resultado_global
