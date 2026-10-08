// ===== ESTADO GLOBAL =====
export let usuarioLogado = null;
export let userRole = 'user';
export let userId = null;
export let socket = null;

// ===== CACHE DE PERMISSÃO - OTIMIZAÇÃO =====
export function isAdmin() {
    return userRole === 'super_admin' || userRole === 'admin';
}

export function isStaff() {
    return userRole === 'super_admin' || userRole === 'admin' || userRole === 'moderador';
}

export function isSuperAdmin() {
    return userRole === 'super_admin';
}

// ===== SESSÃO =====
async function carregarSessao() {
    try {
        const res = await fetch('/api/session');
        if (!res.ok) {
            window.location.href = '/login';
            return false;
        }
        const data = await res.json();
        usuarioLogado = data.usuario;
        userRole = data.role;
        userId = data.id;

        // Atualiza UI global
        document.querySelectorAll('.username-display').forEach(el => {
            el.textContent = usuarioLogado;
        });

        // Esconde elementos por role - OTIMIZAÇÃO
        if (!isAdmin()) {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
        }
        if (!isStaff()) {
            document.querySelectorAll('.staff-only').forEach(el => el.style.display = 'none');
        }

        console.log(`[Diervick] Logado como ${usuarioLogado} | Role: ${userRole}`);
        return true;
    } catch (e) {
        console.error('Erro ao carregar sessão:', e);
        window.location.href = '/login';
        return false;
    }
}

// ===== SOCKET.IO =====
function initSocket() {
    // Socket.IO já vem no template via CDN
    socket = io();

    socket.on('connect', () => {
        console.log('[Socket] Conectado');
        // Backend já coloca nos rooms staff/user_id automaticamente
    });

    socket.on('conectado', (data) => {
        console.log(`[Socket] Rooms: ${data.role}`);
    });

    socket.on('disconnect', () => {
        console.log('[Socket] Desconectado');
    });

    // Eventos globais
    socket.on('tarefa_atualizada', (tarefa) => {
        window.dispatchEvent(new CustomEvent('diervick:tarefa_atualizada', { detail: tarefa }));
    });

    socket.on('tarefa_removida', (data) => {
        window.dispatchEvent(new CustomEvent('diervick:tarefa_removida', { detail: data }));
    });

    socket.on('receber_mensagem', (msg) => {
        window.dispatchEvent(new CustomEvent('diervick:chat_msg', { detail: msg }));
    });
}

// ===== DEBOUNCE HELPER - OTIMIZAÇÃO =====
export function debounce(func, delay = 300) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

// ===== FETCH WRAPPER COM AUTH - OTIMIZAÇÃO =====
export async function apiFetch(url, options = {}) {
    const defaultOpt = {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin'
    };
    const res = await fetch(url, {...defaultOpt,...options });
    if (res.status === 401) {
        window.location.href = '/login';
        return null;
    }
    if (res.status === 403) {
        alert('Sem permissão pra essa ação');
        return null;
    }
    return res;
}

// ===== LOGOUT =====
window.logout = async () => {
    await fetch('/logout');
    window.location.href = '/login';
};

// ===== INIT =====
document.addEventListener('DOMContentLoaded', async () => {
    const sessaoOK = await carregarSessao();
    if (!sessaoOK) return;

    initSocket();

    // Dispara evento pros outros módulos iniciarem
    window.dispatchEvent(new CustomEvent('diervick:ready', {
        detail: { usuarioLogado, userRole, userId }
    }));
});