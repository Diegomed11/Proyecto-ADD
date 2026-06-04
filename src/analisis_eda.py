"""
Módulo de análisis exploratorio de datos — EDA (Etapa 2 del pipeline).

Genera estadísticas descriptivas, detecta valores nulos o atípicos,
y produce resúmenes que orientan las decisiones de preprocesamiento.

Clases:
    AnalizadorExploratorio: Realiza el análisis exploratorio de los datos.
"""

import pandas as pd
import numpy as np


class AnalizadorExploratorio:
    """
    Realiza el análisis exploratorio de datos (EDA).

    Comprende la estructura, distribución y características generales
    de los datos antes de procesarlos.

    Parameters
    ----------
    datos : pd.DataFrame
        DataFrame con los datos crudos a explorar.
    """

    def __init__(self, datos: pd.DataFrame):
        self._datos = datos

    def resumen_general(self) -> dict:
        """
        Genera un resumen general del dataset.

        Returns
        -------
        dict
            Contiene total de registros, columnas, tipos de datos y nulos.
        """
        return {
            "total_registros": len(self._datos),
            "total_columnas": len(self._datos.columns),
            "tipos_datos": self._datos.dtypes.astype(str).to_dict(),
            "total_nulos": int(self._datos.isnull().sum().sum()),
        }

    def estadisticas_descriptivas(self) -> pd.DataFrame:
        """
        Calcula estadísticas descriptivas (media, mediana, std, etc.).

        Returns
        -------
        pd.DataFrame
            Tabla con las estadísticas por columna numérica.
        """
        return self._datos.describe(include="all")

    def detectar_nulos(self) -> dict:
        """
        Identifica columnas con valores nulos y su porcentaje.

        Returns
        -------
        dict
            {columna: porcentaje_nulos} para columnas con nulos > 0.
        """
        total = len(self._datos)
        if total == 0:
            return {}
        nulos = self._datos.isnull().sum()
        nulos_pct = (nulos / total * 100).round(2)
        return {col: pct for col, pct in nulos_pct.items() if pct > 0}

    def detectar_atipicos(self, columna: str) -> list:
        """
        Detecta valores atípicos en una columna usando IQR.

        Parameters
        ----------
        columna : str
            Nombre de la columna a analizar.

        Returns
        -------
        list
            Valores identificados como atípicos.
        """
        serie = self._datos[columna].dropna()
        if not pd.api.types.is_numeric_dtype(serie):
            return []
        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1
        limite_inferior = q1 - 1.5 * iqr
        limite_superior = q3 + 1.5 * iqr
        atipicos = serie[(serie < limite_inferior) | (serie > limite_superior)]
        return atipicos.tolist()

    def distribucion_por_categoria(self, columna: str) -> dict:
        """
        Cuenta la frecuencia de cada categoría en una columna.

        Parameters
        ----------
        columna : str
            Nombre de la columna categórica.

        Returns
        -------
        dict
            {categoría: frecuencia}.
        """
        return self._datos[columna].value_counts().to_dict()

    def matriz_correlacion(self) -> dict:
        """
        Calcula la correlación de Pearson entre las columnas numéricas.

        Returns
        -------
        dict
            {'columnas': [...], 'matriz': [[...], ...]} con valores en [-1, 1]
            (o vacío si hay menos de 2 columnas numéricas).
        """
        num = self._datos.select_dtypes(include=[np.number])
        # Descartar columnas constantes (su correlación es indefinida -> NaN).
        num = num.loc[:, num.nunique(dropna=True) > 1]
        if num.shape[1] < 2:
            return {"columnas": [], "matriz": []}
        corr = num.corr(numeric_only=True).round(3)
        corr = corr.replace([np.inf, -np.inf], 0).fillna(0)
        return {
            "columnas": list(corr.columns),
            "matriz": corr.values.tolist(),
        }

    def filas_duplicadas(self) -> dict:
        """Cuenta filas completamente duplicadas."""
        n = int(self._datos.duplicated().sum())
        total = len(self._datos)
        pct = round(n / total * 100, 2) if total else 0.0
        return {"n": n, "pct": pct}

    def cardinalidad(self) -> dict:
        """Nº de valores únicos por columna (útil para detectar IDs y constantes)."""
        return {col: int(self._datos[col].nunique(dropna=True)) for col in self._datos.columns}

    def observaciones(self) -> list:
        """
        Genera hallazgos automáticos en lenguaje natural a partir del dataset.

        Returns
        -------
        list[dict]
            Cada hallazgo: {'nivel': 'info'|'warning'|'success', 'texto': str}.
        """
        obs = []
        total = len(self._datos)
        if total == 0:
            return [{"nivel": "warning", "texto": "El dataset no tiene filas."}]

        # Duplicados
        dup = self.filas_duplicadas()
        if dup["n"] > 0:
            obs.append({"nivel": "warning",
                        "texto": f"Hay {dup['n']} filas duplicadas ({dup['pct']}%). Considera eliminarlas."})

        # Nulos
        nulos = self.detectar_nulos()
        if nulos:
            peor = max(nulos.items(), key=lambda kv: kv[1])
            obs.append({"nivel": "warning",
                        "texto": f"«{peor[0]}» es la columna con más valores faltantes ({peor[1]}%). "
                                 f"{len(nulos)} columna(s) tienen nulos en total."})
        else:
            obs.append({"nivel": "success", "texto": "No hay valores faltantes: el dataset está completo."})

        # Columnas constantes y posibles identificadores
        card = self.cardinalidad()
        constantes = [c for c, u in card.items() if u <= 1]
        if constantes:
            obs.append({"nivel": "info",
                        "texto": f"Columna(s) con un solo valor (sin información útil): {', '.join(constantes[:5])}."})
        ids = [c for c, u in card.items() if u == total and total > 1]
        if ids:
            obs.append({"nivel": "info",
                        "texto": f"«{ids[0]}» parece un identificador único (un valor distinto por fila)."})

        # Correlaciones fuertes
        corr = self.matriz_correlacion()
        if corr["columnas"]:
            cols = corr["columnas"]
            mejor = None
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    v = corr["matriz"][i][j]
                    if mejor is None or abs(v) > abs(mejor[2]):
                        mejor = (cols[i], cols[j], v)
            if mejor and abs(mejor[2]) >= 0.7:
                signo = "positiva" if mejor[2] > 0 else "negativa"
                obs.append({"nivel": "info",
                            "texto": f"Correlación {signo} fuerte ({mejor[2]:+.2f}) entre «{mejor[0]}» y «{mejor[1]}»."})

        # Outliers
        num_cols = self._datos.select_dtypes(include=[np.number]).columns
        out_total = {c: len(self.detectar_atipicos(c)) for c in num_cols}
        peor_out = max(out_total.items(), key=lambda kv: kv[1]) if out_total else None
        if peor_out and peor_out[1] > 0:
            pct = round(peor_out[1] / total * 100, 1)
            obs.append({"nivel": "info",
                        "texto": f"«{peor_out[0]}» tiene {peor_out[1]} valores atípicos ({pct}%) según el método IQR."})

        return obs
