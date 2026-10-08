from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User
from utils import registrar_log

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        username = request.json.get('usuario') if request.is_json else request.form.get('usuario')
        password = request.json.get('senha') if request.is_json else request.form.get('senha')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            registrar_log('LOGIN', f'User {username}')
            if is_ajax: return jsonify({"sucesso": True})
            return redirect(url_for('main.index'))
        else:
            msg = "Utilizador ou senha incorretos!"
            if is_ajax: return jsonify({"sucesso": False, "erro": msg}), 401
            return render_template('login.html', erro=msg)
    return render_template('login.html')

@bp.route('/logout')
def logout():
    registrar_log('LOGOUT')
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/api/session')
@login_required
def get_session():
    return jsonify({"usuario": current_user.username, "role": current_user.role, "id": current_user.id})