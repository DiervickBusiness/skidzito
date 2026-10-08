from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from extensions import db

user_tarefa = db.Table('user_tarefa',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('tarefa_id', db.Integer, db.ForeignKey('tarefa.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user') # super_admin, admin, moderador, user
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    criado_por = db.Column(db.String(80))
    
    tarefas = db.relationship('Tarefa', secondary=user_tarefa, back_populates='usuarios')
    fixados = db.relationship('Fixado', backref='user', lazy=True)
    
    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}

class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20), default='pendente') # pendente, em_progresso, concluido
    criado_por = db.Column(db.Integer, db.ForeignKey('user.id'))
    concluido_por = db.Column(db.String(80))
    data_conclusao = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    usuarios = db.relationship('User', secondary=user_tarefa, back_populates='tarefas')
    criador = db.relationship('User', foreign_keys=[criado_por])
    
    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "status": self.status,
            "criado_por": self.criador.username if self.criador else None,
            "concluido_por": self.concluido_por,
            "data_conclusao": self.data_conclusao.isoformat() if self.data_conclusao else None,
            "users": [u.to_dict() for u in self.usuarios],
            "criado_em": self.criado_em.isoformat()
        }

class Fixado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nome = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'path', name='_user_path_uc'),)

class Arquivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False, unique=True)
    tamanho = db.Column(db.Integer)
    mimetype = db.Column(db.String(100))
    hash_md5 = db.Column(db.String(32))
    dono_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    upload_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    dono = db.relationship('User')
    versoes = db.relationship('ArquivoVersao', backref='arquivo', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'path': self.path,
            'tamanho': self.tamanho,
            'mimetype': self.mimetype,
            'tipo': self.nome.rsplit('.', 1)[-1].lower() if '.' in self.nome else 'file',
            'dono_id': self.dono_id,
            'upload_em': self.upload_em.isoformat() if self.upload_em else None
        }

class ArquivoVersao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    arquivo_id = db.Column(db.Integer, db.ForeignKey('arquivo.id'), nullable=False)
    path_backup = db.Column(db.String(500), nullable=False)
    salvo_por = db.Column(db.String(80))
    salvo_em = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80))
    acao = db.Column(db.String(50)) # LOGIN, CRIAR_TAREFA, DELETAR_ARQUIVO
    detalhes = db.Column(db.Text)
    ip = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)