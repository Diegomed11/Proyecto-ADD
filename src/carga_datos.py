"""
Módulo de carga y gestión de datos (Etapa 1 del pipeline).

Soporta carga desde archivos locales (CSV/TSV/JSON), desde URLs de API REST
y desde bases de datos SQL (SQLite).
Centraliza la lógica de entrada para que el resto del sistema reciba
siempre un pd.DataFrame independientemente del origen de los datos.

Clases:
    CargadorDatos: Carga datos desde archivo o URL y retorna un DataFrame.
"""

import pandas as pd
import requests
import psycopg2


class CargadorDatos:
    """
    Cargador centralizado de datos para el pipeline de Machine Learning.
    
    Esta clase maneja la ingestión de datos desde diversas fuentes
    (archivos locales, URLs, bases de datos SQL y NoSQL) unificando
    la salida en estructuras tabulares.

    Parameters
    ----------
    url_base : str, optional
        URL base para peticiones HTTP por defecto (default "").
    tiempo_espera : int, optional
        Tiempo máximo de espera (timeout) en segundos (default 10).

    Attributes
    ----------
    datos_crudos : dict
        Copia en memoria de la última carga (útil para JSON/REST).

    Notes
    -----
    Para conexiones MongoDB utilice `cargar_desde_mongo()`.
    """

    def __init__(self, url_base: str = "", tiempo_espera: int = 10):
        self.url_base = url_base
        self.tiempo_espera = tiempo_espera
        self.datos_crudos: dict = {}



    def cargar_desde_archivo(self, archivo) -> pd.DataFrame:

        nombre = archivo.name.lower()
        if nombre.endswith(".csv"):
            return self._leer_csv(archivo)
        elif nombre.endswith(".tsv"):
            return self._leer_tsv(archivo)
        elif nombre.endswith(".json"):
            return self._leer_json(archivo)
        else:
            raise ValueError(f"Formato no soportado: '{archivo.name}'. Use .csv, .tsv o .json.")

    def cargar_desde_ruta(self, ruta: str) -> pd.DataFrame:

        import os
        if not os.path.isfile(ruta):
            raise FileNotFoundError(f"No se encontró el archivo: '{ruta}'")

        ruta_lower = ruta.lower()
        if ruta_lower.endswith(".csv"):
            return pd.read_csv(ruta)
        elif ruta_lower.endswith(".tsv"):
            return pd.read_csv(ruta, sep='\t')
        elif ruta_lower.endswith(".json"):
            import json
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            self.datos_crudos = datos if isinstance(datos, dict) else {"items": datos}
            if isinstance(datos, list):
                return pd.json_normalize(datos)
            elif isinstance(datos, dict):
                for key, value in datos.items():
                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                        return pd.json_normalize(value)
                return pd.json_normalize([datos])
            else:
                raise ValueError("El JSON debe ser una lista de objetos o un objeto único.")
        else:
            raise ValueError(f"Formato no soportado: '{ruta}'. Use .csv, .tsv o .json.")

    def cargar_desde_url(self, url: str) -> pd.DataFrame:

        try:
            respuesta = requests.get(url, timeout=self.tiempo_espera)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"No se pudo conectar a '{url}': {e}") from e
        except requests.exceptions.Timeout as e:
            raise ConnectionError(f"Tiempo de espera agotado al conectar a '{url}'.") from e

        self._manejar_error(respuesta)

        try:
            datos = respuesta.json()
        except requests.exceptions.JSONDecodeError as e:
            raise ValueError(f"La respuesta de '{url}' no es JSON válido.") from e

        # Almacenar datos crudos
        self.datos_crudos = datos if isinstance(datos, dict) else {"items": datos}

        if isinstance(datos, list):
            return pd.json_normalize(datos)
        elif isinstance(datos, dict):
            # Buscar listas anidadas en el diccionario (patrón común en APIs de NASA)
            for key, value in datos.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    return pd.json_normalize(value)
            return pd.json_normalize([datos])
        else:
            raise ValueError("La respuesta JSON debe ser una lista de objetos o un objeto.")

  
    def obtener_datos_api(self) -> list:
        """
        Obtiene datos desde la URL base configurada.

        Equivalente genérico de obtener_datos_lanzamientos() del UML.

        Returns
        -------
        list
            Lista de registros obtenidos de la API.
        """
        if not self.url_base:
            raise ValueError("No se ha configurado una url_base.")
        df = self.cargar_desde_url(self.url_base)
        return df.to_dict(orient="records")

    def obtener_datos_secundarios(self, url: str) -> list:
        """
        Obtiene datos desde una URL secundaria.

        Equivalente genérico de obtener_datos_cohetes() del UML.

        Parameters
        ----------
        url : str
            URL del endpoint secundario.

        Returns
        -------
        list
            Lista de registros obtenidos.
        """
        df = self.cargar_desde_url(url)
        return df.to_dict(orient="records")


    def _conectar_postgres(self, config: dict):
        return psycopg2.connect(
            host=config.get("host", "localhost"),
            port=config.get("port", 5432),
            database=config["database"],
            user=config["user"],
            password=config.get("password", "")
        )

    def listar_tablas_sql(self, config: dict) -> list:
        conn = self._conectar_postgres(config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name;"
        )
        tablas = [fila[0] for fila in cursor.fetchall()]
        cursor.close()
        conn.close()
        return tablas

    def cargar_desde_sql(self, config: dict, tabla: str) -> pd.DataFrame:
        tablas_disponibles = self.listar_tablas_sql(config)
        if tabla not in tablas_disponibles:
            raise ValueError(
                f"La tabla '{tabla}' no existe. "
                f"Tablas disponibles: {tablas_disponibles}"
            )
        conn = self._conectar_postgres(config)
        df = pd.read_sql_query(f'SELECT * FROM "{tabla}"', conn)
        conn.close()
        return df

    def obtener_esquema_tabla(self, config: dict, tabla: str) -> list:
        conn = self._conectar_postgres(config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position;",
            (tabla,)
        )
        columnas = cursor.fetchall()
        cursor.close()
        conn.close()
        return columnas

    def obtener_primary_keys(self, config: dict, tabla: str) -> list:
        conn = self._conectar_postgres(config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.table_schema = 'public' "
            "AND tc.table_name = %s "
            "AND tc.constraint_type = 'PRIMARY KEY';",
            (tabla,)
        )
        pks = [fila[0] for fila in cursor.fetchall()]
        cursor.close()
        conn.close()
        return pks

    def ejecutar_consulta(self, config: dict, sql: str, limite: int = 500) -> dict:
        """
        Ejecuta una consulta SQL arbitraria contra la base conectada.

        Para SELECT devuelve columnas y filas (hasta `limite`); para comandos
        (INSERT/UPDATE/DELETE/DDL) devuelve el número de filas afectadas.

        Returns
        -------
        dict
            {'tipo': 'select', 'columnas': [...], 'filas': [[...]], 'n': int}
            o {'tipo': 'comando', 'afectadas': int}.
        """
        def _safe(v):
            if v is None or isinstance(v, (int, float, bool, str)):
                return v
            return str(v)

        conn = self._conectar_postgres(config)
        try:
            cur = conn.cursor()
            cur.execute(sql)
            if cur.description:  # hay conjunto de resultados (SELECT, RETURNING, ...)
                columnas = [d[0] for d in cur.description]
                filas = [[_safe(c) for c in fila] for fila in cur.fetchmany(limite)]
                conn.commit()
                return {"tipo": "select", "columnas": columnas, "filas": filas, "n": len(filas)}
            else:
                afectadas = cur.rowcount
                conn.commit()
                return {"tipo": "comando", "afectadas": afectadas}
        finally:
            conn.close()

    def consulta_a_dataframe(self, config: dict, sql: str) -> pd.DataFrame:
        """
        Ejecuta un SELECT y devuelve el resultado como DataFrame con tipos reales
        (numéricos, fechas, etc.), apto para EDA y modelado.
        """
        conn = self._conectar_postgres(config)
        try:
            return pd.read_sql_query(sql, conn)
        finally:
            conn.close()

    def contar_registros(self, config: dict, tabla: str) -> int:
        conn = self._conectar_postgres(config)
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{tabla}"')
        total = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return total

    # ── Conexión MongoDB ────────────────────────────────────────────

    def listar_colecciones_mongo(self, uri: str, db_name: str) -> list:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        return db.list_collection_names()

    def cargar_desde_mongo(self, uri: str, db_name: str, coleccion: str) -> pd.DataFrame:
        from pymongo import MongoClient
        client = MongoClient(uri)
        db = client[db_name]
        cursor = db[coleccion].find()
        datos = list(cursor)
        client.close()
        if not datos:
            return pd.DataFrame()
        for d in datos:
            if '_id' in d:
                d['_id'] = str(d['_id'])
        return pd.json_normalize(datos)

    # ── Lectores internos ────────────────────────────────────────────

    def _leer_csv(self, archivo) -> pd.DataFrame:
        """Lee un archivo CSV y retorna un DataFrame."""
        return pd.read_csv(archivo)

    def _leer_tsv(self, archivo) -> pd.DataFrame:
        """Lee un archivo TSV (tab-separated) y retorna un DataFrame."""
        return pd.read_csv(archivo, sep='\t')

    def _leer_json(self, archivo) -> pd.DataFrame:
        """Lee un archivo JSON y retorna un DataFrame normalizado."""
        import json
        datos = json.load(archivo)
        self.datos_crudos = datos if isinstance(datos, dict) else {"items": datos}
        if isinstance(datos, list):
            return pd.json_normalize(datos)
        elif isinstance(datos, dict):
            for key, value in datos.items():
                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    return pd.json_normalize(value)
            return pd.json_normalize([datos])
        else:
            raise ValueError("El JSON debe ser una lista de objetos o un objeto único.")

    def _manejar_error(self, respuesta) -> None:
        if respuesta.status_code == 404:
            raise ConnectionError(f"Recurso no encontrado (404): {respuesta.url}")
        elif respuesta.status_code == 401:
            raise ConnectionError(f"No autorizado (401): {respuesta.url}")
        elif respuesta.status_code == 403:
            raise ConnectionError(f"Acceso prohibido (403): {respuesta.url}")
        elif respuesta.status_code >= 500:
            raise ConnectionError(
                f"Error del servidor ({respuesta.status_code}): {respuesta.url}"
            )
        elif not respuesta.ok:
            raise ConnectionError(
                f"Error HTTP {respuesta.status_code}: {respuesta.url}"
            )


