from flask import request, jsonify
from flask_login import current_user
from models import db, AuditLog
from functools import wraps
import hashlib, os, re

# HIERARQUIA: maior número = mais poder. 
HIERARCHY = {'user': 0, 'staff': 1, 'admin': 2, 'super_admin': 3}

def get_role():
    return current_user.role if current_user.is_authenticated else 'user'

def is_admin():
    return HIERARCHY.get(get_role(), 0) >= 2

def is_staff():
    return HIERARCHY.get(get_role(), 0) >= 1

def pode_gerenciar(actor_role, target_role):
    """Usado para impedir que um admin altere um super_admin, por exemplo."""
    return HIERARCHY.get(actor_role, 0) > HIERARCHY.get(target_role, 0)

def role_required(*roles):
    """
    Verifica se o usuário possui exatamente a role OU se a hierarquia dele
    é superior à exigida pela rota.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            user_role = get_role()
            user_level = HIERARCHY.get(user_role, 0)
            
            # Pega o nível mais baixo exigido pela lista de roles passadas
            min_required_level = min([HIERARCHY.get(r, 0) for r in roles]) if roles else 0
            
            # Bloqueia apenas se não tiver a role exata E o nível for inferior
            if user_role not in roles and user_level < min_required_level:
                registrar_log('ACESSO_NEGADO', f'Tentou {request.path} com role {user_role}')
                return jsonify({"erro": "Sem permissão"}), 403
            return fn(*args, **kwargs)
        return decorated
    return wrapper

def requer_role_minima(role_minima):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if HIERARCHY.get(get_role(), 0) < HIERARCHY.get(role_minima, 0):
                registrar_log('ACESSO_NEGADO', f'Role insuficiente: {role_minima}')
                return jsonify({"erro": "Permissão insuficiente"}), 403
            return fn(*args, **kwargs)
        return decorated
    return wrapper

def admin_required(fn):
    return role_required('super_admin', 'admin')(fn)

def registrar_log(acao, detalhes=""):
    try:
        log = AuditLog(
            usuario=current_user.username if current_user.is_authenticated else 'anon',
            acao=acao,
            detalhes=detalhes,
            ip=request.remote_addr if request else '0.0.0.0'
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Erro ao salvar log: {e}")
        db.session.rollback()

def get_file_hash(path):
    hash_md5 = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None


# ---------- Helpers de caminho (compatível com Windows e Linux/Android) ----------
def para_web(p):
    """Caminho sempre com '/' para o frontend (no Windows o os.path usa '\\')."""
    return p.replace('\\', '/') if p else p

def resolver_caminho(c):
    """Converte o caminho recebido do frontend/URL em caminho absoluto nativo."""
    if not c:
        return c
    c = c.replace('\\', '/')
    # URL do tipo /api/media/C:/pasta/arq -> "C:/pasta/arq" (drive letter do Windows)
    if re.match(r'^[A-Za-z]:/', c) or c.startswith('/'):
        return os.path.abspath(c)
    return os.path.abspath('/' + c)

def dentro_de(base, p):
    """True se p == base ou está dentro de base (evita /storage/0 casar com /storage/01)."""
    try:
        base = os.path.normcase(os.path.abspath(base))
        p = os.path.normcase(os.path.abspath(p))
        return os.path.commonpath([base, p]) == base
    except ValueError:  # drives diferentes no Windows
        return False
