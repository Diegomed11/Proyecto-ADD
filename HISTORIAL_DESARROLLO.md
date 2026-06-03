# Historial de Desarrollo - Proyecto APCD

Este documento resume las interacciones y el desarrollo realizado durante nuestra sesión de pair programming.

## 1. Integración de Skills y Refactorización Estética (Liquid Glass)
- **Análisis de Skills:** Se analizaron las skills disponibles en la carpeta `.agents`, tomando elementos de diseño visual avanzado, manejo de color y animaciones (como staggered animations, pseudo-elementos brillantes, y loaders).
- **Nuevo Design System:** Se implementó una estética "Liquid Glass" (modo claro) con acentos de color Azul Océano (`#0EA5E9`) y Verde Esmeralda (`#10B981`).
- **Barra Lateral (Sidebar):** Se rediseñó la barra lateral con orbes desenfocados (blur-3xl), bordes translúcidos y botones de navegación tipo "glass pill" interactivos.
- **Vistas Actualizadas:**
  - `base.html`: Inclusión del fondo `mesh-bg` y reglas CSS para el Glassmorphism.
  - `overview.html`: Tarjetas de estadísticas con efecto de cristal y animaciones de entrada en cascada (`stagger`).
  - `pipelines.html`: Área de "drag and drop" con hover magnético.
  - `databases.html`, `modeling.html`, `statistics.html` y `web_scraping.html`: Paneles translúcidos y botones mejorados.

## 2. Corrección de Funcionalidad
- **Subida de Archivos:** Se corrigió un error en `pipelines.html` donde los archivos CSV/JSON no se cargaban a memoria. El problema se debió a una capa de seguridad en `safeFetch` que no procesaba correctamente el `FormData`. Se solucionó implementando un `fetch` nativo optimizado.
- **Traducciones:** Se eliminó la terminología en inglés de la interfaz, reemplazándola por español para mayor accesibilidad.

## 3. Artefactos Generados
A lo largo de la sesión, se documentó el proceso usando artefactos persistentes:
- `DESIGN.md`: Reglas del sistema de diseño Liquid Glass.
- `walkthrough.md`: Recorrido visual y funcional de los cambios estéticos.
- `task.md`: Seguimiento de las tareas completadas.

## 4. Rediseño Anti-"IA" (Dark Technical / Editorial)
Se aplicaron las skills de `.agents/skills` (sobre todo `redesign-existing-projects` y `design-taste-frontend`) para que el frontend **dejara de parecer salida genérica de IA**.

- **Diagnóstico (audit-first):** el estilo "Liquid Glass" previo concentraba varios *sellos de IA* que las propias skills marcan como antipatrones: gradiente azul→verde en botones/iconos/texto, glassmorphism en todo, fondo *mesh gradient*, orbes difuminados, punto pulsante "Sistema Activo", texto con gradiente y múltiples acentos (sky + emerald + indigo).
- **Nuevo sistema:** base casi negra plana (`#0A0A0B`), un **único acento ámbar** (`#F59E0B`), tipografía Geist + Geist Mono con **números tabulares**, bordes *hairline* (`#26262A`), sombras tintadas y motion mínimo. Documentado en `DESIGN.md`.
- **Alcance:** se reescribió `base.html` (config de Tailwind, utilidades `.panel`/`.btn-primary`/`.custom-input`, sidebar y header) y las 7 vistas (`overview`, `databases`, `pipelines`, `sql_editor`, `statistics`, `modeling`, `web_scraping`), preservando **todos** los hooks de JS (IDs, `onclick`, estructura del DOM). Se actualizó `static/js/app.js` (toasts, skeletons y empty-states a paleta oscura).
- **Correcciones de paso:** `sql_editor.html` usaba tokens Material Design 3 inexistentes (estaba sin estilo) → alineado al sistema nuevo; se agregó "Editor SQL" al menú lateral (la ruta existía pero estaba huérfana); se forzó el estilo oscuro de los campos por encima de la capa base de `@tailwindcss/forms`.
- **Verificación:** las 7 rutas responden `200`; estilos computados confirmados en navegador (paneles `#121214`, acento `#F59E0B`, inputs `#0F0F11`, números mono tabulares). Se añadió `.claude/launch.json` para levantar la app (`apcd-web`, uvicorn).

## 5. Preparación para despliegue (Hugging Face Spaces)
Tras descartar AWS gratuito (el free tier de 1 GB no soporta `torch`/`transformers`, que piden ~4 GB), se preparó el despliegue **gratis** en Hugging Face Spaces (16 GB, ideal para apps con `transformers`):
- `Dockerfile` (SDK docker, puerto 7860, **PyTorch CPU-only**, pre-descarga del modelo de sentimiento, usuario no-root UID 1000).
- `.dockerignore` (excluye `.git`, cachés y `.agents/` de la imagen).
- `README.md` con cabecera YAML de HF (`sdk: docker`, `app_port: 7860`).
- `requirements.txt`: se eliminó `streamlit` (dependencia muerta tras migrar a FastAPI).

