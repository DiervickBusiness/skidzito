import { isAdmin, isStaff, apiFetch, debounce, socket } from './main.js';

let caminhoAtual = '';
let raizAtual = '';
let arquivosCache = [];
let editor = null;
let arquivoAberto = null;
let termoBuscaAtual = '';
let arquivosSelecionados = new Set();
let modoSelecao = false;
let paginaAtual = 1;
let temMaisPaginas = true;
let carregandoMais = false;

// ===== INIT =====
window.addEventListener('diervick:ready', initFM);

async function initFM() {
    await carregarArquivos(caminhoAtual);
    bindEventos();
    bindBusca();
    bindEventosSocket();
    bindToolbarSelecao();
    bindScrollInfinito();
    console.log('[FM] File Manager pronto');
}

// ===== CARREGAR ARQUIVOS =====
async function carregarArquivos(caminho, page = 1, busca = termoBuscaAtual, append = false) {
    if (carregandoMais) return;
    carregandoMais = true;

    termoBuscaAtual = busca;
    paginaAtual = page;

    const checkboxRecursiva = document.getElementById('busca-recursiva');
    const recursiva = checkboxRecursiva ? checkboxRecursiva.checked : false;
    const selectOrdenar = document.getElementById('ordenar-por');
    const ordenacao = selectOrdenar ? selectOrdenar.value : 'nome';
    const selectTipo = document.getElementById('filtro-tipo');
    const tipo = selectTipo ? selectTipo.value : '';

    let url = `/api/arquivos?caminho=${encodeURIComponent(caminho)}&page=${page}&limit=50&ordenar=${ordenacao}`;
    if (busca) {
        url += `&busca=${encodeURIComponent(busca)}`;
        if (recursiva) url += `&recursiva=true`;
    }
    if (tipo) url += `&tipo=${tipo}`;

    const res = await apiFetch(url);
    carregandoMais = false;
    if (!res || !res.ok) return;

    const data = await res.json();
    caminhoAtual = data.atual;
    if (data.raiz) raizAtual = data.raiz;

    if (append) {
        arquivosCache = [...arquivosCache, ...data.itens];
    } else {
        arquivosCache = data.itens;
        limparSelecao();
    }

    temMaisPaginas = data.itens.length === 50;

    document.getElementById('display-caminho').textContent = caminhoAtual;
    atualizarInfoDisco(data.disco);
    renderizarGrid();
    renderizarBreadcrumb();
}

// ===== RENDERIZAR GRID - ÍCONES SVG MODERNOS =====
function renderizarGrid() {
    const lista = document.getElementById('lista');
    if (!lista) return;

    if (arquivosCache.length === 0) {
        if (termoBuscaAtual) {
            lista.innerHTML = `<div class="col-span-full text-center text-slate-500 py-8">Nenhum arquivo encontrado para "${escapeHtml(termoBuscaAtual)}"</div>`;
        } else {
            lista.innerHTML = `<div class="col-span-full text-center text-slate-500 py-8">Pasta vazia</div>`;
        }
        return;
    }

    const iconPasta = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-1"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>`;

    lista.innerHTML = arquivosCache.map(item => {
        const isFolder = item.is_dir;
        const icon = isFolder ? iconPasta : getFileIcon(item.nome);
        const tamanho = isFolder ? '' : formatarTamanho(item.tamanho);
        const selecionado = arquivosSelecionados.has(item.caminho);
        const nomeExibido = item.caminho_relativo || item.nome;
        const thumbUrl = item.tem_thumb ? `/api/thumb/${item.caminho.substring(1)}` : null;

        return `
            <div class="file-card ${isFolder ? 'folder' : 'file'} ${selecionado ? 'selecionado' : ''} relative" data-path="${item.caminho}" data-isdir="${isFolder}">
                ${modoSelecao && !isFolder ? `
                    <input type="checkbox" class="checkbox-select absolute top-2 left-2 z-10 w-5 h-5 accent-blue-600"
                           ${selecionado ? 'checked' : ''} data-path="${item.caminho}">
                ` : ''}
                ${thumbUrl ? `<img src="${thumbUrl}" class="thumb-preview w-full h-20 object-cover rounded mb-1" loading="lazy">` : `<div class="icon text-slate-400 mb-1">${icon}</div>`}
                <div class="nome text-xs font-medium" title="${item.caminho}">${nomeExibido}</div>
                ${tamanho ? `<div class="text-slate-500 text-[10px] mt-1">${tamanho}</div>` : ''}
            </div>
        `;
    }).join('');

    bindCards();
}