class SimuladorNoSQL:

    def __init__(self):
        self._colecciones = {}
        self._generar_datos()

    def _generar_datos(self):
        self._colecciones["estudiantes"] = [
            {"_id": 1, "nombre": "Carlos Mendoza", "edad": 21, "carrera": "Ingeniería en Sistemas",
             "contacto": {"email": "carlos.mendoza@uni.mx", "telefono": "3312345601"},
             "direccion": {"ciudad": "Guadalajara", "estado": "Jalisco"}},
            {"_id": 2, "nombre": "María López", "edad": 22, "carrera": "Ciencia de Datos",
             "contacto": {"email": "maria.lopez@uni.mx", "telefono": "3312345602"},
             "direccion": {"ciudad": "Zapopan", "estado": "Jalisco"}},
            {"_id": 3, "nombre": "Jorge Ramírez", "edad": 20, "carrera": "Telemática",
             "contacto": {"email": "jorge.ramirez@uni.mx", "telefono": "3312345603"},
             "direccion": {"ciudad": "Tlaquepaque", "estado": "Jalisco"}},
            {"_id": 4, "nombre": "Ana Torres", "edad": 23, "carrera": "Inteligencia Artificial",
             "contacto": {"email": "ana.torres@uni.mx", "telefono": "3312345604"},
             "direccion": {"ciudad": "Tonalá", "estado": "Jalisco"}},
            {"_id": 5, "nombre": "Luis García", "edad": 21, "carrera": "Ingeniería en Sistemas",
             "contacto": {"email": "luis.garcia@uni.mx", "telefono": "3312345605"},
             "direccion": {"ciudad": "Monterrey", "estado": "Nuevo León"}},
            {"_id": 6, "nombre": "Sofía Hernández", "edad": 19, "carrera": "Ciencia de Datos",
             "contacto": {"email": "sofia.hdz@uni.mx", "telefono": "3312345606"},
             "direccion": {"ciudad": "CDMX", "estado": "Ciudad de México"}},
            {"_id": 7, "nombre": "Diego Martínez", "edad": 24, "carrera": "Telemática",
             "contacto": {"email": "diego.mtz@uni.mx", "telefono": "3312345607"},
             "direccion": {"ciudad": "Puebla", "estado": "Puebla"}},
            {"_id": 8, "nombre": "Valentina Cruz", "edad": 20, "carrera": "Inteligencia Artificial",
             "contacto": {"email": "vale.cruz@uni.mx", "telefono": "3312345608"},
             "direccion": {"ciudad": "Querétaro", "estado": "Querétaro"}},
            {"_id": 9, "nombre": "Fernando Díaz", "edad": 22, "carrera": "Ingeniería en Sistemas",
             "contacto": {"email": "fer.diaz@uni.mx", "telefono": "3312345609"},
             "direccion": {"ciudad": "León", "estado": "Guanajuato"}},
            {"_id": 10, "nombre": "Camila Ruiz", "edad": 21, "carrera": "Ciencia de Datos",
             "contacto": {"email": "camila.ruiz@uni.mx", "telefono": "3312345610"},
             "direccion": {"ciudad": "Mérida", "estado": "Yucatán"}},
            {"_id": 11, "nombre": "Andrés Vega", "edad": 23, "carrera": "Telemática",
             "contacto": {"email": "andres.vega@uni.mx", "telefono": "3312345611"},
             "direccion": {"ciudad": "Guadalajara", "estado": "Jalisco"}},
            {"_id": 12, "nombre": "Isabella Morales", "edad": 20, "carrera": "Inteligencia Artificial",
             "contacto": {"email": "isa.morales@uni.mx", "telefono": "3312345612"},
             "direccion": {"ciudad": "Zapopan", "estado": "Jalisco"}},
        ]

        self._colecciones["cursos"] = [
            {"_id": 101, "nombre": "Bases de Datos Avanzadas", "creditos": 8, "profesor": "Dr. Pérez",
             "horario": {"dias": ["Lunes", "Miércoles"], "hora_inicio": "08:00", "hora_fin": "10:00"},
             "prerequisitos": ["Bases de Datos", "Programación"]},
            {"_id": 102, "nombre": "Machine Learning", "creditos": 9, "profesor": "Dra. Sánchez",
             "horario": {"dias": ["Martes", "Jueves"], "hora_inicio": "10:00", "hora_fin": "12:00"},
             "prerequisitos": ["Estadística", "Álgebra Lineal"]},
            {"_id": 103, "nombre": "Redes de Computadoras", "creditos": 7, "profesor": "Mtro. López",
             "horario": {"dias": ["Lunes", "Viernes"], "hora_inicio": "14:00", "hora_fin": "16:00"},
             "prerequisitos": ["Sistemas Operativos"]},
            {"_id": 104, "nombre": "Inteligencia Artificial", "creditos": 9, "profesor": "Dr. Rodríguez",
             "horario": {"dias": ["Miércoles", "Viernes"], "hora_inicio": "08:00", "hora_fin": "10:00"},
             "prerequisitos": ["Programación", "Estadística"]},
            {"_id": 105, "nombre": "Cálculo Multivariable", "creditos": 8, "profesor": "Dra. Gutiérrez",
             "horario": {"dias": ["Lunes", "Miércoles", "Viernes"], "hora_inicio": "12:00", "hora_fin": "13:00"},
             "prerequisitos": ["Cálculo Integral"]},
            {"_id": 106, "nombre": "Desarrollo Web", "creditos": 6, "profesor": "Mtro. Flores",
             "horario": {"dias": ["Martes", "Jueves"], "hora_inicio": "16:00", "hora_fin": "18:00"},
             "prerequisitos": ["Programación"]},
            {"_id": 107, "nombre": "Seguridad Informática", "creditos": 7, "profesor": "Dr. Navarro",
             "horario": {"dias": ["Lunes", "Jueves"], "hora_inicio": "10:00", "hora_fin": "12:00"},
             "prerequisitos": ["Redes de Computadoras"]},
            {"_id": 108, "nombre": "Procesamiento de Lenguaje Natural", "creditos": 8, "profesor": "Dra. Castro",
             "horario": {"dias": ["Martes", "Viernes"], "hora_inicio": "08:00", "hora_fin": "10:00"},
             "prerequisitos": ["Machine Learning"]},
            {"_id": 109, "nombre": "Big Data", "creditos": 9, "profesor": "Dr. Ramírez",
             "horario": {"dias": ["Miércoles", "Viernes"], "hora_inicio": "14:00", "hora_fin": "16:00"},
             "prerequisitos": ["Bases de Datos Avanzadas"]},
            {"_id": 110, "nombre": "Visión Computacional", "creditos": 8, "profesor": "Dra. Herrera",
             "horario": {"dias": ["Lunes", "Miércoles"], "hora_inicio": "16:00", "hora_fin": "18:00"},
             "prerequisitos": ["Machine Learning", "Álgebra Lineal"]},
        ]

        self._colecciones["inscripciones"] = [
            {"_id": 1001, "estudiante_id": 1, "curso_id": 101, "semestre": "2025-A", "calificacion": 92,
             "asistencia": {"total_clases": 30, "asistidas": 28}},
            {"_id": 1002, "estudiante_id": 2, "curso_id": 102, "semestre": "2025-A", "calificacion": 88,
             "asistencia": {"total_clases": 30, "asistidas": 27}},
            {"_id": 1003, "estudiante_id": 3, "curso_id": 103, "semestre": "2025-A", "calificacion": 75,
             "asistencia": {"total_clases": 30, "asistidas": 22}},
            {"_id": 1004, "estudiante_id": 4, "curso_id": 104, "semestre": "2025-A", "calificacion": 95,
             "asistencia": {"total_clases": 30, "asistidas": 30}},
            {"_id": 1005, "estudiante_id": 5, "curso_id": 105, "semestre": "2025-A", "calificacion": 68,
             "asistencia": {"total_clases": 30, "asistidas": 20}},
            {"_id": 1006, "estudiante_id": 6, "curso_id": 106, "semestre": "2025-A", "calificacion": 91,
             "asistencia": {"total_clases": 30, "asistidas": 29}},
            {"_id": 1007, "estudiante_id": 7, "curso_id": 107, "semestre": "2025-A", "calificacion": 83,
             "asistencia": {"total_clases": 30, "asistidas": 25}},
            {"_id": 1008, "estudiante_id": 8, "curso_id": 108, "semestre": "2025-B", "calificacion": 97,
             "asistencia": {"total_clases": 30, "asistidas": 30}},
            {"_id": 1009, "estudiante_id": 9, "curso_id": 109, "semestre": "2025-B", "calificacion": 72,
             "asistencia": {"total_clases": 30, "asistidas": 21}},
            {"_id": 1010, "estudiante_id": 10, "curso_id": 110, "semestre": "2025-B", "calificacion": 86,
             "asistencia": {"total_clases": 30, "asistidas": 26}},
            {"_id": 1011, "estudiante_id": 11, "curso_id": 101, "semestre": "2025-B", "calificacion": 79,
             "asistencia": {"total_clases": 30, "asistidas": 24}},
            {"_id": 1012, "estudiante_id": 12, "curso_id": 102, "semestre": "2025-B", "calificacion": 94,
             "asistencia": {"total_clases": 30, "asistidas": 29}},
            {"_id": 1013, "estudiante_id": 1, "curso_id": 104, "semestre": "2025-B", "calificacion": 90,
             "asistencia": {"total_clases": 30, "asistidas": 28}},
            {"_id": 1014, "estudiante_id": 3, "curso_id": 106, "semestre": "2025-B", "calificacion": 85,
             "asistencia": {"total_clases": 30, "asistidas": 26}},
            {"_id": 1015, "estudiante_id": 5, "curso_id": 102, "semestre": "2025-B", "calificacion": 77,
             "asistencia": {"total_clases": 30, "asistidas": 23}},
        ]

    def obtener_colecciones(self) -> dict:
        return self._colecciones

    def obtener_nombres_colecciones(self) -> list:
        return list(self._colecciones.keys())

    def coleccion_a_dataframe(self, nombre: str) -> pd.DataFrame:
        if nombre not in self._colecciones:
            raise ValueError(f"La colección '{nombre}' no existe.")
        return pd.json_normalize(self._colecciones[nombre])

    def resumen(self) -> dict:
        resultado = {}
        for nombre, documentos in self._colecciones.items():
            resultado[nombre] = {
                "total_documentos": len(documentos),
                "campos": list(documentos[0].keys()) if documentos else [],
            }
        return resultado


