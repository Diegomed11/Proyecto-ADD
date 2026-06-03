# Design System — Proyecto APCD (Oscuro suave, alto contraste)

> Tema **oscuro pero no casi-negro** (base zinc-900), con acento ámbar y **texto claro de alto contraste** para que todo sea legible. Construido sobre tokens en `base.html`: re-tematizar es cambiar valores, no reescribir vistas.

## Core Protocol
Superficies gris-oscuro levantadas (no negro puro), bordes finos visibles, un **único acento ámbar** para acciones/estado, tipografía Geist + Geist Mono con números **tabulares**. Sobrio y legible.

## Color Palette

| Token | Hex | Uso |
|-------|------------|-----|
| `ink` / `background` | `#18181B` | Fondo de página (zinc-900, oscuro suave) |
| `surface` / `.panel` | `#1F1F23` | Tarjetas y contenedores (levantadas) |
| `surface-2` | `#2A2A30` | Chips, insets, barras de fondo, bloques de código |
| `border-glass` | `#34343C` | Bordes y divisores (visibles) |
| `line-strong` | `#46464F` | Bordes de énfasis / inputs |
| `on-surface` | `#EDEDEF` | Texto principal (~14:1) |
| `on-surface-variant` | `#B4B4BC` | Texto secundario (~8:1) |
| `on-surface-dim` | `#8B8B95` | Texto terciario / iconos inactivos (~4.9:1) |
| `primary` (acento ÚNICO) | `#F59E0B` | Ámbar: acciones, foco, estado, nav activa |
| `primary-hover` | `#FBBF24` | Hover del acento |

**Estados semánticos** (tonos claros para legibilidad sobre oscuro): éxito `#4ADE80`, error `#FCA5A5`, aviso `#FBBF24`, info `#7DD3FC`, sobre fondos oscuros tenues.

## Component Specifications

### Paneles (`.panel`)
- `background: #1F1F23` · `border: 1px solid #34343C` · `box-shadow: 0 1px 2px rgba(0,0,0,0.3)` · `border-radius: 8px`.

### Botones
- **Primario (`.btn-primary`):** ámbar `#F59E0B`, **texto casi negro `#1A1206`** (contraste alto). Hover `#FBBF24`.
- **Secundario (`.btn-secondary`):** superficie `#2A2A30`, borde `#46464F`, texto claro.

### Campos (`.custom-input` / `.custom-select`)
- Fondo `#17171B` (inset), borde `#3A3A42`, texto claro, placeholder `#71717A`. Foco: borde ámbar + anillo `rgba(245,158,11,0.18)`. `!important` para ganarle a `@tailwindcss/forms`.

### Datos
- Cifras y celdas en **Geist Mono** con `tabular-nums`. Cabeceras mono `11px` mayúscula, color `on-surface-dim`.

## Accesibilidad / contraste
Texto principal ~14:1, secundario ~8:1, terciario ~4.9:1, ámbar sobre oscuro ~9:1 — todo WCAG AA. Foco visible: anillo ámbar de 2px. Las superficies se levantaron respecto a la versión anterior para que "no se vea tan oscuro".

## Banned Practices
- ❌ Texto gris apagado de bajo contraste (causa de la queja previa) y superficies casi-negras.
- ❌ Gradientes, glassmorphism, fondos mesh, orbes o brillos.
- ❌ Más de un color de acento; sombras negras duras; bordes invisibles.
