"""
Modelos de NLP basados en Transformers / BERT (Etapa de análisis de texto web).

Expone un catálogo de tareas y una función `analizar(tarea, texto, opciones)`
que ejecuta el modelo de HuggingFace correspondiente. Los modelos se cargan
de forma diferida (lazy) y se cachean en memoria para reutilizarlos.

COMPATIBILIDAD DE VERSIONES
---------------------------
A partir de transformers 5.x cambiaron / se eliminaron varios nombres de tarea
de `pipeline()`:
    sentiment-analysis   -> text-classification
    ner                  -> token-classification
    summarization        -> (eliminada del pipeline)
    question-answering   -> (eliminada del pipeline)

Para que la app funcione igual en 4.x y en 5.x:
  * sentiment / ner / zeroshot usan pipeline() con nombres de tarea seguros.
  * summary y qa cargan el modelo + tokenizer directamente (AutoModel...) y
    ejecutan la inferencia a mano. Esto es independiente de la versión.

Catálogo de modelos:
    sentiment : Análisis de sentimiento (DistilBERT SST-2)
    summary   : Resumen automático (DistilBART CNN)
    zeroshot  : Clasificación temática sin entrenar (BART-MNLI)
    ner       : Reconocimiento de entidades nombradas (BERT NER)
    qa        : Pregunta-respuesta extractiva (DistilBERT SQuAD)
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Catálogo que también consume el frontend para construir el menú.
MODELOS_NLP = {
    "sentiment": {
        "nombre": "Análisis de Sentimiento",
        "modelo": "distilbert-base-uncased-finetuned-sst-2-english",
        "tarea_hf": "text-classification",
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
        "tarea_hf": "token-classification",
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

# Caché de modelos con eviction LRU. Mantener TODOS los modelos cargados a la vez
# puede superar varios GB (BART-large ~3 GB) y tumbar una instancia de 8 GB. Por eso
# guardamos como máximo NLP_MAX_MODELOS en memoria; al cargar uno nuevo se libera el
# menos usado. Configurable por entorno (default 1 → máximo seguro para 8 GB).
import gc
from collections import OrderedDict

_MAX_MODELOS = max(1, int(os.environ.get("NLP_MAX_MODELOS", "1")))
_PIPELINES = OrderedDict()


def _obtener_cache(clave):
    """Devuelve el modelo cacheado (y lo marca como recién usado) o None."""
    if clave in _PIPELINES:
        _PIPELINES.move_to_end(clave)
        return _PIPELINES[clave]
    return None


def _recordar_cache(clave, valor):
    """Guarda un modelo y libera los más antiguos si se supera el límite."""
    _PIPELINES[clave] = valor
    _PIPELINES.move_to_end(clave)
    while len(_PIPELINES) > _MAX_MODELOS:
        _PIPELINES.popitem(last=False)  # descarta el menos usado
        gc.collect()  # libera la RAM del modelo evacuado
    return valor


def _get_pipeline(tarea: str):
    """Devuelve (cacheado) el pipeline de HuggingFace para tareas basadas en pipeline.

    Sólo se usa para sentiment / zeroshot / ner, cuyos nombres de tarea siguen
    existiendo en transformers 4.x y 5.x.
    """
    cacheado = _obtener_cache(tarea)
    if cacheado is not None:
        return cacheado
    from transformers import pipeline
    cfg = MODELOS_NLP[tarea]
    kwargs = {}
    if tarea == "ner":
        kwargs["aggregation_strategy"] = "simple"
    return _recordar_cache(tarea, pipeline(cfg["tarea_hf"], model=cfg["modelo"], **kwargs))


def _get_modelo_directo(tarea: str, auto_clase):
    """Carga (cacheado) tokenizer + modelo directamente, sin pipeline.

    Se usa para summary (seq2seq) y qa, cuyas tareas de pipeline se eliminaron
    en transformers 5.x. Cargar el modelo a mano funciona en cualquier versión.
    """
    clave = f"__directo__{tarea}"
    cacheado = _obtener_cache(clave)
    if cacheado is not None:
        return cacheado
    from transformers import AutoTokenizer
    cfg = MODELOS_NLP[tarea]
    tok = AutoTokenizer.from_pretrained(cfg["modelo"])
    mdl = auto_clase.from_pretrained(cfg["modelo"])
    mdl.eval()
    return _recordar_cache(clave, (tok, mdl))


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
        r = clf(texto[:512], truncation=True)[0]
        return {"tipo": "sentiment", "label": str(r["label"]), "score": float(r["score"])}

    if tarea == "summary":
        return _resumir(texto)

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
            # Normalizar etiquetas tipo "B-PER" / "I-LOC" -> "PER" / "LOC"
            if "-" in grupo:
                grupo = grupo.split("-")[-1]
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
        if not grupos:
            return {"tipo": "ner", "grupos": [], "aviso": "No se detectaron entidades nombradas en el texto."}
        return {"tipo": "ner", "grupos": grupos}

    if tarea == "qa":
        pregunta = (opciones.get("pregunta") or "").strip()
        if not pregunta:
            raise ValueError("Escribe una pregunta para el modelo.")
        return _preguntar(pregunta, texto)

    raise ValueError(f"Modelo de NLP no implementado: '{tarea}'.")


def _resumir(texto: str) -> dict:
    """Resumen con un modelo seq2seq (DistilBART), sin depender del pipeline."""
    import torch
    from transformers import AutoModelForSeq2SeqLM

    tok, mdl = _get_modelo_directo("summary", AutoModelForSeq2SeqLM)
    entrada = texto[:3000]
    inputs = tok(entrada, return_tensors="pt", truncation=True, max_length=1024)
    with torch.no_grad():
        ids = mdl.generate(
            **inputs,
            max_length=160,
            min_length=30,
            num_beams=4,
            no_repeat_ngram_size=3,
            early_stopping=True,
        )
    resumen = tok.decode(ids[0], skip_special_tokens=True).strip()
    if not resumen:
        raise ValueError("El modelo no pudo generar un resumen para este texto.")
    return {"tipo": "summary", "resumen": resumen}


def _preguntar(pregunta: str, texto: str) -> dict:
    """QA extractivo cargando el modelo directamente (compatible 4.x y 5.x)."""
    import torch
    from transformers import AutoModelForQuestionAnswering

    tok, mdl = _get_modelo_directo("qa", AutoModelForQuestionAnswering)
    inputs = tok(
        pregunta,
        texto[:3000],
        return_tensors="pt",
        truncation="only_second",
        max_length=512,
        padding=True,
    )
    with torch.no_grad():
        salida = mdl(**inputs)

    inicio_logits = salida.start_logits[0]
    fin_logits = salida.end_logits[0]
    inicio = int(torch.argmax(inicio_logits))
    fin = int(torch.argmax(fin_logits)) + 1
    if fin <= inicio:
        fin = inicio + 1

    ids = inputs["input_ids"][0][inicio:fin]
    respuesta = tok.decode(ids, skip_special_tokens=True)
    # Limpiar artefactos de subpalabras (##) cuando el span empieza a mitad de palabra.
    respuesta = respuesta.replace(" ##", "").replace("##", "").strip()

    # Score = producto de las probabilidades softmax de inicio y fin.
    p_inicio = torch.softmax(inicio_logits, dim=-1)[inicio]
    p_fin = torch.softmax(fin_logits, dim=-1)[min(fin - 1, len(fin_logits) - 1)]
    score = float(p_inicio * p_fin)

    if not respuesta:
        return {
            "tipo": "qa",
            "pregunta": pregunta,
            "respuesta": "No encontré una respuesta clara en el texto.",
            "score": 0.0,
        }
    return {"tipo": "qa", "pregunta": pregunta, "respuesta": respuesta, "score": score}