function getFileIcon(nome) {
    const ext = nome.split('.').pop().toLowerCase();
    const svgBase = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-1">`;
    
    if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(ext)) {
        return `${svgBase}<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>`;
    }
    if (['mp4', 'webm', 'mov', 'avi', 'mkv'].includes(ext)) {
        return `${svgBase}<rect width="18" height="18" x="3" y="3" rx="2"/><path d="m9 8 6 4-6 4Z"/></svg>`;
    }
    if (['mp3', 'wav', 'ogg', 'm4a'].includes(ext)) {
        return `${svgBase}<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
    }
    if (['zip', 'rar', 'tar', 'gz', '7z'].includes(ext)) {
        return `${svgBase}<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/><path d="m3 15 6-6"/><path d="m15 9 6 6"/></svg>`;
    }
    if (['py', 'js', 'html', 'css', 'json', 'md', 'xml', 'sql', 'sh', 'php', 'env', 'ini', 'conf', 'log'].includes(ext)) {
        return `${svgBase}<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
    }
    if (['pdf'].includes(ext)) {
        return `${svgBase}<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M10 18v-4a2 2 0 1 1 4 0v4"/><path d="M10 14H8"/></svg>`;
    }

    return `${svgBase}<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`;
}

function formatarTamanho(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function renderizarBreadcrumb() {
    const container = document.getElementById('breadcrumb');
    if (!container) return;

    const raiz = (raizAtual || '').replace(/\/+$/, '');
    const relativo = caminhoAtual.startsWith(raiz) ? caminhoAtual.slice(raiz.length) : caminhoAtual;
    const partes = relativo.split('/').filter(p => p);
    let html = `<span class="crumb cursor-pointer hover:text-blue-400" data-path="${raiz || '/'}">/</span>`;
    let caminhoAcum = raiz;

    partes.forEach((parte) => {
        caminhoAcum += '/' + parte;
        html += ` / <span class="crumb cursor-pointer hover:text-blue-400" data-path="${caminhoAcum}">${parte}</span>`;
    });

    container.innerHTML = html;
    container.querySelectorAll('.crumb').forEach(span => {
        span.addEventListener('click', () => {
            termoBuscaAtual = '';
            const inputBusca = document.getElementById('input-busca');
            if (inputBusca) inputBusca.value = '';
            carregarArquivos(span.dataset.path);
        });
    });
}

function atualizarInfoDisco(disco) {
    const el = document.getElementById('info-disco');
    if (!el || !disco) return;
    const livre = formatarTamanho(disco.livre);
    const total = formatarTamanho(disco.total);
    const percentual = ((disco.total - disco.livre) / disco.total * 100).toFixed(0);
    el.innerHTML = `💾 ${livre} livres de ${total} (${percentual}% usado)`;
}

// ===== BIND EVENTOS =====
function bindCards() {
    document.querySelectorAll('.file-card').forEach(card => {
        const path = card.dataset.path;
        const isDir = card.dataset.isdir === 'true';

        const checkbox = card.querySelector('.checkbox-select');
        if (checkbox) {
            checkbox.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleSelecao(path);
            });
        }

        card.addEventListener('click', () => {
            if (modoSelecao && !isDir) {
                toggleSelecao(path);
                return;
            }

            if (isDir) {
                termoBuscaAtual = '';
                const inputBusca = document.getElementById('input-busca');
                const inputBuscaMobile = document.getElementById('input-busca-mobile');
                if (inputBusca) inputBusca.value = '';
                if (inputBuscaMobile) inputBuscaMobile.value = '';
                carregarArquivos(path);
            } else {
                abrirPreview(path);
            }
        });

        card.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            mostrarMenuContexto(e.pageX, e.pageY, path, isDir);
        });
    });
}

