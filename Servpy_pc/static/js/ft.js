import { userId, isAdmin, isStaff, apiFetch, socket, debounce } from './main.js'; // ← FIX: debounce aqui em cima

let tabelaTarefas = null;
let tarefasCache = [];

// ===== INIT =====
window.addEventListener('diervick:ready', initTabela);

// FIX: Escuta evento do ui.js pra update instantâneo
window.addEventListener('diervick:tarefa_atualizada', (e) => {
    const tarefa = e.detail;
    if (tarefa.status === 'deletada') {
        removerLinha(tarefa.id);
    } else {
        atualizarLinha(tarefa);
    }
});

async function initTabela() {
    tabelaTarefas = document.getElementById('tabela-tarefas');
    if (!tabelaTarefas) return;

    await carregarTarefas();
    console.log('[FT] Tabela pronta');
}

// ===== CARREGAR =====
async function carregarTarefas() {
    const res = await apiFetch('/api/tarefas');
    if (!res ||!res.ok) return;

    const data = await res.json();
    tarefasCache = data.tarefas;
    renderizarTabela();
}

function renderizarTabela() {
    if (!tabelaTarefas) return;

    const tbody = tabelaTarefas.querySelector('tbody');
    if (tarefasCache.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center p-4 text-slate-500">Nenhuma tarefa</td></tr>`;
        return;
    }

    tbody.innerHTML = tarefasCache.map(t => linhaHTML(t)).join('');
}

function linhaHTML(t) {
    const podeEditar = isStaff() || (t.users && t.users.some(u => u.id === userId));
    const statusClass = `status-${t.status}`;
    const usersStr = t.users? t.users.map(u => u.username || u.usuario).join(', ') : 'Ninguém';

    return `
        <tr data-id="${t.id}" class="${statusClass}">
            <td>${t.id}</td>
            <td class="titulo">${t.titulo}</td>
            <td>${t.descricao || '-'}</td>
            <td class="users">${usersStr}</td>
            <td><span class="badge ${statusClass}">${t.status}</span></td>
            <td class="acoes flex gap-2">
                ${podeEditar? `<button onclick="editarTarefa(${t.id})" class="btn-edit">✏️</button>` : ''}
                ${isAdmin()? `<button onclick="deletarTarefa(${t.id})" class="btn-del">🗑️</button>` : ''}
            </td>
        </tr>
    `;
}

// ===== FUNÇÕES GLOBAIS - FIX DO TypeError =====
window.deletarTarefa = async (id) => {
    if (!confirm('Deletar tarefa?')) return;

    const res = await apiFetch(`/api/tarefas/${id}`, { method: 'DELETE' });
    if (!res ||!res.ok) {
        alert('Erro ao deletar');
    }
    // Socket atualiza sozinho, não precisa fazer nada
};

window.editarTarefa = (id) => {
    const tarefa = tarefasCache.find(t => t.id === id);
    if (tarefa) {
        document.dispatchEvent(new CustomEvent('diervick:abrir_modal_tarefa', { detail: tarefa }));
    }
};

// ===== SOCKET UPDATE =====
function atualizarLinha(tarefa) {
    const idx = tarefasCache.findIndex(t => t.id === tarefa.id);
    if (idx >= 0) {
        tarefasCache[idx] = tarefa; // Update
    } else {
        tarefasCache.unshift(tarefa); // Nova
    }
    renderizarTabela();
}

function removerLinha(id) {
    tarefasCache = tarefasCache.filter(t => t.id!== id);
    renderizarTabela();
}

// ===== FILTROS =====
window.filtrarTarefas = (status = 'todos') => {
    const tbody = tabelaTarefas.querySelector('tbody');
    const linhas = tbody.querySelectorAll('tr[data-id]');

    linhas.forEach(tr => {
        if (status === 'todos') {
            tr.style.display = '';
        } else {
            tr.style.display = tr.classList.contains(`status-${status}`)? '' : 'none';
        }
    });
};

// ===== BUSCA COM DEBOUNCE =====
window.buscarTarefas = debounce((termo) => {
    const termoL = termo.toLowerCase();
    const linhas = tabelaTarefas.querySelectorAll('tbody tr[data-id]');

    linhas.forEach(tr => {
        const texto = tr.textContent.toLowerCase();
        tr.style.display = texto.includes(termoL)? '' : 'none';
    });
}, 300);