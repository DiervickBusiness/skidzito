import { userRole, userId, usuarioLogado, isAdmin, isStaff, apiFetch, socket } from './main.js';

let modalTarefa = null;
let modalUsuario = null;
let usuariosCache = [];

// ===== INIT =====
window.addEventListener('diervick:ready', initUI);

async function initUI() {
    modalTarefa = document.getElementById('modal-tarefa');
    modalUsuario = document.getElementById('modal-usuarios');

    bindBotoes();
    await carregarUsuariosSelect();
    bindEventosSocket();
    bindEventosCustom();

    console.log('[UI] Pronta');
}

// ===== BIND BOTÕES =====
function bindBotoes() {
    // Botão nova tarefa
    const btnNovaTarefa = document.getElementById('btn-nova-tarefa');
    if (btnNovaTarefa) {
        if (!isStaff()) btnNovaTarefa.style.display = 'none';
        btnNovaTarefa.addEventListener('click', () => abrirModalTarefa());
    }

    // Toggle Arquivos/Tarefas - OTIMIZADO PARA TAILWIND
    const btnToggleView = document.getElementById('btn-toggle-view');
    if (btnToggleView) {
        btnToggleView.addEventListener('click', () => {
            const secArq = document.getElementById('section-arquivos');
            const secTar = document.getElementById('section-tarefas');
            
            const isArq = !secArq.classList.contains('hidden');

            if (isArq) {
                // Esconde Arquivos, Mostra Tarefas
                secArq.classList.add('hidden');
                secArq.classList.remove('flex', 'flex-col');
                
                secTar.classList.remove('hidden');
                secTar.classList.add('flex', 'flex-col'); 
                
                btnToggleView.textContent = '📋 TAREFAS';
            } else {
                // Esconde Tarefas, Mostra Arquivos
                secTar.classList.add('hidden');
                secTar.classList.remove('flex', 'flex-col');
                
                secArq.classList.remove('hidden');
                secArq.classList.add('flex', 'flex-col'); 
                
                btnToggleView.textContent = '📁 ARQUIVOS';
            }
        });
    }

    // Botão usuários
    const btnUsers = document.getElementById('btn-users');
    if (btnUsers) {
        if (!isAdmin()) btnUsers.style.display = 'none';
        btnUsers.addEventListener('click', () => abrirModalUsuario());
    }

    // Fechar modais
    document.querySelectorAll('.modal.close,.modal.btn-cancel, #btn-fechar-modal, #btn-fechar-usuarios, #btn-fechar-seo').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.closest('.modal').classList.remove('flex');
            e.target.closest('.modal').classList.add('hidden');
        });
    });

    // Submit tarefa
    const formTarefa = document.getElementById('form-tarefa');
    if (formTarefa) {
        formTarefa.addEventListener('submit', async (e) => {
            e.preventDefault();
            await salvarTarefa();
        });
    }

    // Submit usuário
    const formUsuario = document.getElementById('form-usuario');
    if (formUsuario) {
        formUsuario.addEventListener('submit', async (e) => {
            e.preventDefault();
            await salvarUsuario();
        });
    }

    // Sidebar mobile
    document.getElementById('btn-toggle-left')?.addEventListener('click', () => {
        document.getElementById('sidebar-left').classList.toggle('-translate-x-full');
        document.getElementById('overlay').classList.toggle('hidden');
    });
    document.getElementById('btn-toggle-right')?.addEventListener('click', () => {
        document.getElementById('sidebar-right').classList.toggle('translate-x-full');
        document.getElementById('overlay').classList.toggle('hidden');
    });
    document.getElementById('btn-fechar-left')?.addEventListener('click', () => {
        document.getElementById('sidebar-left').classList.add('-translate-x-full');
        document.getElementById('overlay').classList.add('hidden');
    });
    document.getElementById('btn-fechar-right')?.addEventListener('click', () => {
        document.getElementById('sidebar-right').classList.add('translate-x-full');
        document.getElementById('overlay').classList.add('hidden');
    });
    document.getElementById('overlay')?.addEventListener('click', () => {
        document.getElementById('sidebar-left').classList.add('-translate-x-full');
        document.getElementById('sidebar-right').classList.add('translate-x-full');
        document.getElementById('overlay').classList.add('hidden');
    });
}

