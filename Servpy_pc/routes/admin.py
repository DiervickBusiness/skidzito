from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from extensions import db, socketio
from models import User, AuditLog
# FIX: Importamos o pode_gerenciar do utils para usar uma fonte única de verdade
from utils import admin_required, registrar_log, pode_gerenciar 
import subprocess

bp = Blueprint('admin', __name__)

def log_tentativa_invasao(acao, target_user):
    registrar_log('TENTATIVA_INVASAO', f'{current_user.username} tentou {acao} em {target_user} [{current_user.role}]')

@bp.route('/api/admin/listar_usuarios')
@login_required
@admin_required
def rota_listar_usuarios():
    users = User.query.all()
    return jsonify({"usuarios": [{
        "id": u.id,
        "usuario": u.username,
        "role": u.role,
        "criado_por": u.criado_por,
        "ativo": u.ativo,
        "criado_em": u.criado_em.isoformat()
    } for u in users]})

@bp.route('/api/admin/criar_usuario', methods=['POST'])
@login_required
@admin_required
def rota_criar_usuario():
    dados = request.json
    novo_usuario = dados.get('novo_usuario')
    nova_senha = dados.get('nova_senha')
    role = dados.get('role', 'user')

    if not novo_usuario or not nova_senha:
        return jsonify({"erro": "Usuário e senha obrigatórios"}), 400
    if User.query.filter_by(username=novo_usuario).first():
        return jsonify({"erro": "Usuário já existe"}), 400

    if current_user.role == 'admin' and role in ['admin', 'super_admin']:
        log_tentativa_invasao('CRIAR', f'{novo_usuario} role:{role}')
        return jsonify({"erro": "Sem permissão para criar usuário com esta role"}), 403

    hashed = generate_password_hash(nova_senha)
    user = User(username=novo_usuario, password=hashed, role=role, criado_por=current_user.username, ativo=True)
    db.session.add(user)
    db.session.commit()
    registrar_log('CRIAR_USUARIO', f'{novo_usuario} role:{role}')

    socketio.emit('user_atualizado', {
        'acao': 'criado',
        'user': {
            'id': user.id,
            'usuario': user.username,
            'role': user.role,
            'criado_por': user.criado_por,
            'ativo': user.ativo,
            'criado_em': user.criado_em.isoformat()
        }
    })

    return jsonify({"status": "sucesso", "mensagem": f"Usuário {novo_usuario} criado"})

@bp.route('/api/admin/editar_usuario', methods=['POST'])
@login_required
@admin_required
def rota_editar_usuario():
    dados = request.json
    user_id = dados.get('id')
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        return jsonify({"erro": "Use outro painel para editar seu próprio usuário"}), 400

    # FIX: Usando a função oficial
    if not pode_gerenciar(current_user.role, user.role):
        log_tentativa_invasao('EDITAR', user.username)
        return jsonify({"erro": "Sem permissão: você só pode editar usuários com role inferior"}), 403

    if 'role' in dados:
        nova_role = dados['role']
        if current_user.role == 'admin' and nova_role in ['admin', 'super_admin']:
            log_tentativa_invasao('PROMOVER', f'{user.username} -> {nova_role}')
            return jsonify({"erro": "Sem permissão para promover para esta role"}), 403
        user.role = nova_role

    if 'ativo' in dados:
        user.ativo = dados['ativo']
    if dados.get('nova_senha'):
        user.password = generate_password_hash(dados['nova_senha'])

    db.session.commit()
    registrar_log('EDITAR_USUARIO', f'{user.username} por {current_user.username}')

    socketio.emit('user_atualizado', {
        'acao': 'editado',
        'user': {
            'id': user.id,
            'usuario': user.username,
            'role': user.role,
            'criado_por': user.criado_por,
            'ativo': user.ativo,
            'criado_em': user.criado_em.isoformat()
        }
    })

    return jsonify({"status": "sucesso"})

@bp.route('/api/admin/deletar_usuario', methods=['POST'])
@login_required
@admin_required
def rota_deletar_usuario():
    user_para_remover = request.json.get('usuario')
    if user_para_remover == current_user.username:
        return jsonify({"erro": "Não pode deletar a si mesmo"}), 400

    user = User.query.filter_by(username=user_para_remover).first()
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    # FIX: Usando a função oficial
    if not pode_gerenciar(current_user.role, user.role):
        log_tentativa_invasao('DELETAR', user.username)
        return jsonify({"erro": "Sem permissão: você só pode deletar usuários com role inferior"}), 403

    user_id = user.id
    db.session.delete(user)
    db.session.commit()
    registrar_log('DELETAR_USUARIO', f'{user_para_remover} por {current_user.username}')

    socketio.emit('user_atualizado', {'acao': 'deletado', 'user_id': user_id})
    return jsonify({"status": "sucesso", "mensagem": f"Usuário {user_para_remover} removido"})

@bp.route('/api/admin/logs')
@login_required
@admin_required
def get_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return jsonify({"logs": [{
        "id": l.id,
        "usuario": l.usuario,
        "acao": l.acao,
        "detalhes": l.detalhes,
        "ip": l.ip,
        "timestamp": l.timestamp.isoformat()
    } for l in logs]})

@bp.route('/api/comando', methods=['POST'])
@login_required
@admin_required
def api_executar_comando():
    if current_user.role != 'super_admin':
        log_tentativa_invasao('TERMINAL', 'bloqueado')
        return jsonify({"erro": "Apenas super_admin executa comandos"}), 403

    cmd = request.json.get('cmd')
    if not cmd:
        return jsonify({"saida": "Comando vazio"}), 400
    try:
        saida = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=5, universal_newlines=True)
        registrar_log('TERMINAL', cmd)
        return jsonify({"saida": saida})
    except subprocess.TimeoutExpired:
        return jsonify({"saida": "Erro: Comando excedeu 5s de timeout"}), 500
    except Exception as e:
        return jsonify({"saida": str(e)}), 500