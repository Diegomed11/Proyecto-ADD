import os
import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Dict, Any, List
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
        elif nombre.startswith("NoSQL:"): tipo = "NoSQL"
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
        nlp_resultado = scraper.extraer_texto_y_sentimiento()
        
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
            "nlp": nlp_resultado
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/features/{source_name:path}")
async def get_model_features(source_name: str):
    """Devuelve las columnas numéricas disponibles para modelado."""
    if source_name not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    
    df = _fuentes[source_name]
    from src.preprocesamiento import Preprocesador
    prep = Preprocesador(df)
    tipos = prep.detectar_tipos_columna()
    
    return {"status": "success", "numericas": tipos.get("numericas", [])}

class TrainRequest(BaseModel):
    source: str
    col_x: str
    col_y: str

@router.post("/models/train")
async def train_model(req: TrainRequest):
    """Entrena un modelo de regresión lineal simple usando Scikit-Learn."""
    if req.source not in _fuentes:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
        
    df = _fuentes[req.source]
    from src.modelado import Modelador
    modelador = Modelador(df)
    
    try:
        modelador.entrenar_regresion_lineal(req.col_x, req.col_y)
        coefs = modelador.obtener_coeficientes()
        
        from sklearn.metrics import r2_score
        y_true = modelador.obtener_valores_reales()
        y_pred = modelador.obtener_predicciones()
        r2 = r2_score(y_true, y_pred)
        
        coefs["r2"] = float(r2)
        
        return {"status": "success", "metrics": coefs}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