// ===== MODAL TAREFA =====
function abrirModalTarefa(tarefa = null) {
    const form = document.getElementById('form-tarefa');
    form.reset();

    if (tarefa) {
        form.querySelector('[name=id]').value = tarefa.id;
        form.querySelector('[name=titulo]').value = tarefa.titulo;
        form.querySelector('[name=descricao]').value = tarefa.descricao || '';
        form.querySelector('[name=status]').value = tarefa.status;

        const userIds = tarefa.users.map(u => u.id);
        form.querySelectorAll('[name=user_ids]').forEach(cb => {
            cb.checked = userIds.includes(parseInt(cb.value));
        });

        document.getElementById('modal-tarefa-titulo').textContent = 'Editar Tarefa';
    } else {
        form.querySelector('[name=id]').value = '';
        document.getElementById('modal-tarefa-titulo').textContent = 'Nova Tarefa';
    }

    modalTarefa.classList.remove('hidden');
    modalTarefa.classList.add('flex');
}

async function salvarTarefa() {
    const form = document.getElementById('form-tarefa');
    const id = form.querySelector('[name=id]').value;

    const user_ids = Array.from(form.querySelectorAll('[name=user_ids]:checked'))
       .map(cb => parseInt(cb.value));

    const dados = {
        titulo: form.querySelector('[name=titulo]').value,
        descricao: form.querySelector('[name=descricao]').value,
        status: form.querySelector('[name=status]').value,
        user_ids: user_ids
    };

    let url = '/api/tarefas/adicionar';
    if (id) {
        url = '/api/tarefas/atualizar';
        dados.id = parseInt(id);
    }

    const res = await apiFetch(url, {
        method: 'POST',
        body: JSON.stringify(dados)
    });

    if (res && res.ok) {
        modalTarefa.classList.remove('flex');
        modalTarefa.classList.add('hidden');
    } else {
        alert('Erro ao salvar tarefa');
    }
}

// ===== USUÁRIOS SELECT N:N =====
async function carregarUsuariosSelect() {
    if (!isStaff()) return;

    const res = await apiFetch('/api/admin/listar_usuarios');
    if (!res ||!res.ok) return;

    const data = await res.json();
    usuariosCache = data.usuarios;

    const container = document.getElementById('usuarios-checkboxes');
    if (container) {
        container.innerHTML = data.usuarios.map(u => `
            <label class="checkbox-label">
                <input type="checkbox" name="user_ids" value="${u.id}">
                ${u.usuario} <span class="role-badge">${u.role}</span>
            </label>
        `).join('');
    }

    renderTabelaUsuarios(usuariosCache);
}

// ===== MODAL USUÁRIO =====
function abrirModalUsuario() {
    document.getElementById('form-usuario').reset();
    renderTabelaUsuarios(usuariosCache);
    modalUsuario.classList.remove('hidden');
    modalUsuario.classList.add('flex');
}

async function salvarUsuario() {
    const form = document.getElementById('form-usuario');
    const dados = {
        novo_usuario: form.querySelector('[name=username]').value,
        nova_senha: form.querySelector('[name=password]').value,
        role: form.querySelector('[name=role]').value
    };

    const res = await apiFetch('/api/admin/criar_usuario', {
        method: 'POST',
        body: JSON.stringify(dados)
    });

    if (res && res.ok) {
        form.reset();
    } else {
        const err = await res.json();
        alert(err.erro || 'Erro ao criar usuário');
    }
}

