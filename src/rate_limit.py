"""
Rate limiting ligero en memoria (por IP) para proteger la app de abuso.

No usa dependencias externas ni Redis: como el estado de la app ya vive en
memoria (instancia única), una ventana deslizante en memoria es suficiente y
coherente con la arquitectura.

Dos cubos por IP:
  - general: límite alto para navegación normal.
  - pesado : límite bajo para endpoints caros (subir, EDA, reporte, scraping,
             NLP, entrenar modelos) que consumen CPU/RAM.

Configurable por variables de entorno:
  RATE_LIMIT_ENABLED   (default "1")
  RATE_LIMIT_GENERAL   peticiones/min generales (default 120)
  RATE_LIMIT_HEAVY     peticiones/min en endpoints pesados (default 15)
"""

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Prefijos de endpoints caros (CPU/RAM) → límite estricto.
# (Se deja fuera /api/viz porque es ligero e interactivo: cambiar de gráfico.)
PREFIJOS_PESADOS = (
    "/api/upload",
    "/api/eda",
    "/api/report",
    "/api/scrape",
    "/api/nlp",
    "/api/models/train",
    "/api/etl/preview",
    "/api/etl/apply",
)


class RateLimiter(BaseHTTPMiddleware):
    """Middleware de límite de peticiones por IP con ventana deslizante."""

    def __init__(self, app, general_per_min=120, heavy_per_min=15, window=60):
        super().__init__(app)
        self.general = general_per_min
        self.heavy = heavy_per_min
        self.window = window
        self._hits = defaultdict(deque)  # clave -> deque[timestamps]

    @staticmethod
    def _client_ip(request):
        # Detrás de un ALB / proxy la IP real viene en X-Forwarded-For.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "desconocida"

    async def dispatch(self, request, call_next):
        path = request.url.path
        # Nunca limitar estáticos ni el health check (lo usa la nube).
        if path.startswith("/static") or path == "/health":
            return await call_next(request)

        es_pesado = any(path.startswith(p) for p in PREFIJOS_PESADOS)
        limite = self.heavy if es_pesado else self.general
        clave = f"{self._client_ip(request)}:{'h' if es_pesado else 'g'}"

        ahora = time.time()
        marcas = self._hits[clave]
        corte = ahora - self.window
        while marcas and marcas[0] < corte:
            marcas.popleft()

        if len(marcas) >= limite:
            espera = int(self.window - (ahora - marcas[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": f"Demasiadas peticiones. Espera {espera}s e intenta de nuevo."},
                headers={"Retry-After": str(espera)},
            )

        marcas.append(ahora)
        # Limpieza oportunista para que el dict no crezca sin límite.
        if len(self._hits) > 4096:
            self._purgar(corte)
        return await call_next(request)

    def _purgar(self, corte):
        vacias = [k for k, v in self._hits.items() if not v or v[-1] < corte]
        for k in vacias:
            del self._hits[k]


def config_desde_entorno():
    """Devuelve (activado, kwargs) leyendo las variables de entorno."""
    activado = os.environ.get("RATE_LIMIT_ENABLED", "1") in ("1", "true", "True")
    kwargs = {
        "general_per_min": int(os.environ.get("RATE_LIMIT_GENERAL", "120")),
        "heavy_per_min": int(os.environ.get("RATE_LIMIT_HEAVY", "15")),
    }
    return activado, kwargs
