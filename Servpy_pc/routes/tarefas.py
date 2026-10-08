from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Tarefa, User
from utils import is_staff, role_required, registrar_log
from extensions import socketio

bp = Blueprint('tarefas', __name__)

@bp.route('/api/tarefas', methods=['GET'])
@login_required
def listar_tarefas():
    if is_staff():
        tarefas = Tarefa.query.order_by(Tarefa.criado_em.desc()).all()
    else:
        tarefas = current_user.tarefas
    return jsonify({"tarefas": [t.to_dict() for t in tarefas]})

# FIX: Pedimos apenas a role 'staff'. O utils.py já entende que admin/super_admin tem acesso.
@bp.route('/api/tarefas/adicionar', methods=['POST'])
@login_required
@role_required('staff') 
def adicionar_tarefa():
    data = request.json
    nova = Tarefa(
        titulo=data.get('titulo'),
        descricao=data.get('descricao', ''),
        criado_por=current_user.id
    )
    user_ids = data.get('user_ids', [])
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        nova.usuarios = users
    else:
        nova.usuarios = [current_user]
        
    db.session.add(nova)
    db.session.commit()
    registrar_log('CRIAR_TAREFA', f'{nova.titulo}')
    socketio.emit('tarefa_atualizada', nova.to_dict(), room='staff')
    
    return jsonify(nova.to_dict())

@bp.route('/api/tarefas/atualizar', methods=['POST'])
@login_required
def atualizar_tarefa():
    dados = request.json
    id_tarefa = dados.get('id')
    tarefa = Tarefa.query.get_or_404(id_tarefa)
    
    if not is_staff() and current_user not in tarefa.usuarios:
        return jsonify({"erro": "Sem permissão"}), 403
        
    if 'titulo' in dados: tarefa.titulo = dados['titulo']
    if 'descricao' in dados: tarefa.descricao = dados['descricao']
    if 'status' in dados:
        tarefa.status = dados['status']
        if dados['status'] == 'concluido':
            tarefa.concluido_por = current_user.username
            tarefa.data_conclusao = datetime.utcnow()
            
    if 'user_ids' in dados and is_staff():
        users = User.query.filter(User.id.in_(dados['user_ids'])).all()
        tarefa.usuarios = users
        
    db.session.commit()
    registrar_log('ATUALIZAR_TAREFA', f'ID {id_tarefa} -> {tarefa.status}')
    socketio.emit('tarefa_atualizada', tarefa.to_dict(), room='staff')
    
    return jsonify({"status": "sucesso"})
    
@bp.route('/api/tarefas/<int:id>', methods=['DELETE'])
@login_required
@role_required('admin') # Apenas admin ou super_admin deletam tarefas
def deletar_tarefa(id):
    tarefa = Tarefa.query.get_or_404(id)
    titulo = tarefa.titulo
    db.session.delete(tarefa)
    db.session.commit()
    registrar_log('DELETAR_TAREFA', titulo)
    socketio.emit('tarefa_atualizada', {'id': id, 'status': 'deletada'}, room='staff')
    return jsonify({"status": "sucesso"})