function bindEventos() {
    const inputUpload = document.getElementById('input-upload');
    if (inputUpload) {
        inputUpload.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files.length) return;
            await uploadMultiplos(files);
            e.target.value = '';
        });
    }

    const displayCaminho = document.getElementById('display-caminho');
    if (displayCaminho) {
        displayCaminho.addEventListener('click', () => {
            if (caminhoAtual !== raizAtual && caminhoAtual !== '/') {
                termoBuscaAtual = '';
                const inputBusca = document.getElementById('input-busca');
                const inputBuscaMobile = document.getElementById('input-busca-mobile');
                if (inputBusca) inputBusca.value = '';
                if (inputBuscaMobile) inputBuscaMobile.value = '';
                const pai = caminhoAtual.split('/').slice(0, -1).join('/') || '/';
                carregarArquivos(pai);
            }
        });
        displayCaminho.style.cursor = 'pointer';
    }

    const dropZone = document.getElementById('lista');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop', async (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            await uploadMultiplos(e.dataTransfer.files);
        });
    }
}

function bindToolbarSelecao() {
    const btnSelecionar = document.getElementById('btn-toggle-selecao');
    const btnDeletarLote = document.getElementById('btn-deletar-lote');
    const btnCancelarSelecao = document.getElementById('btn-cancelar-selecao');
    const btnCompactarLote = document.getElementById('btn-compactar-lote');

    if (btnSelecionar) {
        btnSelecionar.addEventListener('click', () => {
            modoSelecao = !modoSelecao;
            if (!modoSelecao) limparSelecao();
            renderizarGrid();
            atualizarToolbarSelecao();
        });
    }
    if (btnDeletarLote) btnDeletarLote.addEventListener('click', deletarSelecionados);
    if (btnCancelarSelecao) {
        btnCancelarSelecao.addEventListener('click', () => {
            modoSelecao = false;
            limparSelecao();
            renderizarGrid();
            atualizarToolbarSelecao();
        });
    }
    if (btnCompactarLote) btnCompactarLote.addEventListener('click', compactarSelecionados);
}

function toggleSelecao(path) {
    if (arquivosSelecionados.has(path)) arquivosSelecionados.delete(path);
    else arquivosSelecionados.add(path);
    atualizarToolbarSelecao();
    renderizarGrid();
}

function limparSelecao() {
    arquivosSelecionados.clear();
    atualizarToolbarSelecao();
}

function atualizarToolbarSelecao() {
    const toolbar = document.getElementById('toolbar-selecao');
    const contador = document.getElementById('contador-selecao');
    if (toolbar) {
        if (modoSelecao) {
            toolbar.classList.remove('hidden');
            if (contador) contador.textContent = `${arquivosSelecionados.size} selecionado(s)`;
        } else {
            toolbar.classList.add('hidden');
        }
    }
}

async function deletarSelecionados() {
    if (arquivosSelecionados.size === 0) return;
    if (!confirm(`Mover ${arquivosSelecionados.size} arquivo(s) pra lixeira?`)) return;

    await apiFetch('/api/remover-lote', {
        method: 'POST',
        body: JSON.stringify({ caminhos: Array.from(arquivosSelecionados) })
    });

    modoSelecao = false;
    limparSelecao();
    await carregarArquivos(caminhoAtual);
}