class WebScraper:

    def __init__(self, url: str = ""):
        self._url = url
        self._html_crudo = ""
        self._tablas = []

    def establecer_url(self, url: str):
        self._url = url

    def obtener_html(self) -> str:
        if not self._url:
            raise ValueError("No se ha establecido una URL.")
        respuesta = requests.get(self._url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if not respuesta.ok:
            raise ConnectionError(f"Error HTTP {respuesta.status_code}: {self._url}")
        self._html_crudo = respuesta.text
        return self._html_crudo

    def obtener_extracto_html(self, caracteres: int = 1500) -> str:
        if not self._html_crudo:
            self.obtener_html()
        return self._html_crudo[:caracteres]

    def extraer_tablas(self) -> list:
        if not self._html_crudo:
            self.obtener_html()
        try:
            import io
            self._tablas = pd.read_html(io.StringIO(self._html_crudo))
        except ValueError:
            self._tablas = []
        return self._tablas

    def obtener_texto_limpio(self, max_caracteres: int = 4000) -> str:
        """
        Extrae el texto plano de los párrafos (<p>) de la página, descartando
        fragmentos demasiado cortos (menús, pies, etc.).

        Parameters
        ----------
        max_caracteres : int
            Límite superior de longitud del texto devuelto.

        Returns
        -------
        str
            Texto limpio, listo para alimentar a un modelo de NLP.
        """
        if not self._html_crudo:
            self.obtener_html()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self._html_crudo, 'html.parser')
        parrafos = soup.find_all('p')
        texto_limpio = " ".join(
            p.get_text(strip=True) for p in parrafos if len(p.get_text(strip=True)) > 20
        )
        return texto_limpio[:max_caracteres]

    def extraer_texto_y_sentimiento(self) -> dict:
        if not self._html_crudo:
            self.obtener_html()

        texto_limpio = self.obtener_texto_limpio(2000)

        if not texto_limpio:
            return {"texto": "", "sentimiento": "N/A", "score": 0.0}
            
        try:
            import os
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            from transformers import pipeline
            # 'text-classification' es el nombre de tarea válido en transformers 4.x y 5.x
            # (el alias 'sentiment-analysis' se eliminó en 5.x).
            classifier = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english",
            )
            resultado = classifier(texto_limpio[:512], truncation=True)[0]
            
            return {
                "texto": texto_limpio[:500] + "...", 
                "sentimiento": resultado["label"], 
                "score": float(resultado["score"])
            }
        except Exception as e:
            return {"texto": texto_limpio[:500] + "...", "sentimiento": "Error", "score": 0.0, "error": str(e)}

    def obtener_tabla(self, indice: int = 0) -> pd.DataFrame:
        if not self._tablas:
            self.extraer_tablas()
        if indice < 0 or indice >= len(self._tablas):
            raise IndexError(f"Índice {indice} fuera de rango. Se encontraron {len(self._tablas)} tablas.")
        return self._tablas[indice]

    def total_tablas(self) -> int:
        if not self._tablas:
            self.extraer_tablas()
        return len(self._tablas)
