/**
 * App.js — Lógica principal del Frontend APCD
 * 
 * Skills aplicadas de .agents/skills/impeccable:
 * - [delight.md]        Toast mejorado con iconos, barra de progreso y aria-live
 * - [product.md]        Skeleton loading en vez de spinners
 * - [harden.md]         Prevención de doble-submit, manejo de errores de red
 * - [interaction-design.md] Focus management, aria-live para lectores de pantalla
 * - [animate.md]        Ease-out-quart (cubic-bezier(0.25,1,0.5,1)), 150-300ms
 * - [onboard.md]        Empty states informativos
 */

document.addEventListener('DOMContentLoaded', () => {
    updateSourcesCount();
});

// ─── Contador de fuentes del header ───────────────────────────────
async function updateSourcesCount() {
    try {
        const response = await fetch('/api/sources');
        const data = await response.json();
        const count = data.sources ? data.sources.length : 0;
        
        const badge = document.getElementById('sources-count-badge');
        if (badge) {
            badge.textContent = `Fuentes: ${count}`;
        }
    } catch (error) {
        console.error("Error al obtener el conteo de fuentes:", error);
    }
}

// ─── [delight.md] Sistema de Toasts mejorado ──────────────────────
// Iconos por tipo, barra de progreso, aria-live, auto-dismiss con curva de salida
const TOAST_CONFIG = {
    success: {
        icon: 'check_circle',
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        text: 'text-emerald-800',
        iconColor: 'text-emerald-500',
        progress: 'bg-emerald-400',
    },
    error: {
        icon: 'error',
        bg: 'bg-red-50',
        border: 'border-red-200',
        text: 'text-red-800',
        iconColor: 'text-red-500',
        progress: 'bg-red-400',
    },
    warning: {
        icon: 'warning',
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        text: 'text-amber-800',
        iconColor: 'text-amber-500',
        progress: 'bg-amber-400',
    },
    info: {
        icon: 'info',
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        text: 'text-blue-800',
        iconColor: 'text-blue-500',
        progress: 'bg-blue-400',
    },
};

function showToast(message, type = 'info', duration = 4000) {
    const config = TOAST_CONFIG[type] || TOAST_CONFIG.info;
    const container = document.getElementById('toast-container') || document.body;
    
    const toast = document.createElement('div');
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    toast.className = `pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg 
        ${config.bg} ${config.border} ${config.text}
        animate-toast-in relative overflow-hidden max-w-sm`;
    
    toast.innerHTML = `
        <span class="material-symbols-outlined ${config.iconColor} text-[20px] mt-0.5 shrink-0">${config.icon}</span>
        <p class="text-sm font-medium leading-snug flex-1">${message}</p>
        <button onclick="this.closest('[role=alert]').remove()" 
                class="shrink-0 opacity-50 hover:opacity-100 transition-opacity" 
                aria-label="Cerrar notificación">
            <span class="material-symbols-outlined text-[16px]">close</span>
        </button>
        <div class="toast-progress ${config.progress}" style="animation-duration:${duration}ms"></div>
    `;
    
    container.appendChild(toast);
    
    // [animate.md] Auto-dismiss con curva ease-out-quart
    setTimeout(() => {
        toast.style.animation = 'toast-out 0.3s cubic-bezier(0.25, 1, 0.5, 1) forwards';
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, duration);
}

// ─── [product.md] Skeleton loading helpers ────────────────────────
// Crear skeletons con forma del contenido real
function createSkeleton(width = '100%', height = '1rem', className = '') {
    const el = document.createElement('div');
    el.className = `skeleton ${className}`;
    el.style.width = width;
    el.style.height = height;
    el.setAttribute('aria-hidden', 'true');
    return el;
}

function createTableSkeleton(rows = 5, cols = 4) {
    let html = '';
    for (let r = 0; r < rows; r++) {
        html += '<tr class="border-b border-slate-100">';
        for (let c = 0; c < cols; c++) {
            const w = c === 0 ? '60%' : c === cols - 1 ? '30%' : '45%';
            html += `<td class="py-3 px-4"><div class="skeleton" style="width:${w};height:0.875rem"></div></td>`;
        }
        html += '</tr>';
    }
    return html;
}

// ─── [onboard.md] Empty state component ───────────────────────────
function createEmptyState(icon, title, description, actionText, actionCallback) {
    const div = document.createElement('div');
    div.className = 'flex flex-col items-center justify-center py-16 px-8 text-center animate-fade-in';
    div.innerHTML = `
        <div class="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
            <span class="material-symbols-outlined text-slate-400 text-[32px]">${icon}</span>
        </div>
        <h3 class="text-lg font-semibold text-on-surface mb-1">${title}</h3>
        <p class="text-sm text-on-surface-variant max-w-md mb-6 leading-relaxed">${description}</p>
        ${actionText ? `<button class="bg-primary text-white px-5 py-2 rounded-lg text-sm font-medium 
            transition-all duration-200 hover:bg-primary-hover hover:shadow-md 
            active:scale-[0.97]" id="empty-state-action">${actionText}</button>` : ''}
    `;
    if (actionText && actionCallback) {
        div.querySelector('#empty-state-action').addEventListener('click', actionCallback);
    }
    return div;
}

// ─── [harden.md] Prevención de doble-submit ───────────────────────
function lockButton(button, loadingText = 'Procesando...') {
    if (!button) return;
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.innerHTML = `
        <span class="material-symbols-outlined text-sm animate-spin">sync</span>
        ${loadingText}
    `;
}

function unlockButton(button) {
    if (!button) return;
    button.disabled = false;
    if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
    }
}

// ─── [harden.md] Fetch con manejo de errores robusto ──────────────
async function safeFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const message = errorData.detail || `Error ${response.status}`;
            
            if (response.status === 401) {
                showToast('Sesión expirada. Recarga la página.', 'error');
            } else if (response.status === 429) {
                showToast('Demasiadas solicitudes. Intenta en un momento.', 'warning');
            } else if (response.status >= 500) {
                showToast('Error en el servidor. Intenta de nuevo.', 'error');
            } else {
                showToast(message, 'error');
            }
            return { ok: false, data: errorData, status: response.status };
        }
        const data = await response.json();
        return { ok: true, data, status: response.status };
    } catch (error) {
        if (!navigator.onLine) {
            showToast('Sin conexión a internet.', 'error');
        } else {
            showToast('Error de red. Verifica tu conexión.', 'error');
        }
        return { ok: false, data: null, status: 0 };
    }
}

// ─── [animate.md] Stagger animation helper ────────────────────────
// Aplica animación escalonada a elementos hijos (50ms entre cada uno, máximo 500ms total)
function staggerChildren(container, animationClass = 'animate-fade-in') {
    const children = container.children;
    const delay = Math.min(50, 500 / children.length); // [animate.md] cap total stagger
    Array.from(children).forEach((child, i) => {
        child.style.animationDelay = `${i * delay}ms`;
        child.classList.add(animationClass);
    });
}