async function compactarSelecionados() {
    if (arquivosSelecionados.size === 0) return;
    const res = await fetch('/api/compactar-stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ caminhos: Array.from(arquivosSelecionados) })
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'arquivos.zip';
    a.click();
}

function bindScrollInfinito() {
    const lista = document.getElementById('lista');
    if (!lista) return;
    lista.addEventListener('scroll', debounce(() => {
        if (carregandoMais || !temMaisPaginas) return;
        const { scrollTop, scrollHeight, clientHeight } = lista;
        if (scrollTop + clientHeight >= scrollHeight - 100) {
            carregarArquivos(caminhoAtual, paginaAtual + 1, termoBuscaAtual, true);
        }
    }, 200));
}

function bindBusca() {
    const inputBusca = document.getElementById('input-busca');
    const inputBuscaMobile = document.getElementById('input-busca-mobile');
    const checkboxRecursiva = document.getElementById('busca-recursiva');
    const selectOrdenar = document.getElementById('ordenar-por');
    const selectTipo = document.getElementById('filtro-tipo');

    const buscar = debounce((termo) => {
        carregarArquivos(caminhoAtual, 1, termo);
    }, 500);

    if (inputBusca) inputBusca.addEventListener('input', e => buscar(e.target.value));
    if (inputBuscaMobile) inputBuscaMobile.addEventListener('input', e => buscar(e.target.value));
    if (checkboxRecursiva) checkboxRecursiva.addEventListener('change', () => { if (termoBuscaAtual) buscar(termoBuscaAtual); });
    if (selectOrdenar) selectOrdenar.addEventListener('change', () => carregarArquivos(caminhoAtual, 1));
    if (selectTipo) selectTipo.addEventListener('change', () => carregarArquivos(caminhoAtual, 1));
}

// ===== SOCKET REALTIME COM TRAVA DE ABA =====
function bindEventosSocket() {
    window.addEventListener('diervick:arquivo_atualizado', (e) => {
        const secArq = document.getElementById('section-arquivos');
        // Só recarrega se a aba de arquivos estiver visível
        if (secArq && !secArq.classList.contains('hidden')) {
            const data = e.detail;
            if (data.arquivo && data.arquivo.path.startsWith(caminhoAtual)) {
                carregarArquivos(caminhoAtual);
            }
            if (data.acao === 'deletado') {
                carregarArquivos(caminhoAtual);
            }
        }
    });
}

async function uploadMultiplos(files) {
    const progresso = document.getElementById('upload-progresso');
    if (progresso) progresso.classList.remove('hidden');

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        await uploadArquivo(file, (percent) => {
            if (progresso) progresso.textContent = `Enviando ${i+1}/${files.length}: ${file.name} - ${percent}%`;
        });
    }

    if (progresso) progresso.classList.add('hidden');
    await carregarArquivos(caminhoAtual);
}

function uploadArquivo(file, onProgress) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('arquivo', file);
        formData.append('caminho', caminhoAtual);

        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && onProgress) {
                const percent = Math.round((e.loaded / e.total) * 100);
                onProgress(percent);
            }
        };
        xhr.onload = () => resolve();
        xhr.onerror = () => reject();
        xhr.open('POST', '/api/upload');
        xhr.send(formData);
    });
}

