import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.api_routes import router as api_router
from src.rate_limit import RateLimiter, config_desde_entorno

# Obtener la ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="PDA - Pipeline de Análisis de Datos")

# Rate limiting por IP (protege la app de abuso/DoS). Configurable por entorno.
_rl_activado, _rl_kwargs = config_desde_entorno()
if _rl_activado:
    app.add_middleware(RateLimiter, **_rl_kwargs)

# Montar los estáticos (si hay CSS o JS adicional)
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Configurar Jinja2 para las plantillas HTML
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Incluir las rutas de la API
app.include_router(api_router, prefix="/api")


# --- Health check (lo usan las plataformas de nube para saber si la app vive) ---
@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Manejadores de error amigables ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Las rutas de API devuelven JSON; las vistas devuelven una página.
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request, "error.html",
            {"codigo": 404, "titulo": "Página no encontrada",
             "mensaje": "La ruta que buscas no existe o se movió."},
            status_code=404,
        )
    return templates.TemplateResponse(
        request, "error.html",
        {"codigo": exc.status_code, "titulo": "Error",
         "mensaje": str(exc.detail)},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})
    return templates.TemplateResponse(
        request, "error.html",
        {"codigo": 500, "titulo": "Error interno",
         "mensaje": "Algo salió mal en el servidor. Inténtalo de nuevo."},
        status_code=500,
    )


# --- Rutas del Frontend (Vistas) ---

@app.get("/")
async def landing(request: Request):
    # Página de presentación (hero). El botón "Empezar ahora" lleva a /app.
    return templates.TemplateResponse(request, "landing.html", {})

@app.get("/app")
async def overview(request: Request):
    return templates.TemplateResponse(request, "overview.html", {"active_tab": "overview"})

@app.get("/report")
async def report_page(request: Request):
    return templates.TemplateResponse(request, "report.html", {"active_tab": "report"})

@app.get("/databases")
async def databases(request: Request):
    return templates.TemplateResponse(request, "databases.html", {"active_tab": "databases"})

@app.get("/sql-editor")
async def sql_editor(request: Request):
    return templates.TemplateResponse(request, "sql_editor.html", {"active_tab": "sql-editor"})

@app.get("/etl")
async def etl(request: Request):
    return templates.TemplateResponse(request, "etl.html", {"active_tab": "etl"})

@app.get("/statistics")
async def statistics(request: Request):
    return templates.TemplateResponse(request, "statistics.html", {"active_tab": "statistics"})

@app.get("/web-scraping")
async def web_scraping(request: Request):
    return templates.TemplateResponse(request, "web_scraping.html", {"active_tab": "web-scraping"})

@app.get("/modeling")
async def modeling(request: Request):
    return templates.TemplateResponse(request, "modeling.html", {"active_tab": "modeling"})

if __name__ == "__main__":
    import uvicorn
    # El puerto se puede fijar con la variable de entorno PORT (nube); por defecto 8000 en local.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.web_app:app", host="0.0.0.0", port=port, reload=True)
