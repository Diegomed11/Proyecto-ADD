"""
Módulo de ETL — limpieza general de DataFrames.

Aplica una serie de transformaciones configurables que cubren la mayoría
de casos típicos de datos sucios (duplicados, nulos, outliers, tipos
incorrectos, espacios en texto, nombres inconsistentes…).

Es agnóstico al origen: funciona igual con CSVs, resultados SQL o tablas
extraídas por scraping. Devuelve siempre un DataFrame nuevo + un log
detallado de qué se hizo, para que el usuario sepa exactamente cómo
quedaron sus datos.

Función principal:
    limpiar(df, opciones) -> dict con {df, log, antes, despues}
"""

import re
from typing import Dict, Any, List

import numpy as np
import pandas as pd


# ── Opciones por defecto (limpieza "general" que rara vez hace daño) ─────────
DEFAULTS: Dict[str, Any] = {
    "remove_duplicates": True,      # quitar filas duplicadas exactas
    "drop_constant": True,          # quitar columnas con un solo valor
    "trim_text": True,              # quitar espacios al principio/fin de texto
    "coerce_types": True,           # detectar números/fechas en columnas de texto
    "standardize_names": False,     # nombres a snake_case (opt-in: cambia el contrato)

    # Estrategia de nulos: 'none' | 'drop_cols' | 'fill' | 'drop_rows'
    "null_strategy": "drop_cols",
    "null_threshold": 0.5,          # >50% de nulos en una columna -> se descarta
    "null_fill_numeric": "median",  # 'mean' | 'median' | 'zero'
    "null_fill_categorical": "mode",  # 'mode' | 'unknown'

    "remove_outliers": False,       # IQR — destructivo, opt-in
    "drop_columns": [],             # nombres concretos que el usuario quiera quitar
}