// ===== VIEWER UNIVERSAL COM FORÇAR LEITURA =====
window.abrirPreview = async (path) => {
    const ext = path.split('.').pop().toLowerCase();
    const codeExts = ['txt', 'py', 'js', 'html', 'css', 'json', 'md', 'sh', 'yml', 'xml', 'log', 'env', 'ini', 'conf'];

    if (codeExts.includes(ext)) {
        return abrirEditor(path);
    }

    const res = await apiFetch(`/api/arquivos/preview-path?path=${encodeURIComponent(path)}`);

    if (!res || !res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 404) {
            alert('Arquivo não cadastrado no banco. Recarregue a pasta.');
        } else {
            alert(data.erro || 'Erro ao carregar preview');
        }
        return;
    }

    const preview = await res.json();
    mostrarModalViewer(preview, path);
};
function mostrarModalViewer(preview, path) {
    const modal = document.getElementById('modal-viewer') || criarModalViewer();
    document.getElementById('viewer-titulo').textContent = preview.nome;
    const container = document.getElementById('viewer-content');

    modal.classList.remove('hidden');
    modal.classList.add('flex');

    switch(preview.tipo_viewer) {
        case 'image':
            container.innerHTML = `<img src="${preview.url_raw}" class="max-w-full max-h-[70vh] mx-auto object-contain">`;
            break;
        case 'video':
            container.innerHTML = `<video src="${preview.url_raw}" controls autoplay class="max-w-full max-h-[70vh] mx-auto"></video>`;
            break;
        case 'audio':
            container.innerHTML = `
                <div class="p-8 text-center">
                    <div class="text-6xl mb-4">🎵</div>
                    <p class="mb-4 font-bold">${preview.nome}</p>
                    <audio src="${preview.url_raw}" controls autoplay class="w-full max-w-md mx-auto"></audio>
                </div>`;
            break;
        case 'pdf':
            container.innerHTML = `<iframe src="${preview.url_raw}" class="w-full h-[70vh]"></iframe>`;
            break;
        case 'code':
            return abrirEditor(path);
        case 'zip':
            container.innerHTML = `
                <div class="text-center p-8">
                    <div class="text-6xl mb-4">📦</div>
                    <p class="mb-2 font-bold">${preview.nome}</p>
                    <p class="text-slate-400 text-sm mb-6">${formatarTamanho(preview.tamanho)}</p>
                    <button onclick="window.open('${preview.url_download}', '_blank')"
                            class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded">⬇️ Baixar ZIP</button>
                </div>`;
            break;
        default:
            container.innerHTML = `
                <div class="text-center p-8">
                    <div class="text-6xl mb-4">📄</div>
                    <p class="mb-2 font-bold">${preview.nome}</p>
                    <p class="text-slate-400 text-sm mb-6">${preview.mimetype || 'Desconhecido'} - ${formatarTamanho(preview.tamanho)}</p>
                    <div class="flex gap-4 justify-center">
                        <button onclick="window.open('${preview.url_download}', '_blank')"
                                class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded text-sm font-bold">⬇️ Baixar</button>
                        <button onclick="fecharViewer(); abrirEditor('${path}')"
                                class="bg-slate-700 hover:bg-slate-600 px-6 py-2 rounded text-sm font-bold border border-slate-500">📝 Forçar Texto</button>
                    </div>
                </div>`;
    }
}