// ===== TABELA USUÁRIOS =====
function renderTabelaUsuarios(users) {
    const tbody = document.getElementById('lista-usuarios');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-slate-500 p-4">Nenhum usuário</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => `
        <tr class="border-b border-slate-800 hover:bg-slate-800/30" data-user-id="${u.id}">
            <td class="p-2 font-medium">${u.usuario}</td>
            <td class="p-2"><span class="px-2 py-1 rounded text-xs ${u.role === 'super_admin'? 'bg-red-600' : u.role === 'admin'? 'bg-yellow-600' : 'bg-slate-600'}">${u.role}</span></td>
            <td class="p-2">
                <span class="${u.ativo? 'text-green-400' : 'text-red-400'}">
                    ${u.ativo? '🟢 Ativo' : '🔴 Inativo'}
                </span>
            </td>
            <td class="p-2 flex gap-2">
                <button onclick="toggleUserAtivo(${u.id}, ${!u.ativo})" class="text-xs bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded">
                    ${u.ativo? 'Desativar' : 'Ativar'}
                </button>
                ${u.usuario!== usuarioLogado? `
                <button onclick="deletarUser('${u.usuario}')" class="text-xs bg-red-600 hover:bg-red-700 px-2 py-1 rounded">Deletar</button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

// ===== FUNÇÕES GLOBAIS DOS BOTÕES =====
window.toggleUserAtivo = async (id, ativo) => {
    await apiFetch('/api/admin/editar_usuario', {
        method: 'POST',
        body: JSON.stringify({ id, ativo })
    });
};

window.deletarUser = async (usuario) => {
    if (!confirm(`Deletar ${usuario}?`)) return;
    await apiFetch('/api/admin/deletar_usuario', {
        method: 'POST',
        body: JSON.stringify({ usuario })
    });
};

// ===== LISTA USERS ONLINE =====
function renderUsersOnline(users) {
    const listaOnline = document.getElementById('lista-users-online');
    if (!listaOnline) return;

    if (users.length === 0) {
        listaOnline.innerHTML = '<div class="text-slate-500 text-sm p-2">Ninguém online</div>';
        return;
    }

    listaOnline.innerHTML = users.map(user => {
        const isEu = user === usuarioLogado;
        const cor = isEu? 'text-blue-400' : 'text-green-400';
        const icone = isEu? '👤' : '🟢';

        return `
            <div class="flex items-center gap-2 p-2 hover:bg-slate-700/50 rounded">
                <span class="text-xs">${icone}</span>
                <span class="${cor} text-sm font-medium">${user}</span>
                ${isEu? '<span class="text-xs text-slate-500">(você)</span>' : ''}
            </div>
        `;
    }).join('');
}

// ===== SOCKET EVENTS =====
function bindEventosSocket() {
    socket.on('update_online', (data) => {
        renderUsersOnline(data.users);
    });

    socket.on('tarefa_atualizada', (tarefa) => {
        console.log('[UI→FT] Tarefa via socket:', tarefa.titulo);
        window.dispatchEvent(new CustomEvent('diervick:tarefa_atualizada', { detail: tarefa }));
    });

    socket.on('user_atualizado', (data) => {
        console.log('[UI] User atualizado:', data);

        if (data.acao === 'criado') {
            usuariosCache.push(data.user);
        } else if (data.acao === 'editado') {
            const idx = usuariosCache.findIndex(u => u.id === data.user.id);
            if (idx >= 0) usuariosCache[idx] = data.user;
        } else if (data.acao === 'deletado') {
            usuariosCache = usuariosCache.filter(u => u.id!== data.user_id);
        }

        if (modalUsuario &&!modalUsuario.classList.contains('hidden')) {
            renderTabelaUsuarios(usuariosCache);
        }
        carregarUsuariosSelect();
    });

    window.addEventListener('diervick:tarefa_atualizada', (e) => {
        console.log('[UI] Tarefa atualizada via socket:', e.detail.titulo);
    });

    window.addEventListener('diervick:tarefa_removida', (e) => {
        console.log('[UI] Tarefa removida:', e.detail.id);
    });
}

// ===== EVENTOS CUSTOM FT.JS =====
function bindEventosCustom() {
    document.addEventListener('diervick:abrir_modal_tarefa', (e) => {
        abrirModalTarefa(e.detail);
    });
}

// ===== DELETE TAREFA =====
window.deletarTarefa = async (id) => {
    if (!isAdmin()) return alert('Sem permissão');
    if (!confirm('Deletar tarefa?')) return;

    const res = await apiFetch(`/api/tarefas/${id}`, { method: 'DELETE' });
    if (!res ||!res.ok) alert('Erro ao deletar');
};
