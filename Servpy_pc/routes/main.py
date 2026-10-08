from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import socket, os
from extensions import db
from models import Fixado
from config import Config
from utils import HIERARCHY

bp = Blueprint("main", __name__)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

@bp.route("/")
@login_required
def index():
    from extensions import usuarios_online
    nivel = HIERARCHY.get(current_user.role, 0)
    # nivel 0 = user normal -> blueprint como desktop
    if nivel == 0:
        return render_template("blueprint.html")
    # admin / moderador -> index normal
    agora = datetime.now().strftime("%H:%M:%S")
    return render_template("index.html", ip=get_ip(), user=current_user.username, hora=agora)

@bp.route("/api/status")
def get_status():
    from extensions import usuarios_online
    return jsonify({"online": len(usuarios_online)})

@bp.route("/blueprint")
@login_required
def blueprint():
    return render_template("blueprint.html")

@bp.route("/api/blueprint-data")
@login_required
def blueprint_data():
    return jsonify({"nodes": []})

@bp.route("/api/fixados")
@login_required
def api_fixados():
    fix = Fixado.query.filter_by(user_id=current_user.id).all()
    return jsonify([{"id": f.id, "nome": f.nome, "path": f.path, "caminho": f.path} for f in fix])

@bp.route("/api/fixar", methods=["POST"])
@login_required
def api_fixar():
    data = request.json
    path = data.get("path")
    if not path:
        return jsonify({"ok": False}), 400
    path = os.path.abspath(path)
    # verifica se já existe
    existe = Fixado.query.filter_by(user_id=current_user.id, path=path).first()
    if existe:
        db.session.delete(existe)
        db.session.commit()
        return jsonify({"ok": True, "acao": "removido"})
    novo = Fixado(user_id=current_user.id, nome=os.path.basename(path), path=path)
    db.session.add(novo)
    db.session.commit()
    return jsonify({"ok": True, "acao": "fixado", "id": novo.id})