function criarModalViewer() {
    const modal = document.createElement('div');
    modal.id = 'modal-viewer';
    modal.className = 'modal hidden fixed inset-0 bg-black/80 z-50 items-center justify-center p-4';
    modal.innerHTML = `
        <div class="bg-slate-800 rounded-lg max-w-5xl w-full max-h-[90vh] flex flex-col">
            <div class="flex justify-between items-center p-4 border-b border-slate-700">
                <h3 id="viewer-titulo" class="font-bold truncate pr-4 text-sm text-blue-400"></h3>
                <button onclick="fecharViewer()" class="text-xl hover:text-red-400 transition">✕</button>
            </div>
            <div id="viewer-content" class="p-4 overflow-auto flex-1"></div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) fecharViewer();
    });
    return modal;
}

window.fecharViewer = () => {
    const modal = document.getElementById('modal-viewer');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        const video = modal.querySelector('video');
        const audio = modal.querySelector('audio');
        if (video) video.pause();
        if (audio) audio.pause();
        document.getElementById('viewer-content').innerHTML = '';
    }
};

// ===== EDITOR CODEMIRROR =====
async function abrirEditor(path) {
    arquivoAberto = path;
    const nome = path.split('/').pop();

    const res = await fetch(`/api/media/${path.substring(1)}`);
    if (!res.ok) return alert('Erro ao abrir arquivo');

    const conteudo = await res.text();
    const modal = document.getElementById('modal-container');
    const modalContent = document.getElementById('modal-content');
    const modalTitle = document.getElementById('modal-title');

    modalTitle.textContent = `EDITANDO: ${nome}`;
    modalContent.innerHTML = '<textarea id="code-editor"></textarea>';
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    const textarea = document.getElementById('code-editor');
    editor = CodeMirror.fromTextArea(textarea, {
        lineNumbers: true,
        mode: detectarModo(nome),
        theme: 'dracula',
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: true
    });
    editor.setValue(conteudo);
    editor.setSize('100%', '100%');

    document.getElementById('btn-save').onclick = () => salvarArquivo();
    document.getElementById('btn-fechar-modal').onclick = fecharEditor;
    document.getElementById('btn-raw').onclick = () => window.open(`/api/media/${path.substring(1)}`, '_blank');
}

function detectarModo(nome) {
    const ext = nome.split('.').pop().toLowerCase();
    const modos = {
        js: 'javascript', py: 'python', html: 'htmlmixed', css: 'css',
        json: 'javascript', md: 'markdown', yml: 'yaml', yaml: 'yaml',
        sh: 'shell', sql: 'sql', xml: 'xml'
    };
    return modos[ext] || 'text';
}

async function salvarArquivo() {
    if (!editor || !arquivoAberto) return;

    const conteudo = editor.getValue();
    const res = await apiFetch('/api/salvar', {
        method: 'POST',
        body: JSON.stringify({ caminho: arquivoAberto, conteudo })
    });

    if (res && res.ok) {
        alert('Arquivo salvo!');
        fecharEditor();
        await carregarArquivos(caminhoAtual);
    } else {
        alert('Erro ao salvar');
    }
}

function fecharEditor() {
    const modal = document.getElementById('modal-container');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    if (editor) {
        editor.toTextArea();
        editor = null;
    }
    arquivoAberto = null;
}

// ===== MENU CONTEXTO =====
function mostrarMenuContexto(x, y, path, isDir) {
    removerMenuContexto();

    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';

    const acoes = [
        { txt: '👁️ Visualizar', fn: () => abrirPreview(path) },
        { txt: '📝 Renomear', fn: () => renomearArquivo(path) },
        { txt: '📦 Compactar', fn: () => compactarArquivo(path) },
        { txt: '⬇️ Download', fn: () => window.open(`/api/download/${path.substring(1)}`, '_blank') },
    ];

    if (isAdmin()) {
        acoes.push({ txt: '🗑️ Mover pra Lixeira', fn: () => removerArquivo(path), class: 'danger' });
    }

    menu.innerHTML = acoes.map(a =>
        `<button class="${a.class || ''}" data-action="${a.txt}">${a.txt}</button>`
    ).join('');

    menu.querySelectorAll('button').forEach((btn, i) => {
        btn.addEventListener('click', () => {
            acoes[i].fn();
            removerMenuContexto();
        });
    });

    document.body.appendChild(menu);

    setTimeout(() => {
        document.addEventListener('click', removerMenuContexto, { once: true });
    }, 0);
}

function removerMenuContexto() {
    document.querySelectorAll('.context-menu').forEach(m => m.remove());
}

async function renomearArquivo(path) {
    const nome = path.split('/').pop();
    const novo = prompt('Novo nome:', nome);
    if (!novo || novo === nome) return;

    const novoPath = path.split('/').slice(0, -1).concat(novo).join('/');
    const res = await apiFetch('/api/renomear', {
        method: 'POST',
        body: JSON.stringify({ antigo: path, novo: novoPath })
    });

    if (res && res.ok) await carregarArquivos(caminhoAtual);
    else alert('Erro ao renomear');
}

async function compactarArquivo(path) {
    const res = await apiFetch('/api/compactar', {
        method: 'POST',
        body: JSON.stringify({ caminho: path })
    });

    if (res && res.ok) {
        alert('Compactado!');
        await carregarArquivos(caminhoAtual);
    } else alert('Erro ao compactar');
}

async function removerArquivo(path) {
    if (!confirm(`Mover ${path.split('/').pop()} pra lixeira?`)) return;

    const res = await apiFetch('/api/remover', {
        method: 'POST',
        body: JSON.stringify({ caminho: path })
    });

    if (res && res.ok) await carregarArquivos(caminhoAtual);
    else alert('Erro ao mover pra lixeira');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.fmCarregarArquivos = carregarArquivos