def limpiar(df: pd.DataFrame, opciones: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Aplica una limpieza configurable a un DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Datos originales (no se modifican; se trabaja sobre una copia).
    opciones : dict
        Opciones de limpieza (se mezcla con DEFAULTS).

    Returns
    -------
    dict
        {
            'df': DataFrame limpio,
            'log': [{'paso', 'detalle', 'afectado'}, ...],
            'antes': {'filas', 'columnas', 'nulos', 'duplicados'},
            'despues': {'filas', 'columnas', 'nulos', 'duplicados'},
        }
    """
    cfg = {**DEFAULTS, **(opciones or {})}
    df_out = df.copy()
    log: List[Dict[str, Any]] = []
    antes = _stats(df_out)

    # 1. Normalizar nombres de columna (snake_case, sin acentos en espacios)
    if cfg["standardize_names"]:
        viejos = df_out.columns.tolist()
        nuevos = [_norm_nombre(c) for c in viejos]
        # Resolver duplicados con sufijo numérico
        nuevos = _dedup_lista(nuevos)
        cambios = sum(1 for a, b in zip(viejos, nuevos) if a != b)
        df_out.columns = nuevos
        if cambios:
            log.append({"paso": "Nombres de columnas",
                        "detalle": f"Normalizadas {cambios} columnas a minúsculas con guion_bajo.",
                        "afectado": cambios})

    # 2. Quitar espacios sobrantes en columnas de texto
    if cfg["trim_text"]:
        total = 0
        for c in df_out.select_dtypes(include=["object"]).columns:
            antes_s = df_out[c]
            # Sólo trim a valores no nulos
            trimmed = antes_s.astype(str).str.strip()
            # Volver a poner NaN donde antes había NaN
            trimmed = trimmed.where(antes_s.notna(), antes_s)
            cambios = int((antes_s.fillna("").astype(str) != trimmed.fillna("")).sum())
            df_out[c] = trimmed
            total += cambios
        if total:
            log.append({"paso": "Espacios en texto",
                        "detalle": f"Eliminados espacios sobrantes en {total} celdas.",
                        "afectado": total})

    # 3. Detectar tipos reales (texto que en realidad es número o fecha)
    if cfg["coerce_types"]:
        convertidas = []
        for c in df_out.select_dtypes(include=["object"]).columns:
            serie = df_out[c]
            no_nulos = serie.notna().sum()
            if no_nulos == 0:
                continue
            # ¿Numérica?
            num = pd.to_numeric(serie, errors="coerce")
            if num.notna().sum() / no_nulos >= 0.9:
                df_out[c] = num
                convertidas.append(f"{c} -> número")
                continue
            # ¿Fecha?
            try:
                fec = pd.to_datetime(serie, errors="coerce", format="mixed")
            except (ValueError, TypeError):
                fec = pd.to_datetime(serie, errors="coerce")
            if fec.notna().sum() / no_nulos >= 0.9:
                df_out[c] = fec
                convertidas.append(f"{c} -> fecha")
        if convertidas:
            muestra = ", ".join(convertidas[:3]) + ("…" if len(convertidas) > 3 else "")
            log.append({"paso": "Tipos de datos",
                        "detalle": f"Convertidas {len(convertidas)} columna(s) a su tipo real ({muestra}).",
                        "afectado": len(convertidas)})

    # 4. Quitar columnas pedidas explícitamente por el usuario
    drop_cols = cfg.get("drop_columns") or []
    if drop_cols:
        # Si se normalizaron nombres, traducir los pedidos al nuevo nombre
        if cfg["standardize_names"]:
            drop_cols = [_norm_nombre(c) for c in drop_cols]
        existentes = [c for c in drop_cols if c in df_out.columns]
        if existentes:
            df_out = df_out.drop(columns=existentes)
            log.append({"paso": "Columnas eliminadas (a petición)",
                        "detalle": f"Eliminadas: {', '.join(existentes)}.",
                        "afectado": len(existentes)})

    # 5. Columnas constantes (un único valor o sólo nulos)
    if cfg["drop_constant"]:
        const = [c for c in df_out.columns if df_out[c].nunique(dropna=True) <= 1]
        if const:
            df_out = df_out.drop(columns=const)
            muestra = ", ".join(const[:3]) + ("…" if len(const) > 3 else "")
            log.append({"paso": "Columnas constantes",
                        "detalle": f"Eliminadas {len(const)} columna(s) con un solo valor ({muestra}).",
                        "afectado": len(const)})

    # 6. Estrategia de nulos
    null_strategy = cfg["null_strategy"]

    if null_strategy == "drop_cols":
        umbral = float(cfg["null_threshold"])
        n = len(df_out)
        if n:
            ratios = df_out.isnull().sum() / n
            alta = [c for c in df_out.columns if ratios[c] > umbral]
            if alta:
                df_out = df_out.drop(columns=alta)
                muestra = ", ".join(alta[:3]) + ("…" if len(alta) > 3 else "")
                log.append({"paso": "Columnas con muchos nulos",
                            "detalle": f"Eliminadas {len(alta)} columna(s) con >{int(umbral * 100)}% de valores faltantes ({muestra}).",
                            "afectado": len(alta)})
        # Tras descartar las peores, rellenamos el resto (mejor que dejar nulos)
        rellenos = _rellenar_nulos(df_out, cfg)
        if rellenos:
            log.append(rellenos)

    elif null_strategy == "fill":
        rellenos = _rellenar_nulos(df_out, cfg)
        if rellenos:
            log.append(rellenos)

    elif null_strategy == "drop_rows":
        n0 = len(df_out)
        df_out = df_out.dropna()
        eliminadas = n0 - len(df_out)
        if eliminadas:
            log.append({"paso": "Filas con nulos",
                        "detalle": f"Eliminadas {eliminadas} filas que tenían al menos un valor nulo.",
                        "afectado": eliminadas})

    # 7. Outliers (IQR) — destructivo, sólo si lo pide explícitamente
    if cfg["remove_outliers"]:
        n0 = len(df_out)
        mask = pd.Series(True, index=df_out.index)
        for c in df_out.select_dtypes(include=[np.number]).columns:
            s = df_out[c]
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0 or pd.isna(iqr):
                continue
            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            mask &= ((s >= low) & (s <= high)) | s.isna()
        df_out = df_out[mask]
        eliminadas = n0 - len(df_out)
        if eliminadas:
            log.append({"paso": "Valores atípicos",
                        "detalle": f"Eliminadas {eliminadas} filas con outliers (método IQR · k=1.5).",
                        "afectado": eliminadas})

    # 8. Duplicados al FINAL (después de coerciones y trims, así sí se detectan)
    if cfg["remove_duplicates"]:
        n0 = len(df_out)
        df_out = df_out.drop_duplicates().reset_index(drop=True)
        eliminadas = n0 - len(df_out)
        if eliminadas:
            log.append({"paso": "Filas duplicadas",
                        "detalle": f"Eliminadas {eliminadas} filas exactamente repetidas.",
                        "afectado": eliminadas})

    return {"df": df_out, "log": log, "antes": antes, "despues": _stats(df_out)}


# ─────────────────────────── helpers internos ───────────────────────────────


def _stats(df: pd.DataFrame) -> Dict[str, int]:
    """Resumen rápido del estado de un DataFrame (para mostrar antes/después)."""
    return {
        "filas": int(len(df)),
        "columnas": int(len(df.columns)),
        "nulos": int(df.isnull().sum().sum()),
        "duplicados": int(df.duplicated().sum()),
    }


def _norm_nombre(nombre: str) -> str:
    """Convierte un nombre de columna a snake_case ASCII."""
    s = str(nombre).strip().lower()
    # Reemplazos básicos para no perder semántica con acentos
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n"), ("ü", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "col"


def _dedup_lista(lst: List[str]) -> List[str]:
    """Garantiza nombres únicos añadiendo sufijo _2, _3… donde haga falta."""
    vistos: Dict[str, int] = {}
    salida = []
    for x in lst:
        if x not in vistos:
            vistos[x] = 1
            salida.append(x)
        else:
            vistos[x] += 1
            salida.append(f"{x}_{vistos[x]}")
    return salida


def _rellenar_nulos(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rellena nulos in-place según la estrategia configurada.
    Devuelve una entrada de log (o {} si no rellenó nada).
    """
    fill_num = cfg["null_fill_numeric"]
    fill_cat = cfg["null_fill_categorical"]
    rellenados = 0

    for c in df.columns:
        n_nulos = int(df[c].isnull().sum())
        if n_nulos == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            if fill_num == "mean":
                val = df[c].mean()
            elif fill_num == "zero":
                val = 0
            else:  # median (por defecto, robusto a outliers)
                val = df[c].median()
            if pd.notna(val):
                df[c] = df[c].fillna(val)
                rellenados += n_nulos
        else:
            if fill_cat == "mode":
                modas = df[c].mode(dropna=True)
                val = modas.iloc[0] if len(modas) else "desconocido"
            else:
                val = "desconocido"
            df[c] = df[c].fillna(val)
            rellenados += n_nulos

    if not rellenados:
        return {}
    return {"paso": "Valores faltantes rellenados",
            "detalle": (f"Rellenados {rellenados} valores nulos "
                        f"(números: {fill_num}, texto: {fill_cat})."),
            "afectado": rellenados}
