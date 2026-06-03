"""
Modelos de NLP basados en Transformers / BERT (Etapa de análisis de texto web).

Expone un catálogo de tareas y una función `analizar(tarea, texto, opciones)`
que ejecuta el pipeline de HuggingFace correspondiente. Los pipelines se cargan
de forma diferida (lazy) y se cachean en memoria para reutilizarlos.

Catálogo de modelos:
    sentiment : Análisis de sentimiento (DistilBERT SST-2)
    summary   : Resumen automático (DistilBART CNN)
    zeroshot  : Clasificación temática sin entrenar (BART-MNLI)
    ner       : Reconocimiento de entidades nombradas (BERT NER)
    qa        : Pregunta-respuesta extractiva (DistilBERT SQuAD)
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Catálogo que también consume el frontend para construir el menú.
MODELOS_NLP = {
    "sentiment": {
        "nombre": "Análisis de Sentimiento",
        "modelo": "distilbert-base-uncased-finetuned-sst-2-english",
        "tarea_hf": "sentiment-analysis",
        "icono": "sentiment_satisfied",
        "tipo": "Clasificación",
        "pagina_ideal": "Reseñas, opiniones, comentarios o blogs personales (mejor en inglés).",
        "necesita": None,
    },
    "summary": {
        "nombre": "Resumen Automático",
        "modelo": "sshleifer/distilbart-cnn-12-6",
        "tarea_hf": "summarization",
        "icono": "summarize",
        "tipo": "Generación",
        "pagina_ideal": "Noticias o artículos largos de varios párrafos (mejor en inglés).",
        "necesita": None,
    },
    "zeroshot": {
        "nombre": "Clasificación Temática",
        "modelo": "facebook/bart-large-mnli",
        "tarea_hf": "zero-shot-classification",
        "icono": "label",
        "tipo": "Zero-shot",
        "pagina_ideal": "Noticias o artículos; tú defines las categorías candidatas.",
        "necesita": "labels",
    },
    "ner": {
        "nombre": "Entidades (NER)",
        "modelo": "dslim/bert-base-NER",
        "tarea_hf": "ner",
        "icono": "person_pin",
        "tipo": "Etiquetado",
        "pagina_ideal": "Noticias o biografías con nombres de personas, lugares y organizaciones.",
        "necesita": None,
    },
    "qa": {
        "nombre": "Pregunta-Respuesta",
        "modelo": "distilbert-base-cased-distilled-squad",
        "tarea_hf": "question-answering",
        "icono": "quiz",
        "tipo": "Extractivo",
        "pagina_ideal": "Páginas informativas o Wikipedia; tú escribes una pregunta.",
        "necesita": "pregunta",
    },
}

# Etiquetas legibles para los grupos de entidades de NER.
_NER_ETIQUETAS = {
    "PER": "Personas",
    "ORG": "Organizaciones",
    "LOC": "Lugares",
    "MISC": "Misceláneo",
}

# Caché de pipelines ya cargados (lazy loading).
_PIPELINES = {}


def _get_pipeline(tarea: str):
    """Devuelve (cacheado) el pipeline de HuggingFace para la tarea dada."""
    if tarea not in _PIPELINES:
        from transformers import pipeline
        cfg = MODELOS_NLP[tarea]
        kwargs = {}
        if tarea == "ner":
            kwargs["aggregation_strategy"] = "simple"
        _PIPELINES[tarea] = pipeline(cfg["tarea_hf"], model=cfg["modelo"], **kwargs)
    return _PIPELINES[tarea]


def analizar(tarea: str, texto: str, opciones: dict = None) -> dict:
    """
    Ejecuta el modelo transformer indicado sobre el texto.

    Parameters
    ----------
    tarea : str
        Clave del modelo: 'sentiment', 'summary', 'zeroshot', 'ner', 'qa'.
    texto : str
        Texto plano extraído de la página.
    opciones : dict, optional
        Parámetros específicos: {'labels': [...]} para zero-shot,
        {'pregunta': '...'} para QA.

    Returns
    -------
    dict
        Resultado estructurado y seguro para JSON.
    """
    opciones = opciones or {}

    if tarea not in MODELOS_NLP:
        raise ValueError(f"Modelo de NLP desconocido: '{tarea}'.")
    if not texto or len(texto.strip()) < 20:
        raise ValueError("No hay suficiente texto en la página para analizar.")

    if tarea == "sentiment":
        clf = _get_pipeline(tarea)
        r = clf(texto[:512])[0]
        return {"tipo": "sentiment", "label": str(r["label"]), "score": float(r["score"])}

    if tarea == "summary":
        s = _get_pipeline(tarea)
        entrada = texto[:3000]
        r = s(entrada, max_length=140, min_length=30, do_sample=False)[0]
        return {"tipo": "summary", "resumen": r["summary_text"].strip()}

    if tarea == "zeroshot":
        labels = opciones.get("labels") or []
        if isinstance(labels, str):
            labels = [l.strip() for l in labels.split(",") if l.strip()]
        labels = [l for l in labels if l]
        if len(labels) < 2:
            raise ValueError("Indica al menos 2 categorías (separadas por comas).")
        z = _get_pipeline(tarea)
        r = z(texto[:1000], candidate_labels=labels, multi_label=False)
        items = [{"label": str(l), "score": float(sc)} for l, sc in zip(r["labels"], r["scores"])]
        return {"tipo": "zeroshot", "items": items}

    if tarea == "ner":
        n = _get_pipeline(tarea)
        entidades = n(texto[:1500])
        agrupado = {}
        for e in entidades:
            grupo = e.get("entity_group") or e.get("entity") or "MISC"
            # Limpiar artefactos de subpalabras (##) del tokenizador
            palabra = str(e.get("word", "")).replace(" ##", "").replace("##", "").strip()
            if not palabra or len(palabra) < 2:
                continue
            agrupado.setdefault(grupo, {})
            # Quedarse con el score máximo por entidad repetida
            prev = agrupado[grupo].get(palabra, 0.0)
            agrupado[grupo][palabra] = max(prev, float(e.get("score", 0.0)))
        grupos = []
        for grupo, ents in agrupado.items():
            ordenadas = sorted(ents.items(), key=lambda t: t[1], reverse=True)[:15]
            grupos.append({
                "tipo": _NER_ETIQUETAS.get(grupo, grupo),
                "entidades": [{"texto": p, "score": s} for p, s in ordenadas],
            })
        grupos.sort(key=lambda g: len(g["entidades"]), reverse=True)
        return {"tipo": "ner", "grupos": grupos}

    if tarea == "qa":
        pregunta = (opciones.get("pregunta") or "").strip()
        if not pregunta:
            raise ValueError("Escribe una pregunta para el modelo.")
        qa = _get_pipeline(tarea)
        r = qa(question=pregunta, context=texto[:3000])
        return {
            "tipo": "qa",
            "pregunta": pregunta,
            "respuesta": str(r.get("answer", "")).strip(),
            "score": float(r.get("score", 0.0)),
        }

    raise ValueError(f"Modelo de NLP no implementado: '{tarea}'.")
