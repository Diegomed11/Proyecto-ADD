import os
import json
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import pandas as pd

from src.carga_datos import CargadorDatos, SimuladorNoSQL, WebScraper
from src.analisis_eda import AnalizadorExploratorio

router = APIRouter()

# Estado global en memoria para guardar las fuentes de datos cargadas
# En producción esto se manejaría con bases de datos o caché (Redis), pero para 
# una herramienta local tipo Jupyter, el estado en memoria es suficiente.
_fuentes: Dict[str, pd.DataFrame] = {}
_config_pg = None
_cargador = CargadorDatos()

# Texto de la última página extraída (lo usan los modelos de NLP de la pestaña web)
_scrape_cache: Dict[str, Any] = {"url": None, "texto": "", "html_excerpt": ""}

class PGConnection(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password: str

class MongoConnection(BaseModel):
    uri: str
    database: str

@router.get("/sources")
async def get_sources():
    """Devuelve la lista de fuentes cargadas en memoria"""
    sources_info = []
    for nombre, df in _fuentes.items():
        # Calcular un tamaño aproximado
        size_bytes = df.memory_usage(deep=True).sum()
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB"
            
        # Determinar el tipo basado en el nombre
        tipo = "CSV"
        if nombre.endswith(".tsv"): tipo = "TSV"
        elif nombre.endswith(".json"): tipo = "JSON"
        elif nombre.startswith("PG:"): tipo = "SQL"
        elif nombre.startswith("Query:"): tipo = "SQL"
        elif nombre.startswith(("NoSQL:", "Mongo:")): tipo = "NoSQL"
        elif nombre.startswith("Web:"): tipo = "Web"
        elif nombre.startswith("Limpio:"): tipo = "ETL"

        sources_info.append({
            "name": nombre,
            "type": tipo,
            "rows": len(df),
            "cols": len(df.columns),
            "size": size_str,
            "status": "Ready"
        })
    return {"sources": sources_info}

@router.delete("/sources/{source_name:path}")
async def delete_source(source_name: str):
    """Elimina una fuente de memoria"""
    if source_name in _fuentes:
        del _fuentes[source_name]
        return {"status": "success", "message": f"Fuente {source_name} eliminada"}
    raise HTTPException(status_code=404, detail="Fuente no encontrada")

@router.post("/connect_db")
async def connect_db(config: PGConnection):
    """Prueba la conexión a la base de datos y guarda las credenciales"""
    global _config_pg
    try:
        conf_dict = config.dict()
        tablas = _cargador.listar_tablas_sql(conf_dict)
        _config_pg = conf_dict
        return {"status": "success", "message": f"Conectado a {config.database}", "tables_count": len(tablas)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/database/tables")
async def list_tables():
    """Lista las tablas de la BD configurada actualmente"""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL")
    try:
        tablas = _cargador.listar_tablas_sql(_config_pg)
        
        tables_info = []
        for tabla in tablas:
            # Obtenemos info ligera (conteo puede ser lento, lo ignoramos para la vista general o lo hacemos condicional)
            tables_info.append({"name": tabla})
            
        return {"tables": tables_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/schema/{table_name}")
async def get_schema(table_name: str):
    """Devuelve el esquema y un preview de 5 filas de una tabla"""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL")
    try:
        columnas = _cargador.obtener_esquema_tabla(_config_pg, table_name)
        pks = _cargador.obtener_primary_keys(_config_pg, table_name)
        
        cols_info = []
        for col in columnas:
            col_name, data_type, is_nullable, col_default = col
            cols_info.append({
                "name": col_name,
                "type": data_type,
                "nullable": True if is_nullable == "YES" else False,
                "is_pk": col_name in pks
            })
            
        # Intentar obtener un preview
        df = _cargador.cargar_desde_sql(_config_pg, table_name)
        preview_data = df.head(10).to_dict(orient="records")
        total_rows = len(df)
        
        return {
            "table": table_name,
            "columns": cols_info,
            "preview": preview_data,
            "total_rows": total_rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QueryRequest(BaseModel):
    sql: str

@router.post("/database/query")
async def run_query(req: QueryRequest):
    """Ejecuta una consulta SQL contra la base PostgreSQL conectada."""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL. Conéctate en la pestaña Bases de datos.")
    sql = (req.sql or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Escribe una consulta SQL.")
    try:
        resultado = _cargador.ejecutar_consulta(_config_pg, sql)
        return {"status": "success", **resultado}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class QuerySaveRequest(BaseModel):
    sql: str
    nombre: Optional[str] = None

@router.post("/database/query/save")
async def save_query(req: QuerySaveRequest):
    """Ejecuta un SELECT y guarda el resultado en memoria como fuente reutilizable."""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL.")
    sql = (req.sql or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Escribe una consulta SQL.")
    try:
        df = _cargador.consulta_a_dataframe(_config_pg, sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Solo se pueden guardar consultas SELECT válidas: {e}")
    if df.shape[1] == 0:
        raise HTTPException(status_code=400, detail="La consulta no devolvió columnas para guardar.")

    base = (req.nombre or "").strip() or f"resultado_{len(_fuentes) + 1}"
    nombre = base if base.startswith("Query:") else f"Query:{base}"
    _guardar_fuente(nombre, df)
    return {"status": "success", "nombre": nombre, "rows": len(df), "cols": df.shape[1]}

@router.post("/database/load/{table_name}")
async def load_table(table_name: str):
    """Carga la tabla en la memoria local como DataFrame"""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL")
    try:
        df = _cargador.cargar_desde_sql(_config_pg, table_name)
        nombre = f"PG:{_config_pg['database']}.{table_name}"
        _guardar_fuente(nombre, df)
        return {"status": "success", "message": f"Tabla {table_name} cargada", "source_name": nombre}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mongo/connect")
async def connect_mongo(req: MongoConnection):
    """Conecta a un cluster de MongoDB y lista sus colecciones."""
    cargador = CargadorDatos()
    try:
        colecciones = cargador.listar_colecciones_mongo(req.uri, req.database)
        return {"status": "success", "message": "Conectado a MongoDB", "collections": colecciones}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mongo/load/{collection}")
async def load_mongo(req: MongoConnection, collection: str):
    """Carga una colección NoSQL y la aplana en un DataFrame estructurado."""
    cargador = CargadorDatos()
    try:
        df = cargador.cargar_desde_mongo(req.uri, req.database, collection)
        nombre = f"Mongo:{req.database}.{collection}"
        _guardar_fuente(nombre, df)
        return {"status": "success", "message": f"Colección '{collection}' aplanada y cargada a memoria", "source_name": nombre}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Límites de seguridad (evitan agotar la RAM en un servidor pequeño / EC2).
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
MAX_ROWS = int(os.environ.get("MAX_ROWS", "100000"))
MAX_COLS = int(os.environ.get("MAX_COLS", "1000"))
MAX_FUENTES = int(os.environ.get("MAX_FUENTES", "25"))


def _verificar_capacidad_fuentes():
    """Evita que la memoria crezca sin límite por demasiadas fuentes cargadas."""
    if len(_fuentes) >= MAX_FUENTES:
        raise HTTPException(
            status_code=429,
            detail=f"Se alcanzó el límite de {MAX_FUENTES} fuentes en memoria. "
                   f"Elimina alguna antes de añadir más.",
        )


def _guardar_fuente(nombre, df):
    """Guarda una fuente respetando el límite de capacidad. Si la fuente ya
    existe (sobrescritura) no cuenta como nueva."""
    if nombre not in _fuentes:
        _verificar_capacidad_fuentes()
    _fuentes[nombre] = df


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Sube un archivo local y lo carga en Pandas"""
    try:
        _verificar_capacidad_fuentes()
        content = await file.read()
        import io

        # Límite de tamaño: rechazamos archivos demasiado grandes antes de parsear.
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_UPLOAD_MB:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo pesa {size_mb:.1f} MB y supera el límite de {MAX_UPLOAD_MB} MB.",
            )
        if not content:
            raise HTTPException(status_code=400, detail="El archivo está vacío.")

        nombre = file.filename or "archivo"
        nombre_lower = nombre.lower()
        if nombre_lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif nombre_lower.endswith(".tsv"):
            df = pd.read_csv(io.BytesIO(content), sep='\t')
        elif nombre_lower.endswith(".json"):
            import json
            datos = json.loads(content.decode("utf-8"))
            if isinstance(datos, list):
                df = pd.json_normalize(datos)
            else:
                df = pd.json_normalize([datos])
        else:
            raise HTTPException(status_code=400, detail="Formato no soportado. Usa CSV, TSV o JSON.")

        if df.empty:
            raise HTTPException(status_code=400, detail="El archivo no contiene datos legibles.")

        # Tope de columnas: un CSV con miles de columnas puede disparar la RAM.
        if len(df.columns) > MAX_COLS:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo tiene {len(df.columns)} columnas y supera el límite de {MAX_COLS}.",
            )

        # Tope de filas: si excede, recortamos y avisamos (mantiene la RAM acotada).
        truncado = False
        if len(df) > MAX_ROWS:
            df = df.head(MAX_ROWS)
            truncado = True

        _guardar_fuente(nombre, df)
        mensaje = f"Archivo {nombre} cargado"
        if truncado:
            mensaje += f" (recortado a las primeras {MAX_ROWS:,} filas)"
        return {
            "status": "success",
            "message": mensaje,
            "rows": len(df),
            "cols": len(df.columns),
            "truncado": truncado,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _construir_eda(df, source_name):
    """Calcula el EDA completo (función síncrona pensada para correr en un hilo)."""
    import numpy as np
    from src.preprocesamiento import Preprocesador

    analizador = AnalizadorExploratorio(df)
    tipos_col = Preprocesador(df).detectar_tipos_columna()

    # En secuencia (cada cálculo ya usa todos los núcleos vía BLAS). El endpoint
    # ejecuta toda esta función en un hilo aparte para no bloquear el servidor.
    resumen = analizador.resumen_general()
    desc_df = analizador.estadisticas_descriptivas()
    nulos = analizador.detectar_nulos()
    correlacion = analizador.matriz_correlacion()
    observaciones = analizador.observaciones()

    desc_dict = {}
    if not desc_df.empty:
        desc_df = desc_df.T
        desc_df = desc_df.replace([np.inf, -np.inf], None).replace({pd.NA: None, np.nan: None})
        desc_dict = desc_df.to_dict(orient="index")

    outliers_info = {col: len(analizador.detectar_atipicos(col))
                     for col in tipos_col.get("numericas", [])}
    dist_categoricas = {col: analizador.distribucion_por_categoria(col)
                        for col in tipos_col.get("categoricas", [])}
    duplicados = analizador.filas_duplicadas()

    return {
        "source": source_name,
        "dimensions": {"rows": resumen["total_registros"], "cols": resumen["total_columnas"]},
        "nulls": nulos,
        "descriptive": desc_dict,
        "outliers": outliers_info,
        "categorical": dist_categoricas,
        "correlation": correlacion,
        "duplicates": duplicados,
        "observations": observaciones,
    }


@router.post("/eda/{source_name:path}")
async def run_eda(source_name: str):
    """Ejecuta el Análisis Exploratorio sobre una fuente cargada"""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    try:
        return await asyncio.to_thread(_construir_eda, _fuentes[source_name], source_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ───────────────────── ETL · Limpieza de fuentes ────────────────────────────


class EtlRequest(BaseModel):
    """Opciones de limpieza ETL. Todas son opcionales con valores por defecto."""
    remove_duplicates: bool = True
    drop_constant: bool = True
    trim_text: bool = True
    coerce_types: bool = True
    standardize_names: bool = False
    null_strategy: str = "drop_cols"  # 'none' | 'drop_cols' | 'fill' | 'drop_rows'
    null_threshold: float = 0.5
    null_fill_numeric: str = "median"
    null_fill_categorical: str = "mode"
    remove_outliers: bool = False
    drop_columns: List[str] = []


def _df_a_filas_seguras(df: pd.DataFrame, n: int = 20):
    """Serializa las primeras n filas de un DataFrame de forma segura para JSON."""
    import numpy as np
    sub = df.head(n).copy()
    # Convertir fechas a string ISO para no perder formato en el JSON
    for c in sub.columns:
        if pd.api.types.is_datetime64_any_dtype(sub[c]):
            sub[c] = sub[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    # Reemplazar NaN/inf por None
    sub = sub.replace([np.inf, -np.inf], None)
    sub = sub.astype(object).where(pd.notna(sub), None)
    return list(sub.columns), sub.values.tolist()


@router.post("/etl/preview/{source_name:path}")
async def etl_preview(source_name: str, req: EtlRequest):
    """Aplica la limpieza en memoria y devuelve resumen + muestra (NO guarda)."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    try:
        from src.etl import limpiar
        res = limpiar(_fuentes[source_name], req.dict())
        cols, filas = _df_a_filas_seguras(res["df"], n=20)
        return {
            "antes": res["antes"],
            "despues": res["despues"],
            "log": res["log"],
            "preview_cols": cols,
            "preview_rows": filas,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la limpieza: {e}")


@router.post("/etl/apply/{source_name:path}")
async def etl_apply(source_name: str, req: EtlRequest):
    """Aplica la limpieza y guarda el resultado como nueva fuente 'Limpio:<nombre>'."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    try:
        from src.etl import limpiar
        res = limpiar(_fuentes[source_name], req.dict())

        # Nombre limpio sin prefijos previos (PG:foo -> foo) para evitar Limpio:PG:foo
        base = source_name.split(":", 1)[1] if ":" in source_name else source_name
        # Si la base ya terminaba en una extensión típica, la quitamos para el nuevo nombre
        for ext in (".csv", ".tsv", ".json"):
            if base.lower().endswith(ext):
                base = base[: -len(ext)]
                break
        nuevo = f"Limpio:{base}"
        i = 2
        while nuevo in _fuentes:
            nuevo = f"Limpio:{base}_{i}"
            i += 1

        _guardar_fuente(nuevo, res["df"])
        return {
            "status": "success",
            "nombre": nuevo,
            "antes": res["antes"],
            "despues": res["despues"],
            "log": res["log"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")


@router.get("/etl/columns/{source_name:path}")
async def etl_columns(source_name: str):
    """Devuelve la lista de columnas (para el selector de 'columnas a eliminar')."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    df = _fuentes[source_name]
    return {"columnas": list(df.columns), "n_filas": len(df)}


# ───────────────────── Visualizaciones interactivas (Plotly) ────────────────

# Paleta alineada con el tema claro (teal primario + apoyos).
_PLOT_COLORWAY = ["#0e766b", "#2a9d8f", "#d6764a", "#9bbf2f", "#5f9a93",
                  "#33a791", "#e0a458", "#8a7fd0"]


def _aplicar_tema(fig, titulo: str = ""):
    """Aplica el tema claro 'glass' de la app a una figura de Plotly."""
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=14, color="#16302d")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#51706b", family="Geist, system-ui, sans-serif", size=12),
        colorway=_PLOT_COLORWAY,
        margin=dict(l=55, r=25, t=45, b=45),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#51706b")),
        xaxis=dict(gridcolor="rgba(22,48,45,0.08)", zerolinecolor="rgba(22,48,45,0.16)"),
        yaxis=dict(gridcolor="rgba(22,48,45,0.08)", zerolinecolor="rgba(22,48,45,0.16)"),
    )
    return fig


class VizRequest(BaseModel):
    kind: str            # 'hist' | 'box' | 'scatter' | 'bar' | 'heatmap'
    x: Optional[str] = None
    y: Optional[str] = None


@router.post("/viz/{source_name:path}")
async def viz(source_name: str, req: VizRequest):
    """Genera una figura de Plotly (JSON) lista para renderizar en el cliente."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    try:
        import json as _json
        import plotly.graph_objects as go
    except ImportError:
        raise HTTPException(status_code=500, detail="Plotly no está instalado en el servidor.")

    df = _fuentes[source_name]
    kind = (req.kind or "").lower()

    try:
        if kind == "hist":
            if not req.x or req.x not in df.columns:
                raise HTTPException(status_code=400, detail="Elige una columna numérica.")
            serie = pd.to_numeric(df[req.x], errors="coerce").dropna()
            fig = go.Figure(go.Histogram(x=serie, marker_color="#F59E0B", nbinsx=30))
            _aplicar_tema(fig, f"Distribución de {req.x}")
            fig.update_layout(xaxis_title=req.x, yaxis_title="frecuencia", bargap=0.05)

        elif kind == "box":
            if not req.x or req.x not in df.columns:
                raise HTTPException(status_code=400, detail="Elige una columna numérica.")
            ser_x = pd.to_numeric(df[req.x], errors="coerce")
            fig = go.Figure()
            if req.y and req.y in df.columns and not pd.api.types.is_numeric_dtype(df[req.y]):
                # Una caja por categoría (máx. 12 grupos para legibilidad)
                grupos = df[req.y].astype(str)
                top = grupos.value_counts().head(12).index
                for g in top:
                    fig.add_trace(go.Box(y=ser_x[grupos == g], name=str(g)))
                fig.update_layout(yaxis_title=req.x, xaxis_title=req.y, showlegend=False)
                titulo = f"{req.x} por {req.y}"
            else:
                fig.add_trace(go.Box(y=ser_x.dropna(), name=req.x, marker_color="#F59E0B"))
                fig.update_layout(yaxis_title=req.x, showlegend=False)
                titulo = f"Caja de {req.x}"
            _aplicar_tema(fig, titulo)

        elif kind == "scatter":
            if not req.x or not req.y or req.x not in df.columns or req.y not in df.columns:
                raise HTTPException(status_code=400, detail="Elige dos columnas numéricas (X e Y).")
            sx = pd.to_numeric(df[req.x], errors="coerce")
            sy = pd.to_numeric(df[req.y], errors="coerce")
            m = sx.notna() & sy.notna()
            fig = go.Figure(go.Scattergl(
                x=sx[m], y=sy[m], mode="markers",
                marker=dict(color="#F59E0B", size=6, opacity=0.6,
                            line=dict(width=0.5, color="rgba(255,255,255,0.2)")),
            ))
            _aplicar_tema(fig, f"{req.y} vs {req.x}")
            fig.update_layout(xaxis_title=req.x, yaxis_title=req.y)

        elif kind == "bar":
            if not req.x or req.x not in df.columns:
                raise HTTPException(status_code=400, detail="Elige una columna categórica.")
            conteo = df[req.x].astype(str).value_counts().head(15)
            fig = go.Figure(go.Bar(x=conteo.values[::-1], y=conteo.index[::-1].astype(str),
                                   orientation="h", marker_color="#F59E0B"))
            _aplicar_tema(fig, f"Frecuencia de {req.x} (top 15)")
            fig.update_layout(xaxis_title="conteo", yaxis_title=req.x)

        elif kind == "heatmap":
            from src.analisis_eda import AnalizadorExploratorio
            corr = AnalizadorExploratorio(df).matriz_correlacion()
            if len(corr["columnas"]) < 2:
                raise HTTPException(status_code=400, detail="Se necesitan al menos 2 columnas numéricas.")
            # Escala divergente: coral (negativa) -> claro (0) -> teal (positiva).
            fig = go.Figure(go.Heatmap(
                z=corr["matriz"], x=corr["columnas"], y=corr["columnas"],
                colorscale=[[0, "#d6764a"], [0.5, "#f3f8f6"], [1, "#0e766b"]],
                zmid=0, zmin=-1, zmax=1,
                colorbar=dict(title="r", tickfont=dict(color="#51706b")),
            ))
            _aplicar_tema(fig, "Matriz de correlación")

        else:
            raise HTTPException(status_code=400, detail=f"Tipo de gráfico no soportado: '{kind}'.")

        return {"figure": _json.loads(fig.to_json())}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el gráfico: {e}")


@router.get("/viz/columns/{source_name:path}")
async def viz_columns(source_name: str):
    """Columnas separadas por tipo, para poblar los selectores de gráficos."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    from src.preprocesamiento import Preprocesador
    tipos = Preprocesador(_fuentes[source_name]).detectar_tipos_columna()
    return {
        "numericas": tipos.get("numericas", []),
        "categoricas": tipos.get("categoricas", []) + tipos.get("texto_libre", []),
    }


# ───────────────────── Reporte automático (1 clic) ──────────────────────────


def _detectar_objetivo(df, tipos):
    """Heurística para elegir un objetivo razonable para el modelado automático."""
    n = len(df)
    numericas = tipos.get("numericas", [])
    categoricas = tipos.get("categoricas", [])

    # Clasificación: categórica con 2..15 clases y que no sea un identificador
    cand_clf = []
    for c in categoricas:
        u = df[c].nunique(dropna=True)
        if 2 <= u <= 15 and u < n:
            cand_clf.append((c, u))
    if cand_clf:
        cand_clf.sort(key=lambda t: t[1])  # menos clases = más aprendible
        return cand_clf[0][0], "clasificacion"

    # Regresión: numérica continua (muchos valores distintos, no constante)
    cand_reg = []
    for c in numericas:
        u = df[c].nunique(dropna=True)
        if u > 15:
            cand_reg.append((c, df[c].var()))
    if cand_reg:
        cand_reg.sort(key=lambda t: (t[1] if t[1] == t[1] else 0), reverse=True)
        return cand_reg[0][0], "regresion"

    return None, None


def _metrica_principal(resultado):
    """Extrae (label, valor_texto, valor_num) de la métrica destacada de un modelo."""
    for m in resultado.get("metricas", []):
        if m.get("destacado"):
            txt = str(m["valor"])
            try:
                num = float(txt.replace("%", "").strip())
            except ValueError:
                num = 0.0
            return m["label"], txt, num
    return "—", "—", 0.0


def _correlaciones_top(analizador, n: int = 5):
    """Extrae los n pares de columnas con mayor correlación absoluta."""
    corr = analizador.matriz_correlacion()
    cols = corr["columnas"]
    pares = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pares.append({"a": cols[i], "b": cols[j], "valor": corr["matriz"][i][j]})
    pares.sort(key=lambda d: abs(d["valor"]), reverse=True)
    return pares[:n]


def _modelado_auto(df, tipos):
    """Detecta un objetivo y entrena/compara los modelos candidatos EN PARALELO."""
    from src.modelado import Modelador

    modelado = {"disponible": False, "motivo": ""}
    df_modelo = df.sample(5000, random_state=42) if len(df) > 5000 else df
    objetivo, tipo_obj = _detectar_objetivo(df_modelo, tipos)

    # Sin objetivo claro → clustering no supervisado (un solo modelo)
    if objetivo is None:
        feats = (tipos.get("numericas", []) + tipos.get("categoricas", []))[:10]
        if not feats:
            return {"disponible": False, "motivo": "No hay columnas utilizables para modelar."}
        res = Modelador(df_modelo).entrenar_ml("kmeans", feats, None, {"k": 3})
        lbl, val, _ = _metrica_principal(res)
        return {"disponible": True, "objetivo": None, "tipo": "clustering",
                "comparacion": [{"nombre": res["modelo_nombre"], "metrica": lbl,
                                 "valor": val, "interpretacion": res["interpretacion"]}],
                "recomendado": res["modelo_nombre"]}

    feats = [c for c in (tipos.get("numericas", []) + tipos.get("categoricas", []))
             if c != objetivo][:10]
    if not feats:
        return {"disponible": False, "motivo": "No hay variables de entrada disponibles."}

    candidatos = ["logistic", "tree"] if tipo_obj == "clasificacion" else ["linear", "tree"]

    # NOTA: se entrena en secuencia A PROPÓSITO. sklearn/numpy ya reparten cada
    # .fit() entre todos los núcleos vía BLAS; añadir hilos de Python encima
    # provoca sobre-suscripción y lo vuelve ~20x más lento (medido). El
    # paralelismo útil aquí es entre peticiones (asyncio.to_thread en el endpoint).
    comparacion = []
    for mname in candidatos:
        try:
            res = Modelador(df_modelo).entrenar_ml(mname, feats, objetivo, {})
            lbl, val, num = _metrica_principal(res)
            comparacion.append({"nombre": res["modelo_nombre"], "metrica": lbl, "valor": val,
                                "_num": num, "interpretacion": res["interpretacion"]})
        except Exception:
            continue

    if not comparacion:
        return {"disponible": False, "motivo": "Ningún modelo pudo entrenarse con estos datos."}

    comparacion.sort(key=lambda d: d["_num"], reverse=True)
    recomendado = comparacion[0]["nombre"]
    for d in comparacion:
        d.pop("_num", None)
    return {"disponible": True, "objetivo": objetivo, "tipo": tipo_obj,
            "features": feats, "comparacion": comparacion, "recomendado": recomendado}


def _construir_reporte(df, source_name):
    """Construye el reporte ejecutando sus secciones independientes EN PARALELO."""
    from src.analisis_eda import AnalizadorExploratorio
    from src.preprocesamiento import Preprocesador
    from src import etl as etl_mod

    analizador = AnalizadorExploratorio(df)
    tipos = Preprocesador(df).detectar_tipos_columna()

    # Secciones calculadas en secuencia: cada una es muy rápida (<0.1 s) y ya
    # está paralelizada internamente por numpy/sklearn (BLAS). Todo este bloque
    # corre en un hilo aparte (asyncio.to_thread) para no bloquear el servidor.
    calidad = analizador.calidad_datos()
    observaciones = analizador.observaciones()
    corr_top = _correlaciones_top(analizador, 5)
    limpieza = etl_mod.limpiar(df, etl_mod.DEFAULTS)
    try:
        modelado = _modelado_auto(df, tipos)
    except Exception as e:
        modelado = {"disponible": False, "motivo": f"No se pudo modelar: {e}"}

    return {
        "source": source_name,
        "dimensions": {"rows": int(len(df)), "cols": int(len(df.columns))},
        "tipos": {k: tipos.get(k, []) for k in ("numericas", "categoricas", "fechas", "texto_libre")},
        "calidad": calidad,
        "observaciones": observaciones,
        "correlaciones_top": corr_top,
        "limpieza_sugerida": {"antes": limpieza["antes"], "despues": limpieza["despues"],
                              "log": limpieza["log"]},
        "modelado": modelado,
    }


@router.get("/report/{source_name:path}")
async def report(source_name: str):
    """Orquesta un informe completo de una fuente: calidad, EDA, limpieza y modelado."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    df = _fuentes[source_name]
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="La fuente no tiene filas.")

    try:
        # Trabajo pesado fuera del event loop → el servidor sigue respondiendo.
        return await asyncio.to_thread(_construir_reporte, df, source_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el reporte: {e}")


@router.post("/report/export")
async def report_export(payload: Dict[str, Any] = Body(...), formato: str = "pdf"):
    """Exporta un reporte (recibido como JSON) a DOCX o PDF para descargar."""
    fmt = (formato or "pdf").lower()
    if fmt not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Formato no soportado (usa 'pdf' o 'docx').")
    try:
        from src import reporte_export as rx
        if fmt == "docx":
            data = await asyncio.to_thread(rx.to_docx, payload)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            data = await asyncio.to_thread(rx.to_pdf, payload)
            media = "application/pdf"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el documento: {e}")

    base = str(payload.get("source", "informe"))
    safe = "".join(ch if ch.isalnum() else "_" for ch in base) or "informe"
    headers = {"Content-Disposition": f'attachment; filename="informe_{safe}.{fmt}"'}
    return Response(content=data, media_type=media, headers=headers)


# ───────────────────────────────────────────────────────────────────────────


class ScrapeRequest(BaseModel):
    url: str

@router.post("/scrape")
async def run_scraping(req: ScrapeRequest):
    """Ejecuta Web Scraping en la URL proporcionada"""
    try:
        scraper = WebScraper()
        scraper.establecer_url(req.url)
        extracto = scraper.obtener_extracto_html(1500)
        tablas = scraper.extraer_tablas()

        # Cachear el texto limpio para los modelos de NLP (pestaña de análisis)
        texto = scraper.obtener_texto_limpio(4000)
        _scrape_cache["url"] = req.url
        _scrape_cache["texto"] = texto
        _scrape_cache["html_excerpt"] = extracto

        tablas_validas = []
        for i, t in enumerate(tablas):
            if len(t) >= 3 and len(t.columns) >= 2:
                tablas_validas.append(i)
                
        # Guardar la primera tabla válida automáticamente en memoria
        saved_name = None
        preview_data = []
        cols = []
        if tablas_validas:
            df = scraper.obtener_tabla(tablas_validas[0])
            import os
            import numpy as np
            base_name = os.path.basename(req.url).split('?')[0] or "web_data"
            saved_name = f"Web:{base_name}_t{tablas_validas[0]}"
            _guardar_fuente(saved_name, df)
            
            df_safe = df.replace([np.inf, -np.inf], None).replace({pd.NA: None, float("nan"): None})
            preview_data = df_safe.head(5).to_dict(orient="records")
            cols = list(df_safe.columns)
            
        return {
            "status": "success",
            "url": req.url,
            "html_excerpt": extracto,
            "tables_found": len(tablas),
            "valid_tables": len(tablas_validas),
            "saved_source": saved_name,
            "preview_cols": cols,
            "preview_data": preview_data,
            "texto_chars": len(texto)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Modelos de NLP (Transformers / BERT) sobre la página extraída ──────

@router.get("/nlp/catalog")
async def nlp_catalog():
    """Catálogo de modelos de NLP disponibles para el menú del frontend."""
    from src.nlp_modelos import MODELOS_NLP
    return {"status": "success", "modelos": MODELOS_NLP}

class NlpRequest(BaseModel):
    tarea: str
    opciones: Optional[Dict[str, Any]] = None

@router.post("/nlp/analyze")
async def nlp_analyze(req: NlpRequest):
    """Ejecuta el modelo transformer elegido sobre el texto de la última página extraída."""
    texto = _scrape_cache.get("texto", "")
    if not texto:
        raise HTTPException(
            status_code=400,
            detail="Primero extrae una página en la sección de arriba."
        )

    from src import nlp_modelos
    try:
        resultado = nlp_modelos.analizar(req.tarea, texto, req.opciones or {})
        return {
            "status": "success",
            "modelo": nlp_modelos.MODELOS_NLP[req.tarea]["nombre"],
            "url": _scrape_cache.get("url"),
            "resultado": resultado,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el análisis NLP: {e}")

@router.get("/models/catalog")
async def get_model_catalog():
    """Devuelve el catálogo de modelos disponibles para el menú del frontend."""
    from src.modelado import Modelador
    return {"status": "success", "modelos": Modelador.MODELOS}

@router.get("/models/features/{source_name:path}")
async def get_model_features(source_name: str):
    """Devuelve las columnas disponibles (numéricas y categóricas) para modelado."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    df = _fuentes[source_name]
    from src.preprocesamiento import Preprocesador
    prep = Preprocesador(df)
    tipos = prep.detectar_tipos_columna()

    numericas = tipos.get("numericas", [])
    categoricas = tipos.get("categoricas", [])

    return {
        "status": "success",
        "numericas": numericas,
        "categoricas": categoricas,
        "todas": numericas + categoricas,
        "n_filas": int(len(df)),
    }

class TrainRequest(BaseModel):
    source: str
    modelo: str = "linear"
    features: List[str] = []
    target: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

@router.post("/models/train")
async def train_model(req: TrainRequest):
    """Entrena el modelo de ML elegido (lineal, logística, árbol o k-means)."""
    if req.source not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")

    df = _fuentes[req.source]
    from src.modelado import Modelador
    modelador = Modelador(df)

    try:
        resultado = modelador.entrenar_ml(req.modelo, req.features, req.target, req.params or {})
        return {"status": "success", "resultado": resultado}
    except ValueError as e:
        # Errores de validación / datos insuficientes → 400 con mensaje claro
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al entrenar el modelo: {e}")
