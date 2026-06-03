import os
import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
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
    _fuentes[nombre] = df
    return {"status": "success", "nombre": nombre, "rows": len(df), "cols": df.shape[1]}

@router.post("/database/load/{table_name}")
async def load_table(table_name: str):
    """Carga la tabla en la memoria local como DataFrame"""
    if not _config_pg:
        raise HTTPException(status_code=400, detail="No hay conexión activa a PostgreSQL")
    try:
        df = _cargador.cargar_desde_sql(_config_pg, table_name)
        nombre = f"PG:{_config_pg['database']}.{table_name}"
        _fuentes[nombre] = df
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
        _fuentes[nombre] = df
        return {"status": "success", "message": f"Colección '{collection}' aplanada y cargada a memoria", "source_name": nombre}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Sube un archivo local y lo carga en Pandas"""
    try:
        content = await file.read()
        import io
        
        nombre = file.filename
        if nombre.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif nombre.endswith(".tsv"):
            df = pd.read_csv(io.BytesIO(content), sep='\t')
        elif nombre.endswith(".json"):
            import json
            datos = json.loads(content.decode("utf-8"))
            if isinstance(datos, list):
                df = pd.json_normalize(datos)
            else:
                df = pd.json_normalize([datos])
        else:
            raise HTTPException(status_code=400, detail="Formato no soportado")
            
        _fuentes[nombre] = df
        return {"status": "success", "message": f"Archivo {nombre} cargado", "rows": len(df), "cols": len(df.columns)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/eda/{source_name:path}")
async def run_eda(source_name: str):
    """Ejecuta el Análisis Exploratorio sobre una fuente cargada"""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
        
    df = _fuentes[source_name]
    analizador = AnalizadorExploratorio(df)
    
    try:
        # Reutilizando AnalizadorExploratorio
        resumen = analizador.resumen_general()
        desc_df = analizador.estadisticas_descriptivas()
        
        # Convertir desc_df a dict seguro para JSON
        desc_dict = {}
        if not desc_df.empty:
            import numpy as np
            desc_df = desc_df.T
            # Reemplazar NaN e inf por None para JSON
            desc_df = desc_df.replace([np.inf, -np.inf], None).replace({pd.NA: None, np.nan: None})
            desc_dict = desc_df.to_dict(orient="index")
            
        nulos = analizador.detectar_nulos()
        
        # Tipos de datos para visualización
        from src.preprocesamiento import Preprocesador
        prep = Preprocesador(df)
        tipos_col = prep.detectar_tipos_columna()
        
        outliers_info = {}
        for col in tipos_col.get("numericas", []):
            atipicos = analizador.detectar_atipicos(col)
            outliers_info[col] = len(atipicos)
            
        dist_categoricas = {}
        for col in tipos_col.get("categoricas", []):
            dist = analizador.distribucion_por_categoria(col)
            dist_categoricas[col] = dist
            
        return {
            "source": source_name,
            "dimensions": {"rows": resumen["total_registros"], "cols": resumen["total_columnas"]},
            "nulls": nulos,
            "descriptive": desc_dict,
            "outliers": outliers_info,
            "categorical": dist_categoricas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            _fuentes[saved_name] = df
            
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
