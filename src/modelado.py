"""
Módulo de modelado (Etapa 4 del pipeline).

Aplica técnicas estadísticas y de machine learning para extraer
patrones, tendencias y predicciones de cualquier DataFrame.

Clases:
    Modelador: Implementa modelos predictivos genéricos sobre los datos.
"""

import numpy as np
import pandas as pd


class Modelador:
    """
    Aplica modelos estadísticos y de ML sobre los datos preprocesados.

    Parameters
    ----------
    datos : pd.DataFrame
        DataFrame con los datos ya filtrados y limpios.

    Attributes
    ----------
    datos : pd.DataFrame
        Datos de trabajo.
    modelo : object or None
        Modelo de regresión entrenado.
    predicciones : pd.Series or None
        Predicciones generadas por el último modelo entrenado.
    """

    def __init__(self, datos: pd.DataFrame):
        self._datos = datos
        self._modelo = None
        self._predicciones = None
        self._col_x = None
        self._col_y = None


    def conteo_por_categoria(self, columna: str) -> dict:
        """
        Cuenta la frecuencia de cada valor en una columna categórica.

        Equivalente genérico de lanzamientos_por_cohete del UML.

        Parameters
        ----------
        columna : str

        Returns
        -------
        dict
            {categoria: conteo} ordenado de mayor a menor.
        """
        conteos = self._datos[columna].value_counts()
        return conteos.to_dict()

    def tasa_exito_por_anio(self, columna_fecha: str = None, columna_exito: str = None) -> dict:
        """
        Calcula la tasa de éxito (proporción de True) agrupada por año.

        Equivalente genérico de tasa_exito_por_anio del UML.

        Parameters
        ----------
        columna_fecha : str, optional
            Columna de fecha. Se autodetecta si no se especifica.
        columna_exito : str, optional
            Columna booleana de éxito. Se autodetecta si no se especifica.

        Returns
        -------
        dict
            {año: tasa_exito} ordenado cronológicamente.
        """
        df = self._datos.copy()

        if columna_fecha is None:
            cols_fecha = [
                c for c in df.columns
                if pd.api.types.is_datetime64_any_dtype(df[c])
            ]
            if not cols_fecha:
                return {}
            columna_fecha = cols_fecha[0]

        if columna_exito is None:
            cols_bool = [
                c for c in df.columns
                if pd.api.types.is_bool_dtype(df[c])
            ]
            if not cols_bool:
                return {}
            columna_exito = cols_bool[0]

        df["_anio"] = df[columna_fecha].dt.year
        tasa = df.groupby("_anio")[columna_exito].mean()
        return tasa.to_dict()

    def promedio_por_categoria(self, columna_grupo: str, columna_valor: str) -> dict:
        """
        Calcula el promedio de una columna numérica agrupado por categoría.

        Parameters
        ----------
        columna_grupo : str
        columna_valor : str

        Returns
        -------
        dict
            {categoria: promedio}.
        """
        resultado = self._datos.groupby(columna_grupo)[columna_valor].mean()
        return resultado.to_dict()


    def analisis_tendencia(self, columna_temporal: str, columna_valor: str) -> dict:
        """
        Detecta si la tendencia de una serie temporal es creciente,
        estable o decreciente usando la pendiente de regresión lineal.

        Parameters
        ----------
        columna_temporal : str
        columna_valor : str

        Returns
        -------
        dict
            {'tendencia': str, 'pendiente': float, 'serie': dict}
        """
        from sklearn.linear_model import LinearRegression

        df = self._datos[[columna_temporal, columna_valor]].dropna()
        if pd.api.types.is_datetime64_any_dtype(df[columna_temporal]):
            df = df.copy()
            df[columna_temporal] = df[columna_temporal].dt.year

        serie = df.groupby(columna_temporal)[columna_valor].mean()
        x = serie.index.values.reshape(-1, 1).astype(float)
        y = serie.values.astype(float)

        modelo = LinearRegression().fit(x, y)
        pendiente = float(modelo.coef_[0])

        if pendiente > 0.01:
            tendencia = "creciente"
        elif pendiente < -0.01:
            tendencia = "decreciente"
        else:
            tendencia = "estable"

        return {
            "tendencia": tendencia,
            "pendiente": pendiente,
            "serie": serie.to_dict(),
        }


    def entrenar_regresion_lineal(self, columna_x: str, columna_y: str) -> None:
        """
        Entrena un modelo de regresión lineal entre dos columnas.

        Parameters
        ----------
        columna_x : str
        columna_y : str

        Raises
        ------
        ValueError
            Si hay menos de 3 filas de datos válidos.
        """
        from sklearn.linear_model import LinearRegression

        df = self._datos[[columna_x, columna_y]].dropna()
        if len(df) < 3:
            raise ValueError(
                f"Se necesitan al menos 3 filas válidas para entrenar el modelo "
                f"(se encontraron {len(df)})."
            )

        x = df[columna_x].values.reshape(-1, 1).astype(float)
        y = df[columna_y].values.astype(float)

        self._modelo = LinearRegression().fit(x, y)
        self._predicciones = pd.Series(self._modelo.predict(x), name="predicciones")
        self._col_x = columna_x
        self._col_y = columna_y

    def predecir(self, valor_x: float) -> float:
        """
        Predice el valor de y para un x dado usando el modelo entrenado.

        Parameters
        ----------
        valor_x : float

        Returns
        -------
        float

        Raises
        ------
        RuntimeError
            Si el modelo no ha sido entrenado.
        """
        if self._modelo is None:
            raise RuntimeError("El modelo no ha sido entrenado. Llame a entrenar_regresion_lineal primero.")
        return float(self._modelo.predict([[valor_x]])[0])

    def predecir_proximo_anio(self, columna_temporal: str = None, columna_valor: str = None) -> int:
        """
        Predice el valor numérico para el próximo año/periodo temporal.

        Equivalente genérico de predecir_proximo_anio del UML.

        Parameters
        ----------
        columna_temporal : str, optional
        columna_valor : str, optional

        Returns
        -------
        int
            Predicción redondeada para el siguiente periodo.
        """
        if self._modelo is None:
            raise RuntimeError("El modelo no ha sido entrenado. Llame a entrenar_regresion_lineal primero.")

        # Usar los datos del modelo entrenado para encontrar el máximo periodo
        df = self._datos[[self._col_x]].dropna()
        max_x = float(df[self._col_x].max())
        proximo = max_x + 1
        return int(round(self.predecir(proximo)))

    def obtener_coeficientes(self) -> dict:
        """
        Retorna los coeficientes del modelo entrenado.

        Returns
        -------
        dict
            {'pendiente': float, 'intercepto': float}

        Raises
        ------
        RuntimeError
            Si el modelo no ha sido entrenado.
        """
        if self._modelo is None:
            raise RuntimeError("El modelo no ha sido entrenado. Llame a entrenar_regresion_lineal primero.")
        return {
            "pendiente": float(self._modelo.coef_[0]),
            "intercepto": float(self._modelo.intercept_),
        }

    def obtener_predicciones(self) -> pd.Series:
        """
        Retorna las predicciones del último modelo entrenado.

        Returns
        -------
        pd.Series or None
        """
        return self._predicciones

    def obtener_valores_reales(self) -> pd.Series:
        """
        Retorna los valores reales usados en el entrenamiento.

        Returns
        -------
        pd.Series or None
        """
        if self._col_y is None:
            return None
        df = self._datos[[self._col_x, self._col_y]].dropna()
        return df[self._col_y].reset_index(drop=True)

    # ──────────────────────────────────────────────────────────────────
    # Machine Learning genérico (menú de modelos)
    # ──────────────────────────────────────────────────────────────────

    # Catálogo de modelos disponibles (lo consume el frontend para el menú)
    MODELOS = {
        "linear":   {"nombre": "Regresión Lineal",    "tipo": "regresion",   "necesita_target": True},
        "logistic": {"nombre": "Regresión Logística", "tipo": "clasificacion", "necesita_target": True},
        "tree":     {"nombre": "Árbol de Decisión",   "tipo": "auto",        "necesita_target": True},
        "kmeans":   {"nombre": "K-Means (Clustering)", "tipo": "clustering",  "necesita_target": False},
    }

    def entrenar_ml(self, modelo: str, features, target=None, params=None) -> dict:
        """
        Punto de entrada unificado para entrenar cualquiera de los modelos
        soportados sobre columnas elegidas por el usuario.

        Parameters
        ----------
        modelo : str
            Uno de: 'linear', 'logistic', 'tree', 'kmeans'.
        features : list[str]
            Columnas de entrada (numéricas o categóricas; las categóricas se
            codifican con one-hot automáticamente).
        target : str, optional
            Columna objetivo (obligatoria salvo en 'kmeans').
        params : dict, optional
            Hiperparámetros opcionales: {'k': int} para K-Means,
            {'max_depth': int} para el árbol.

        Returns
        -------
        dict
            Resultado estructurado y seguro para JSON.
        """
        params = params or {}

        if modelo not in self.MODELOS:
            raise ValueError(f"Modelo desconocido: '{modelo}'.")
        if not features or not isinstance(features, list):
            raise ValueError("Selecciona al menos una variable de entrada.")
        faltantes = [c for c in features if c not in self._datos.columns]
        if faltantes:
            raise ValueError(f"Columnas no encontradas: {', '.join(faltantes)}.")

        if modelo == "kmeans":
            return self._ml_kmeans(features, params)

        # Modelos supervisados → requieren objetivo
        if not target:
            raise ValueError("Selecciona la columna objetivo.")
        if target not in self._datos.columns:
            raise ValueError(f"La columna objetivo '{target}' no existe.")
        if target in features:
            raise ValueError("El objetivo no puede estar también entre las variables de entrada.")

        if modelo == "linear":
            return self._ml_lineal(features, target, params)
        if modelo == "logistic":
            return self._ml_logistica(features, target, params)
        if modelo == "tree":
            return self._ml_arbol(features, target, params)

    # ── Helpers internos ───────────────────────────────────────────────

    def _construir_X(self, df: pd.DataFrame, features: list) -> pd.DataFrame:
        """Selecciona features y codifica categóricas con one-hot."""
        X = df[features].copy()
        cat_cols = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
        if cat_cols:
            X = pd.get_dummies(X, columns=cat_cols, dummy_na=False)
        X = X.apply(pd.to_numeric, errors="coerce")
        return X

    def _preparar_supervisado(self, features: list, target: str):
        """Devuelve (X numérico, y_raw alineado) sin nulos."""
        df = self._datos[features + [target]].dropna()
        if len(df) < 5:
            raise ValueError(
                f"Muy pocas filas válidas tras quitar nulos ({len(df)}). Se necesitan al menos 5."
            )
        X = self._construir_X(df, features)
        mask = X.notna().all(axis=1)
        X = X[mask]
        y_raw = df[target][mask]
        if X.shape[1] == 0 or len(X) < 5:
            raise ValueError("No quedan datos numéricos suficientes tras la preparación.")
        return X.reset_index(drop=True), y_raw.reset_index(drop=True)

    def _split(self, X, y, estratificar=None):
        """Divide en train/test (25%) si hay datos suficientes."""
        from sklearn.model_selection import train_test_split
        if len(X) >= 20:
            try:
                Xtr, Xte, ytr, yte = train_test_split(
                    X, y, test_size=0.25, random_state=42, stratify=estratificar
                )
            except ValueError:
                Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42)
            return Xtr, Xte, ytr, yte, "holdout 25%"
        return X, X, y, y, "dataset completo"

    @staticmethod
    def _f(v, d=4):
        return float(round(float(v), d))

    # ── Modelo 1: Regresión Lineal ─────────────────────────────────────

    def _ml_lineal(self, features, target, params):
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

        if not pd.api.types.is_numeric_dtype(self._datos[target]):
            raise ValueError(
                "La Regresión Lineal necesita un objetivo NUMÉRICO. "
                "Para categorías usa Regresión Logística o Árbol de Decisión."
            )
        X, y_raw = self._preparar_supervisado(features, target)
        y = pd.to_numeric(y_raw, errors="coerce")
        m = y.notna()
        X, y = X[m].reset_index(drop=True), y[m].reset_index(drop=True)

        Xtr, Xte, ytr, yte, evalu = self._split(X, y)
        modelo = LinearRegression().fit(Xtr, ytr)
        pred = modelo.predict(Xte)

        r2 = r2_score(yte, pred)
        rmse = mean_squared_error(yte, pred) ** 0.5
        mae = mean_absolute_error(yte, pred)

        coefs = sorted(zip(X.columns, modelo.coef_), key=lambda t: abs(t[1]), reverse=True)[:12]
        top = coefs[0][0] if coefs else "—"

        return {
            "modelo": "linear", "modelo_nombre": "Regresión Lineal", "tipo": "regresion",
            "n_muestras": int(len(X)), "n_features": int(X.shape[1]), "evaluacion": evalu,
            "metricas": [
                {"label": "R² (precisión)", "valor": f"{self._f(r2)}", "destacado": True},
                {"label": "RMSE", "valor": f"{self._f(rmse)}", "destacado": False},
                {"label": "MAE", "valor": f"{self._f(mae)}", "destacado": False},
            ],
            "detalle": {
                "tipo": "coeficientes",
                "intercepto": self._f(modelo.intercept_),
                "items": [{"nombre": n, "valor": self._f(v)} for n, v in coefs],
            },
            "interpretacion": (
                f"El modelo explica el {r2 * 100:.1f}% de la variación de «{target}» "
                f"sobre datos no vistos. La variable más influyente es «{top}»."
            ),
        }

    # ── Modelo 2: Regresión Logística ──────────────────────────────────

    def _ml_logistica(self, features, target, params):
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler, LabelEncoder
        from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

        if pd.api.types.is_numeric_dtype(self._datos[target]) and self._datos[target].nunique(dropna=True) > 15:
            raise ValueError(
                "La Regresión Logística necesita un objetivo categórico (pocas clases). "
                "El objetivo elegido parece continuo: usa Regresión Lineal o Árbol de Decisión."
            )
        X, y_raw = self._preparar_supervisado(features, target)
        le = LabelEncoder()
        y = le.fit_transform(y_raw.astype(str))
        clases = [str(c) for c in le.classes_]
        if len(clases) < 2:
            raise ValueError("El objetivo debe tener al menos 2 clases distintas.")

        Xs = StandardScaler().fit_transform(X)
        Xtr, Xte, ytr, yte, evalu = self._split(Xs, y, estratificar=y)
        modelo = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
        pred = modelo.predict(Xte)

        acc = accuracy_score(yte, pred)
        f1 = f1_score(yte, pred, average="weighted", zero_division=0)
        cm = confusion_matrix(yte, pred, labels=list(range(len(clases))))

        return {
            "modelo": "logistic", "modelo_nombre": "Regresión Logística", "tipo": "clasificacion",
            "n_muestras": int(len(X)), "n_features": int(X.shape[1]), "evaluacion": evalu,
            "metricas": [
                {"label": "Exactitud (accuracy)", "valor": f"{acc * 100:.1f}%", "destacado": True},
                {"label": "F1 (ponderado)", "valor": f"{self._f(f1)}", "destacado": False},
                {"label": "N.º de clases", "valor": f"{len(clases)}", "destacado": False},
            ],
            "detalle": {
                "tipo": "confusion",
                "clases": clases,
                "matriz": [[int(v) for v in fila] for fila in cm],
            },
            "interpretacion": (
                f"El modelo clasifica «{target}» correctamente el {acc * 100:.1f}% de las veces "
                f"sobre datos no vistos, entre {len(clases)} clases."
            ),
        }

    # ── Modelo 3: Árbol de Decisión (auto clasif./regresión) ───────────

    def _ml_arbol(self, features, target, params):
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
        from sklearn.preprocessing import LabelEncoder
        from sklearn.metrics import (accuracy_score, f1_score, confusion_matrix,
                                      r2_score, mean_squared_error)

        max_depth = params.get("max_depth")
        try:
            max_depth = int(max_depth) if max_depth not in (None, "", 0) else None
        except (TypeError, ValueError):
            max_depth = None

        X, y_raw = self._preparar_supervisado(features, target)
        es_numerico = pd.api.types.is_numeric_dtype(self._datos[target])
        es_clasificacion = (not es_numerico) or (y_raw.nunique(dropna=True) <= 15)

        if es_clasificacion:
            le = LabelEncoder()
            y = le.fit_transform(y_raw.astype(str))
            clases = [str(c) for c in le.classes_]
            modelo = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
            Xtr, Xte, ytr, yte, evalu = self._split(X, y, estratificar=y)
            modelo.fit(Xtr, ytr)
            pred = modelo.predict(Xte)
            acc = accuracy_score(yte, pred)
            f1 = f1_score(yte, pred, average="weighted", zero_division=0)
            cm = confusion_matrix(yte, pred, labels=list(range(len(clases))))
            metricas = [
                {"label": "Exactitud (accuracy)", "valor": f"{acc * 100:.1f}%", "destacado": True},
                {"label": "F1 (ponderado)", "valor": f"{self._f(f1)}", "destacado": False},
                {"label": "Profundidad", "valor": f"{modelo.get_depth()}", "destacado": False},
            ]
            extra_detalle = {"tipo": "confusion", "clases": clases,
                             "matriz": [[int(v) for v in fila] for fila in cm]}
            interp = (f"El árbol clasifica «{target}» con {acc * 100:.1f}% de exactitud "
                      f"sobre datos no vistos.")
            tipo = "clasificacion"
        else:
            y = pd.to_numeric(y_raw, errors="coerce")
            mm = y.notna()
            Xf, yf = X[mm].reset_index(drop=True), y[mm].reset_index(drop=True)
            modelo = DecisionTreeRegressor(max_depth=max_depth, random_state=42)
            Xtr, Xte, ytr, yte, evalu = self._split(Xf, yf)
            modelo.fit(Xtr, ytr)
            pred = modelo.predict(Xte)
            r2 = r2_score(yte, pred)
            rmse = mean_squared_error(yte, pred) ** 0.5
            metricas = [
                {"label": "R² (precisión)", "valor": f"{self._f(r2)}", "destacado": True},
                {"label": "RMSE", "valor": f"{self._f(rmse)}", "destacado": False},
                {"label": "Profundidad", "valor": f"{modelo.get_depth()}", "destacado": False},
            ]
            extra_detalle = None
            interp = (f"El árbol explica el {r2 * 100:.1f}% de la variación de «{target}» "
                      f"sobre datos no vistos.")
            tipo = "regresion"

        importancias = sorted(zip(X.columns, modelo.feature_importances_),
                              key=lambda t: t[1], reverse=True)[:12]
        top = importancias[0][0] if importancias else "—"

        detalle = {"tipo": "importancias",
                   "items": [{"nombre": n, "valor": self._f(v)} for n, v in importancias]}
        if extra_detalle:
            detalle["extra"] = extra_detalle

        return {
            "modelo": "tree", "modelo_nombre": "Árbol de Decisión", "tipo": tipo,
            "n_muestras": int(len(X)), "n_features": int(X.shape[1]), "evaluacion": evalu,
            "metricas": metricas,
            "detalle": detalle,
            "interpretacion": interp + f" La variable más decisiva es «{top}».",
        }

    # ── Modelo 4: K-Means (no supervisado) ─────────────────────────────

    def _ml_kmeans(self, features, params):
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score

        df = self._datos[features].dropna()
        X = self._construir_X(df, features).dropna()
        if X.shape[1] < 1:
            raise ValueError("Se necesita al menos una columna numérica/categórica válida.")
        if len(X) < 10:
            raise ValueError(f"Muy pocas filas para clustering ({len(X)}). Se necesitan al menos 10.")

        try:
            k = int(params.get("k", 3))
        except (TypeError, ValueError):
            k = 3
        k = max(2, min(k, 10, len(X) - 1))

        Xs = StandardScaler().fit_transform(X)
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
        labels = km.labels_
        sil = float(silhouette_score(Xs, labels)) if len(set(labels)) > 1 else 0.0

        counts = pd.Series(labels).value_counts().sort_index()
        items = [{"cluster": int(i), "n": int(c)} for i, c in counts.items()]

        if sil >= 0.5:
            cualidad = "fuerte"
        elif sil >= 0.25:
            cualidad = "moderada"
        else:
            cualidad = "débil"

        return {
            "modelo": "kmeans", "modelo_nombre": "K-Means (Clustering)", "tipo": "clustering",
            "n_muestras": int(len(X)), "n_features": int(X.shape[1]), "evaluacion": "no supervisado",
            "metricas": [
                {"label": "Silhouette", "valor": f"{self._f(sil)}", "destacado": True},
                {"label": "Grupos (k)", "valor": f"{k}", "destacado": False},
                {"label": "Inercia", "valor": f"{self._f(km.inertia_, 1)}", "destacado": False},
            ],
            "detalle": {"tipo": "clusters", "items": items},
            "interpretacion": (
                f"Se agruparon {len(X)} filas en {k} grupos. El silhouette de {sil:.2f} "
                f"indica una separación {cualidad} entre los grupos."
            ),
        }
