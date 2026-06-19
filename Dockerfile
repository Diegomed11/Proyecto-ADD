# APCD — Pipeline de Análisis de Datos
# Imagen para Hugging Face Spaces (SDK: docker). Escucha en el puerto 7860.

FROM python:3.12-slim

# HF Spaces ejecuta el contenedor como usuario no-root con UID 1000.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    HF_HOME=/home/user/.cache/huggingface \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    PYTHONUNBUFFERED=1

# Crear la caché de modelos como el usuario 1000 ANTES de que se monte el
# volumen. Así Docker inicializa el volumen nuevo con la propiedad correcta
# (user:user) y el proceso no-root puede descargar/escribir los modelos.
# (Sin esto, el volumen se crea propiedad de root → PermissionError al bajar
#  los transformers.)
RUN mkdir -p /home/user/.cache/huggingface/hub

WORKDIR /app

# PyTorch CPU-only PRIMERO: usa el índice oficial CPU para evitar el build
# con CUDA (~2 GB). Al instalarlo antes, satisface el 'torch' de requirements.
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu

# Resto de dependencias
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Código de la aplicación
COPY --chown=user . .

# Nota: los 5 modelos de NLP (sentimiento, resumen, zero-shot, NER, QA) se cargan
# de forma DIFERIDA: cada uno se descarga la primera vez que el usuario lo usa y
# queda cacheado. Esto mantiene la imagen ligera y el build rápido (la primera
# ejecución de cada modelo tardará un poco mientras descarga).

EXPOSE 7860

# Healthcheck: usa el endpoint /health para que Docker/compose sepan cuándo
# la app está lista (start-period generoso para el primer arranque).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:7860/health').status==200 else 1)" || exit 1

# OJO: 0.0.0.0 (no 127.0.0.1) para que sea accesible fuera del contenedor.
# Forma shell para que ${PORT} se expanda: HF Spaces usa 7860; otras nubes
# (AWS, Render…) inyectan su propio PORT. Si no hay PORT, usa 7860.
ENV PORT=7860
# 'exec' reemplaza al shell por uvicorn → uvicorn es PID 1 y recibe SIGTERM
# directamente, así el contenedor para de forma limpia y rápida (sin SIGKILL/137).
CMD ["sh", "-c", "exec uvicorn src.web_app:app --host 0.0.0.0 --port ${PORT:-7860}"]
