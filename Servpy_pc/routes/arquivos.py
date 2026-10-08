from flask import Blueprint, request, jsonify, send_file, send_from_directory, Response
from flask_login import login_required, current_user
import os, shutil, zipfile, mimetypes, subprocess, hashlib, io
import sqlalchemy.exc
from werkzeug.utils import secure_filename
from datetime import datetime
from extensions import db, socketio
from models import Arquivo, ArquivoVersao, Fixado
from utils import registrar_log, get_file_hash, admin_required, is_staff, HIERARCHY, para_web, resolver_caminho, dentro_de
from config import Config
from PIL import Image

bp = Blueprint('arquivos', __name__)
RAIZ_PADRAO = Config.RAIZ_PADRAO
THUMB_CACHE = os.path.join(RAIZ_PADRAO, '.thumb_cache')
LIXEIRA = os.path.join(RAIZ_PADRAO, '.trash')
os.makedirs(RAIZ_PADRAO, exist_ok=True)
os.makedirs(THUMB_CACHE, exist_ok=True)
os.makedirs(LIXEIRA, exist_ok=True)


@bp.route('/api/salvar', methods=['POST'])
@login_required
def salvar_arquivo():
    dados = request.get_json()
    caminho = dados.get('caminho')
    conteudo = dados.get('conteudo')

    if not caminho or conteudo is None:
        return jsonify({'erro': 'Dados incompletos'}), 400

    p = os.path.abspath(caminho)

    # Verifica sandbox para impedir que usuários salvem arquivos fora de sua pasta
    if not verificar_acesso_sandbox(p):
        return jsonify({'erro': 'Acesso negado'}), 403

    # Verifica permissão do dono do arquivo
    arq = Arquivo.query.filter_by(path=p).first()
    nivel = HIERARCHY.get(current_user.role, 0)
    
    if arq and arq.dono_id != current_user.id and nivel < 1:
        return jsonify({'erro': 'Você não tem permissão para editar este arquivo'}), 403

    try:
        # Salva o arquivo no disco
        with open(p, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        
        # Atualiza o tamanho do arquivo no banco de dados, se ele existir
        if arq:
            arq.tamanho = os.path.getsize(p)
            db.session.commit()
            
        registrar_log('EDITAR', p)
        return jsonify({'sucesso': True, 'mensagem': 'Salvo com sucesso!'})
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500



# --- FUNÇÃO HELPER DE SEGURANÇA ---
def verificar_acesso_sandbox(caminho_absoluto):
    """Garante que usuários nível 0 não saiam de sua pasta home."""
    if not dentro_de(RAIZ_PADRAO, caminho_absoluto):
        return False
        
    if HIERARCHY.get(current_user.role, 0) == 0:
        pasta_user = os.path.join(RAIZ_PADRAO, 'home', current_user.username)
        if not dentro_de(pasta_user, caminho_absoluto):
            return False
            
    return True
# ----------------------------------


def gerar_thumbnail(path, tamanho=200):
    try:
        hash_nome = hashlib.md5(path.encode()).hexdigest()
        thumb_path = os.path.join(THUMB_CACHE, f"{hash_nome}.jpg")
        if os.path.exists(thumb_path):
            return thumb_path

        ext = path.rsplit('.', 1)[-1].lower()
        if ext in ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']:
            img = Image.open(path)
            img.thumbnail((tamanho, tamanho))
            img.save(thumb_path, 'JPEG', quality=70)
            return thumb_path
        elif ext in ['mp4', 'webm', 'mov', 'mkv', 'avi']:
            cmd = ['ffmpeg', '-i', path, '-ss', '00:00:01', '-vframes', '1',
                   '-vf', f'scale={tamanho}:-1', '-y', thumb_path]
            subprocess.run(cmd, capture_output=True, timeout=5)
            if os.path.exists(thumb_path):
                return thumb_path
    except FileNotFoundError:
        print("FFMPEG não encontrado. Thumb de vídeo desativado.")
    except subprocess.TimeoutExpired:
        print(f"Timeout gerando thumb: {path}")
    except Exception as e:
        print(f"Erro thumb: {e}")
    return None

@bp.route('/api/arquivos')
@login_required
def listar_arquivos():
    caminho = request.args.get('caminho') or RAIZ_PADRAO
    caminho = resolver_caminho(caminho)

    # TRAVA PATH TRAVERSAL
    if not dentro_de(RAIZ_PADRAO, caminho):
        return jsonify({"erro": "Acesso negado"}), 403

    # TRAVA USER NA PASTA DELE
    if HIERARCHY.get(current_user.role, 0) == 0:
        pasta_user = os.path.join(RAIZ_PADRAO, 'home', current_user.username)
        os.makedirs(pasta_user, exist_ok=True)
        if not dentro_de(pasta_user, caminho):
            caminho = pasta_user

    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    busca = request.args.get('busca', '').lower().strip()
    recursiva = request.args.get('recursiva', 'false').lower() == 'true'
    ordenacao = request.args.get('ordenar', 'nome')
    tipo_filtro = request.args.get('tipo', '')

    try:
        todos_arquivos = []

        if busca and recursiva:
            for root, dirs, files in os.walk(caminho):
                if LIXEIRA in root:
                    continue
                for f in files + dirs:
                    caminho_completo = os.path.join(root, f)
                    if busca in f.lower():
                        todos_arquivos.append(caminho_completo)
        else:
            itens_pasta = os.listdir(caminho)
            if '.trash' in itens_pasta:
                itens_pasta.remove('.trash')
            if busca:
                itens_pasta = [f for f in itens_pasta if busca in f.lower()]
            todos_arquivos = [os.path.join(caminho, f) for f in itens_pasta]

        if tipo_filtro:
            if tipo_filtro == 'folder':
                todos_arquivos = [p for p in todos_arquivos if os.path.isdir(p)]
            elif tipo_filtro == 'video':
                exts = ['mp4', 'webm', 'mov', 'mkv', 'avi']
                todos_arquivos = [p for p in todos_arquivos if not os.path.isdir(p) and p.rsplit('.', 1)[-1].lower() in exts]
            elif tipo_filtro == 'image':
                exts = ['jpg', 'jpeg', 'png', 'webp', 'gif']
                todos_arquivos = [p for p in todos_arquivos if not os.path.isdir(p) and p.rsplit('.', 1)[-1].lower() in exts]

        if ordenacao == 'tamanho':
            todos_arquivos.sort(key=lambda x: os.path.getsize(x) if os.path.exists(x) and not os.path.isdir(x) else 0, reverse=True)
        elif ordenacao == 'data':
            todos_arquivos.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        elif ordenacao == 'tipo':
            todos_arquivos.sort(key=lambda x: x.rsplit('.', 1)[-1].lower() if '.' in x and not os.path.isdir(x) else '')
        else:
            todos_arquivos.sort(key=lambda x: os.path.basename(x).lower())

        inicio = (page - 1) * limit
        fim = inicio + limit
        itens_paginados = todos_arquivos[inicio:fim]
        itens = []
        arquivos_novos = []

        if os.path.normcase(caminho) != os.path.normcase(RAIZ_PADRAO) and page == 1 and not busca:
            itens.append({"nome": "⬅️..", "caminho": para_web(os.path.dirname(caminho)), "is_dir": True, "id": None})

        for p in itens_paginados:
            try:
                f = os.path.basename(p)
                stat = os.stat(p)
                is_dir = os.path.isdir(p)

                if is_dir:
                    arquivo_db = None
                else:
                    arquivo_db = Arquivo.query.filter_by(path=p).first()
                    if not arquivo_db:
                        arquivo_db = Arquivo(
                            nome=f,
                            path=p,
                            tamanho=stat.st_size,
                            mimetype=mimetypes.guess_type(p)[0],
                            hash_md5=None,
                            dono_id=current_user.id
                        )
                        arquivos_novos.append(arquivo_db)

                item_data = {
                    "id": arquivo_db.id if arquivo_db and arquivo_db.id else None,
                    "nome": f,
                    "caminho": para_web(p),
                    "is_dir": is_dir,
                    "tamanho": stat.st_size if not is_dir else 0,
                    "modificado": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "tem_thumb": not is_dir and f.rsplit('.', 1)[-1].lower() in ['jpg', 'jpeg', 'png', 'webp', 'mp4', 'webm', 'mov']
                }

                if busca and recursiva:
                    item_data["caminho_relativo"] = para_web(os.path.relpath(p, caminho))

                itens.append(item_data)
            except Exception as e:
                print(f"Erro ao processar {p}: {e}")

        if arquivos_novos:
            try:
                db.session.add_all(arquivos_novos)
                db.session.commit()
                idx_novo = 0
                for item in itens:
                    if not item['is_dir'] and not item['id'] and idx_novo < len(arquivos_novos):
                        item['id'] = arquivos_novos[idx_novo].id
                        idx_novo += 1
            except sqlalchemy.exc.IntegrityError:
                db.session.rollback()
                for item in itens:
                    if not item['is_dir'] and not item['id']:
                        arq = Arquivo.query.filter_by(path=item['caminho']).first()
                        if arq: item['id'] = arq.id

        try:
            stat_disk = os.statvfs(caminho)
            espaco_livre = stat_disk.f_frsize * stat_disk.f_bavail
            espaco_total = stat_disk.f_frsize * stat_disk.f_blocks
        except AttributeError:
            total, used, livre = shutil.disk_usage(caminho)
            espaco_livre, espaco_total = livre, total

        return jsonify({
            "itens": itens,
            "atual": para_web(caminho),
            "raiz": para_web(RAIZ_PADRAO),
            "total": len(todos_arquivos),
            "disco": {"livre": espaco_livre, "total": espaco_total}
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/thumb/<path:caminho>')
@login_required
def servir_thumbnail(caminho):
    p = resolver_caminho(caminho)
    
    # FIX: Trava lateral ativada
    if not verificar_acesso_sandbox(p):
        return '', 403
        
    thumb = gerar_thumbnail(p)
    if thumb and os.path.exists(thumb):
        return send_file(thumb, mimetype='image/jpeg')
    return '', 404

@bp.route('/api/remover-lote', methods=['POST'])
@login_required
def remover_lote():
    paths = request.json.get('caminhos', [])
    nivel = HIERARCHY.get(current_user.role, 0)
    erros = []
    for p in paths:
        arq = Arquivo.query.filter_by(path=p).first()
        if arq and arq.dono_id != current_user.id and nivel < 1:
            erros.append(f"{p}: Sem permissão")
            continue
        try:
            nome = os.path.basename(p)
            destino_lixeira = os.path.join(LIXEIRA, f"{datetime.now().timestamp()}_{nome}")
            shutil.move(p, destino_lixeira)
            if arq:
                db.session.delete(arq)
        except Exception as e:
            erros.append(f"{p}: {str(e)}")
    db.session.commit()
    registrar_log('MOVER_LIXEIRA_LOTE', f'{len(paths)} arquivos')
    socketio.emit('arquivo_atualizado', {'acao': 'deletado'}, room=current_user.username)
    return jsonify({"sucesso": True, "erros": erros})

@bp.route('/api/compactar-stream', methods=['POST'])
@login_required
def compactar_stream():
    paths = request.json.get('caminhos', [])
    if len(paths) > 1000:
        return jsonify({"erro": "Máximo 1000 arquivos"}), 400

    total_size = sum(os.path.getsize(p) for p in paths if os.path.isfile(p))
    if total_size > 2 * 1024 * 1024 * 1024: # 2GB
        return jsonify({"erro": "Total excede 2GB"}), 400

    def gerar_zip():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                if os.path.isfile(p):
                    z.write(p, os.path.basename(p))
                elif os.path.isdir(p):
                    for root, dirs, files in os.walk(p):
                        for file in files:
                            fp = os.path.join(root, file)
                            z.write(fp, os.path.relpath(fp, os.path.dirname(p)))
        buffer.seek(0)
        yield from buffer
    return Response(gerar_zip(), mimetype='application/zip',
                    headers={'Content-Disposition': 'attachment; filename=arquivos.zip'})

@bp.route('/api/lixeira/restaurar', methods=['POST'])
@login_required
def restaurar_lixeira():
    nome = request.json.get('nome')
    caminho_origem = os.path.join(LIXEIRA, nome)
    caminho_destino = request.json.get('destino', RAIZ_PADRAO)

    if HIERARCHY.get(current_user.role, 0) < 2:
        return jsonify({"erro": "Sem permissão"}), 403

    try:
        shutil.move(caminho_origem, os.path.join(caminho_destino, nome.split('_', 1)[1]))
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/lixeira/esvaziar', methods=['POST'])
@login_required
@admin_required
def esvaziar_lixeira():
    try:
        shutil.rmtree(LIXEIRA)
        os.makedirs(LIXEIRA)
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/upload', methods=['POST'])
@login_required
def upload_arquivo():
    if 'arquivo' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    arquivo = request.files['arquivo']
    caminho_destino = request.form.get('caminho', RAIZ_PADRAO)
    if arquivo.filename == '':
        return jsonify({"erro": "Nome do arquivo vazio"}), 400

    MAX_SIZE = 500 * 1024 * 1024 # 500MB
    arquivo.seek(0, os.SEEK_END)
    if arquivo.tell() > MAX_SIZE:
        return jsonify({"erro": "Arquivo excede 500MB"}), 413
    arquivo.seek(0)

    filename = secure_filename(arquivo.filename)
    destino_final = os.path.join(caminho_destino, filename)
    arquivo.save(destino_final)

    novo = Arquivo(
        nome=filename,
        path=destino_final,
        tamanho=os.path.getsize(destino_final),
        mimetype=mimetypes.guess_type(destino_final)[0],
        hash_md5=get_file_hash(destino_final),
        dono_id=current_user.id
    )
    db.session.add(novo)
    db.session.commit()
    registrar_log('UPLOAD', f'{filename} -> {caminho_destino}')

    socketio.emit('arquivo_atualizado', {
        'acao': 'criado',
        'arquivo': novo.to_dict()
    }, room=current_user.username)

    return jsonify({"status": "sucesso", "mensagem": f"Arquivo {filename} enviado!", "id": novo.id})

@bp.route('/api/remover', methods=['POST'])
@login_required
def remover():
    p = request.json.get('caminho')
    try:
        arq = Arquivo.query.filter_by(path=p).first()
        nivel = HIERARCHY.get(current_user.role, 0)
        if arq and arq.dono_id != current_user.id and nivel < 1:
            return jsonify({"erro": "Sem permissão"}), 403

        arq_id = arq.id if arq else None
        nome = os.path.basename(p)
        destino_lixeira = os.path.join(LIXEIRA, f"{datetime.now().timestamp()}_{nome}")
        shutil.move(p, destino_lixeira)

        if arq:
            db.session.delete(arq)
            db.session.commit()

        registrar_log('MOVER_LIXEIRA', p)

        if arq_id:
            socketio.emit('arquivo_atualizado', {
                'acao': 'deletado',
                'id': arq_id
            }, room=current_user.username)

        return jsonify({"status": "Movido pra lixeira"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/renomear', methods=['POST'])
@login_required
def api_renomear():
    antigo = request.json.get('antigo')
    novo = request.json.get('novo')

    arq = Arquivo.query.filter_by(path=antigo).first()
    nivel = HIERARCHY.get(current_user.role, 0)
    if arq and arq.dono_id != current_user.id and nivel < 1:
        return jsonify({"erro": "Sem permissão"}), 403

    try:
        if os.path.exists(antigo):
            os.rename(antigo, novo)
            if arq:
                arq.path = novo
                arq.nome = os.path.basename(novo)
                db.session.commit()
            registrar_log('RENOMEAR', f'{antigo} -> {novo}')
            return jsonify({"sucesso": True})
        return jsonify({"erro": "Arquivo não encontrado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/mover', methods=['POST'])
@login_required
def api_mover():
    origem = request.json.get('origem')
    destino_pasta = request.json.get('destino')

    arq = Arquivo.query.filter_by(path=origem).first()
    nivel = HIERARCHY.get(current_user.role, 0)
    if arq and arq.dono_id != current_user.id and nivel < 1:
        return jsonify({"erro": "Sem permissão"}), 403

    try:
        shutil.move(origem, destino_pasta)
        novo_path = os.path.join(destino_pasta, os.path.basename(origem))
        if arq:
            arq.path = novo_path
            db.session.commit()
        registrar_log('MOVER', f'{origem} -> {destino_pasta}')
        return jsonify({"sucesso": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/compactar', methods=['POST'])
@login_required
def compactar():
    caminho_origem = request.json.get('caminho')
    nome_zip = caminho_origem + ".zip"
    try:
        with zipfile.ZipFile(nome_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            if os.path.isdir(caminho_origem):
                for root, dirs, files in os.walk(caminho_origem):
                    for file in files:
                        z.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(caminho_origem, '..')))
            else:
                z.write(caminho_origem, os.path.basename(caminho_origem))
        registrar_log('COMPACTAR', nome_zip)
        return jsonify({"sucesso": True, "arquivo": nome_zip})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@bp.route('/api/download/<path:caminho>')
@login_required
def baixar_arquivo(caminho):
    p = resolver_caminho(caminho)
    
    # FIX: Trava lateral ativada
    if not verificar_acesso_sandbox(p):
        return jsonify({"erro": "Acesso negado - Arquivo fora da sua permissão"}), 403
        
    registrar_log('DOWNLOAD', p)
    return send_file(p, as_attachment=True)

@bp.route('/api/media/<path:caminho>')
@login_required
def servir_midia(caminho):
    p = resolver_caminho(caminho)
    
    # FIX: Trava lateral ativada
    if not verificar_acesso_sandbox(p):
        return jsonify({"erro": "Acesso negado"}), 403
        
    return send_from_directory(os.path.dirname(p), os.path.basename(p))

@bp.route('/api/arquivos/preview/<int:id>')
@login_required
def preview_arquivo(id):
    arquivo = Arquivo.query.get_or_404(id)
    if arquivo.dono_id != current_user.id and not is_staff():
        return jsonify({'erro': 'Sem permissão'}), 403

    ext = arquivo.nome.rsplit('.', 1)[-1].lower() if '.' in arquivo.nome else ''
    viewers = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'],
        'video': ['mp4', 'webm', 'mov', 'avi', 'mkv'],
        'audio': ['mp3', 'wav', 'ogg', 'm4a', 'flac'],
        'code': ['txt', 'log', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'sh', 'yml'],
        'pdf': ['pdf'],
        'zip': ['zip', 'rar', '7z', 'tar', 'gz']
    }
    tipo_viewer = next((v for v, exts in viewers.items() if ext in exts), 'download')

    return jsonify({
        'id': arquivo.id,
        'nome': arquivo.nome,
        'tamanho': arquivo.tamanho,
        'mimetype': arquivo.mimetype,
        'tipo_viewer': tipo_viewer,
        'url_raw': f'/api/media/{para_web(arquivo.path).lstrip("/")}',
        'url_download': f'/api/download/{para_web(arquivo.path).lstrip("/")}'
    })

@bp.route('/api/arquivos/preview-path')
@login_required
def preview_arquivo_path():
    path = request.args.get('path')
    if not path:
        return jsonify({'erro': 'Path necessário'}), 400

    arquivo = Arquivo.query.filter_by(path=path).first()
    if not arquivo:
        return jsonify({'erro': 'Arquivo não cadastrado no banco'}), 404

    if arquivo.dono_id != current_user.id and not is_staff():
        return jsonify({'erro': 'Sem permissão'}), 403

    ext = arquivo.nome.rsplit('.', 1)[-1].lower() if '.' in arquivo.nome else ''
    viewers = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'],
        'video': ['mp4', 'webm', 'mov', 'avi', 'mkv'],
        'audio': ['mp3', 'wav', 'ogg', 'm4a', 'flac'],
        'code': ['txt', 'log', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'sh', 'yml'],
        'pdf': ['pdf'],
        'zip': ['zip', 'rar', '7z', 'tar', 'gz']
    }
    tipo_viewer = next((v for v, exts in viewers.items() if ext in exts), 'download')

    return jsonify({
        'id': arquivo.id,
        'nome': arquivo.nome,
        'tamanho': arquivo.tamanho,
        'mimetype': arquivo.mimetype,
        'tipo_viewer': tipo_viewer,
        'url_raw': f'/api/media/{para_web(arquivo.path).lstrip("/")}',
        'url_download': f'/api/download/{para_web(arquivo.path).lstrip("/")}'
    })
    
@bp.route('/api/fixados', methods=['GET'])
@login_required
def listar_fixados():
    fixados = Fixado.query.filter_by(user_id=current_user.id).all()
    return jsonify([{"id": f.id, "nome": f.nome, "path": f.path} for f in fixados])

@bp.route('/api/fixar', methods=['POST'])
@login_required
def fixar():
    dados = request.get_json()
    path = dados.get('path')
    if not path: return jsonify({"erro": "path vazio"}), 400
    existe = Fixado.query.filter_by(user_id=current_user.id, path=path).first()
    if existe: return jsonify({"sucesso": True, "msg": "ja fixado"})
    f = Fixado(user_id=current_user.id, nome=os.path.basename(path), path=path)
    db.session.add(f)
    db.session.commit()
    return jsonify({"sucesso": True, "id": f.id})

@bp.route('/api/desfixar/<int:id>', methods=['POST'])
@login_required
def desfixar(id):
    f = Fixado.query.filter_by(id=id, user_id=current_user.id).first()
    if not f: return jsonify({"erro": "nao achado"}), 404
    db.session.delete(f)
    db.session.commit()
    return jsonify({"sucesso": True})