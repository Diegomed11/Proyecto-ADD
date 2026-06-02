# Design System — Proyecto APCD (Liquid Glass & Fluid Motion)

## Core Protocol
**Apple-y Liquid Glass (Light Mode):** Una estética extremadamente premium, fresca y luminosa. Utiliza un fondo con degradados de malla (mesh gradients) muy suaves y difusos, sobre los cuales flotan componentes con fuerte `backdrop-blur`. El movimiento es fluido y continuo, emulando la física del mundo real.

## Color Palette (Pastel Mesh + Ocean Accents)

| Token | Hex | Uso |
|-------|------------|-----|
| `--color-bg-mesh-1` | `#F8FAFC` | Fondo base (Slate 50) |
| `--color-bg-mesh-2` | `#E0F2FE` | Gradiente Azul Cielo Suave |
| `--color-bg-mesh-3` | `#D1FAE5` | Gradiente Verde Menta Suave |
| `--color-surface-glass`| `rgba(255, 255, 255, 0.65)` | Tarjetas y contenedores principales (Requiere blur) |
| `--color-border-glass` | `rgba(255, 255, 255, 0.5)` | Bordes y reflejos de las tarjetas |
| `--color-text` | `#0F172A` | Texto principal (Slate 900) |
| `--color-text-muted` | `#64748B` | Texto secundario (Slate 500) |
| `--color-primary` | `#0EA5E9` | Acento Primario (Ocean Blue - Sky 500) |
| `--color-secondary` | `#10B981` | Acento Secundario (Emerald Green) |

## Component Specifications (The Double-Bezel Glass)

### Cards & Containers
- `background: rgba(255, 255, 255, 0.65)`
- `backdrop-filter: blur(24px) saturate(150%)`
- `border: 1px solid rgba(255, 255, 255, 0.5)`
- `box-shadow: 0 8px 32px -4px rgba(15, 23, 42, 0.04), inset 0 1px 1px rgba(255, 255, 255, 0.8)`
- `border-radius: 16px` a `24px` (Squircles suaves)

### Buttons
- **Primario:** Degradado sutil de Azul a Verde Esmeralda (o color sólido saturado), texto blanco. Bordes redondeados completos (`rounded-full` o `12px`).
- **Glass Button:** Fondo `rgba(255,255,255,0.8)`, hover `rgba(255,255,255,1.0)`, sombra difusa.
- **Micro-Motion:** Al hacer hover, `scale(1.02)` y sombra expandida. Al hacer click, `scale(0.97)`. Transiciones con `cubic-bezier(0.34, 1.56, 0.64, 1)`.

## Motion Choreography
1. **Entry Animation (Staggered Fade-Up):** Los elementos aparecen deslizándose hacia arriba (`translateY(20px)`) y aumentando su opacidad a lo largo de 800ms con `cubic-bezier(0.16, 1, 0.3, 1)`.
2. **Perpetual Ambient Motion:** El fondo de malla (mesh gradient) respira lentamente usando animaciones CSS (escala y traslación sutil).
3. **Hover Physics:** Las tarjetas se elevan sutilmente (`-translate-y-1`) y aumentan el destello interior al pasar el cursor.

## Banned Practices
- ❌ Fondos grises monótonos o blancos puros y duros (sin textura o luz).
- ❌ Sombras grises duras (`rgba(0,0,0,0.3)`). Las sombras deben ser ambientales y colorizadas o de muy baja opacidad.
- ❌ Bordes oscuros en contenedores claros. Usa bordes luminosos (blancos transparentes) para emular refracción de luz.
- ❌ Transiciones lineales (`ease-in-out` o `linear`). Usar siempre spring physics simuladas (cubic-bezier).
