import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.api_routes import router as api_router

# Obtener la ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="PDA - Pipeline de Análisis de Datos")

# Montar los estáticos (si hay CSS o JS adicional)
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Configurar Jinja2 para las plantillas HTML
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# Incluir las rutas de la API
app.include_router(api_router, prefix="/api")

# --- Rutas del Frontend (Vistas) ---

@app.get("/")
async def overview(request: Request):
    return templates.TemplateResponse("overview.html", {"request": request, "active_tab": "overview"})

@app.get("/databases")
async def databases(request: Request):
    return templates.TemplateResponse("databases.html", {"request": request, "active_tab": "databases"})

@app.get("/pipelines")
async def pipelines(request: Request):
    return templates.TemplateResponse("pipelines.html", {"request": request, "active_tab": "pipelines"})

@app.get("/sql-editor")
async def sql_editor(request: Request):
    return templates.TemplateResponse("sql_editor.html", {"request": request, "active_tab": "sql-editor"})

@app.get("/statistics")
async def statistics(request: Request):
    return templates.TemplateResponse("statistics.html", {"request": request, "active_tab": "statistics"})

@app.get("/web-scraping")
async def web_scraping(request: Request):
    return templates.TemplateResponse("web_scraping.html", {"request": request, "active_tab": "web-scraping"})

@app.get("/modeling")
async def modeling(request: Request):
    return templates.TemplateResponse("modeling.html", {"request": request, "active_tab": "modeling"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web_app:app", host="127.0.0.1", port=8000, reload=True)