## 6. Pestaña de Machine Learning con menú de modelos
Se amplió la pestaña de ML: en vez de una única regresión lineal, ahora el usuario **elige el modelo, las variables de entrada (múltiples), el objetivo y los parámetros**. Funciona con cualquier CSV/TSV (las categóricas se codifican one-hot automáticamente).
- **4 modelos coherentes** (cubren los 3 paradigmas), en `src/modelado.py::entrenar_ml`:
  - **Regresión Lineal** (regresión) — R², RMSE, MAE, coeficientes.
  - **Regresión Logística** (clasificación) — accuracy, F1, matriz de confusión.
  - **Árbol de Decisión** (auto clasif./regresión) — métricas según el objetivo + importancia de variables.
  - **K-Means** (no supervisado) — silhouette, inercia, tamaño de grupos.
- **Backend:** `Modelador.entrenar_ml(modelo, features, target, params)` con preparación robusta (one-hot, manejo de nulos, train/test split 25% cuando hay datos, salida JSON-segura). Endpoints `GET /api/models/features` (numéricas + categóricas), `GET /api/models/catalog` y `POST /api/models/train` (contrato nuevo: `{source, modelo, features[], target, params}`).
- **Frontend (`modeling.html`):** menú de 4 tarjetas, chips de selección múltiple de variables, selector de objetivo (oculto en K-Means), parámetros (k / profundidad) y render de resultados adaptado a cada modelo (coeficientes / importancias / matriz de confusión / grupos).
- **Verificación:** probado con datasets reales del repo y end-to-end por HTTP (subida → features → entrenamiento de los 4 modelos) y manejo de la UI en navegador sin errores de consola.

## 7. Pestaña de Extracción Web con menú de modelos Transformer / BERT
Se amplió la pestaña de scraping: además de extraer tablas (que se guardan en memoria), ahora ofrece un **menú de 5 modelos de NLP** que el usuario aplica al texto de la página. Cada tarjeta indica **qué tipo de página rinde mejor** con ese modelo.
- **5 modelos** (`src/nlp_modelos.py`), con carga diferida y caché de pipelines:
  - **Sentimiento** (DistilBERT SST-2) — reseñas/opiniones.
  - **Resumen** (DistilBART CNN) — noticias/artículos largos.
  - **Clasificación temática zero-shot** (BART-MNLI) — el usuario define las categorías candidatas.
  - **Entidades NER** (BERT-NER) — noticias/biografías; agrupa personas/lugares/organizaciones.
  - **Pregunta-Respuesta** (DistilBERT SQuAD) — páginas informativas; el usuario escribe una pregunta.
- **Flujo en dos zonas** (`web_scraping.html`): (A) extraer la página → tablas + DOM; (B) elegir modelo, opciones (categorías / pregunta) y analizar, con resultados adaptados (clasificación, resumen, barras zero-shot, chips de entidades, respuesta QA).
- **Backend:** `/api/scrape` cachea el texto limpio de la página; nuevos `GET /api/nlp/catalog` y `POST /api/nlp/analyze` (`{tarea, opciones}`). `WebScraper.obtener_texto_limpio()` reutilizable.
- **Compatibilidad:** se fijó `transformers>=4.36,<5` en `requirements.txt` — la v5 eliminó las tareas `summarization` y `question-answering` del registro de pipelines; el rango abierto anterior habría roto esos dos modelos. El `Dockerfile` no pre-descarga modelos (carga diferida, build ligero).
- **Verificación:** validaciones de entrada (sin descargar), y modelos reales end-to-end por HTTP (scrape de Wikipedia → sentiment POSITIVE 0.96, NER agrupado correctamente); UI en navegador con las 5 tarjetas y opciones condicionales, sin errores de consola.

## 8. Cambio de tema: oscuro → claro profesional (legibilidad)
El tema dark-tech tenía poco contraste y texto difícil de leer. Se cambió a un **tema claro de alto contraste** con acento azul cobalto (estilo Linear / Notion). Gracias al sistema de tokens, el cambio fue principalmente en `base.html` (config de Tailwind + clases `.panel`/`.btn-primary`/`.custom-input`, sidebar, header) más unos pocos colores hardcodeados en plantillas (cabeceras sticky, insets de código, hovers) y los toasts de `app.js`.
- **Paleta:** fondo `#F7F8FA`, tarjetas `#FFFFFF`, texto `#18181B` (~16:1), acento `#2563EB`. Todo cumple WCAG AA. Documentado en `DESIGN.md`.
- **Verificación:** las 7 rutas sirven el tema claro sin rastros oscuros (`darkMode`/hex oscuros eliminados de lo servido); render Jinja sin errores.

## 9. Vuelta al oscuro, pero legible (ajuste final de tema)
A petición: se prefería el tema oscuro, pero "no tan oscuro" y con letras legibles. Se volvió al **oscuro suave de alto contraste**: base zinc-900 `#18181B` (en vez de casi-negro), superficies levantadas (`#1F1F23`/`#2A2A30`), bordes más visibles (`#34343C`) y **texto más claro** (`#EDEDEF` principal, `#B4B4BC` secundario, `#8B8B95` terciario) — todo WCAG AA. Acento ámbar `#F59E0B`. Cambios concentrados en `base.html` + hovers (vuelven a base blanca) + toasts oscuros en `app.js`. Verificado: 7 rutas sirven el tema oscuro sin rastros claros; render Jinja OK.
