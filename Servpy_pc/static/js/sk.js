import { usuarioLogado, userRole, socket, apiFetch, isAdmin, isStaff } from './main.js';

let termOutput = null;
let termInput = null;
let chatBox = null;
let chatInput = null;
let usersOnline = null;
let terminalAberto = false;

// ===== INIT =====
window.addEventListener('diervick:ready', initSK);

function initSK() {
    termOutput = document.getElementById('term-out');
    termInput = document.getElementById('terminal-input');
    chatBox = document.getElementById('chat-message');
    chatInput = document.getElementById('input-msg');
    usersOnline = document.getElementById('users-online');
    
    bindTerminal();
    bindChat();
    bindBotoes();
    bindSocketEvents();
    
    logTerminal('DIERVICK TERMINAL v3.0', 'text-blue-400');
    logTerminal(`Conectado como: ${usuarioLogado} [${userRole}]`, 'text-green-400');
    logTerminal('Digite "help" para comandos', 'text-slate-500');
    
    console.log('[SK] Terminal + Chat prontos');
}

// ===== TERMINAL =====
function bindTerminal() {
    if (!termInput) return;
    
    termInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const cmd = termInput.value.trim();
            if (!cmd) return;
            
            logTerminal(`$ ${cmd}`, 'text-yellow-400');
            termInput.value = '';
            
            // Comandos locais
            if (cmd === 'clear') {
                termOutput.innerHTML = '';
                return;
            }
            if (cmd === 'help') {
                mostrarHelp();
                return;
            }
            if (cmd === 'whoami') {
                logTerminal(`${usuarioLogado} - ${userRole}`, 'text-green-400');
                return;
            }
            
            // Envia pro backend via socket
            socket.emit('executar_comando', { comando: cmd });
        }
    });
}

function logTerminal(texto, classe = 'text-slate-300') {
    if (!termOutput) return;
    const linha = document.createElement('div');
    linha.className = classe;
    linha.textContent = texto;
    termOutput.appendChild(linha);
    termOutput.scrollTop = termOutput.scrollHeight;
}

function mostrarHelp() {
    const cmds = [
        'help     - Mostra ajuda',
        'clear    - Limpa terminal',
        'whoami   - Mostra usuário atual',
        'ls       - Lista arquivos',
        'pwd      - Caminho atual',
        'users    - Lista usuários online',
        'tasks    - Lista suas tarefas'
    ];
    cmds.forEach(c => logTerminal(c, 'text-cyan-400'));
}

// ===== CHAT =====
function bindChat() {
    if (!chatInput) return;
    
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const msg = chatInput.value.trim();
            if (!msg) return;
            
            socket.emit('enviar_mensagem', { msg: msg }); // ← FIX: usa 'msg'
            chatInput.value = '';
        }
    });
}





function adicionarMsgChat(data) {
    if (!chatBox) return;
    
    const hora = new Date(data.timestamp || Date.now()).toLocaleTimeString('pt-BR', { 
        hour: '2-digit', minute: '2-digit' 
    });
    
    const msgDiv = document.createElement('div');
    const isEu = data.usuario === usuarioLogado;
    const corUser = isEu? 'text-blue-400' : 'text-green-400';
    
    msgDiv.innerHTML = `
        <span class="text-slate-500 text-xs">[${hora}]</span>
        <span class="${corUser} font-bold">${data.usuario}:</span>
        <span class="text-slate-300 break-words">${data.msg}</span>
    `; // ← FIX: usa data.msg
    
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}





// ===== BOTÕES =====
function bindBotoes() {
    // Abrir terminal
    document.getElementById('btn-terminal')?.addEventListener('click', () => {
        document.getElementById('command-center').classList.remove('hidden');
        document.getElementById('command-center').classList.add('flex');
        terminalAberto = true;
        setTimeout(() => termInput?.focus(), 100);
    });
    
    // Fechar terminal
    document.getElementById('btn-fechar-terminal')?.addEventListener('click', () => {
        document.getElementById('command-center').classList.add('hidden');
        document.getElementById('command-center').classList.remove('flex');
        terminalAberto = false;
    });
    
    // SEO Audit - só placeholder por enquanto
    document.getElementById('btn-seo')?.addEventListener('click', () => {
        document.getElementById('modal-seo').classList.remove('hidden');
        document.getElementById('modal-seo').classList.add('flex');
    });
    
    document.getElementById('btn-fechar-seo')?.addEventListener('click', () => {
        document.getElementById('modal-seo').classList.add('hidden');
        document.getElementById('modal-seo').classList.remove('flex');
    });
    
    // SEO Submit
    document.getElementById('btn-gerar-auditoria')?.addEventListener('click', async () => {
        const url = document.getElementById('seo-url').value.trim();
        if (!url) return alert('Digite uma URL');
        
        const res = await apiFetch('/api/seo/auditar', {
            method: 'POST',
            body: JSON.stringify({ url })
        });
        
        if (res && res.ok) {
            const data = await res.json();
            document.getElementById('seo-score').textContent = data.score;
            document.getElementById('seo-result').classList.remove('hidden');
        }
    });
}





// ===== SOCKET EVENTS =====
// ===== SOCKET EVENTS =====
function bindSocketEvents() {
    if (!socket) return;
    
    socket.on('connect', () => {
        logTerminal('Socket conectado', 'text-green-400');
    });
    
    socket.on('terminal_output', (data) => {
        const cor = data.tipo === 'erro'? 'text-red-400' : 
                    data.tipo === 'comando'? 'text-yellow-400' : 
                    'text-slate-300';
        logTerminal(data.saida, cor);
    });
    
    socket.on('receber_mensagem', (data) => {
        adicionarMsgChat(data);
    });
    
    socket.on('update_online', (data) => {
        const sidebarCounter = document.getElementById('users-online');
        if (sidebarCounter) sidebarCounter.textContent = data.total;
        logTerminal(`Usuários online: ${data.total} → ${data.users.join(', ')}`, 'text-cyan-400');
    });
    
    socket.on('tarefa_atualizada', (tarefa) => {
        if (terminalAberto) {
            logTerminal(`[TASK] ${tarefa.titulo} - ${tarefa.status}`, 'text-yellow-400');
        }
    });

    // FIX: Update instantâneo de usuários
    socket.on('user_atualizado', (data) => {
        logTerminal(`[USER] ${data.acao}: ${data.user?.usuario || data.user_id}`, 'text-yellow-400');
        // Dispara evento pro ui.js atualizar a tabela
        window.dispatchEvent(new CustomEvent('diervick:user_update', { detail: data }));
    });
    
    socket.on('disconnect', () => {
        logTerminal('Socket desconectado', 'text-red-400');
        document.getElementById('users-online').textContent = '0';
    });
    
    socket.on('reconnect', () => {
        logTerminal('Socket reconectado', 'text-green-400');
    });
}




// ===== COMANDOS CUSTOM =====
window.executarComando = (cmd) => {
    if (termInput) {
        termInput.value = cmd;
        termInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    }
};