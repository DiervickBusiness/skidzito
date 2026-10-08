import os, socket
from dotenv import load_dotenv
load_dotenv()  # lê o .env ANTES de importar a Config
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, socketio, login_manager, limiter
from models import User
from werkzeug.middleware.proxy_fix import ProxyFix
from whitenoise import WhiteNoise

app = Flask(__name__)
app.config.from_object(Config)

# 1. Ajuste fino de Reverse Proxy (Para túneis Cloudflare / Nginx)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# 2. Servidor de arquivos estáticos otimizado
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

# 3. Origens permitidas (CORS) - NUNCA use '*' com supports_credentials=True
def _ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

PORTA = int(os.getenv('PORT', 5000))
# Origens locais sempre liberadas (PC + celular na mesma rede) + as do .env (ex.: domínio do Cloudflare)
_locais = [f"http://localhost:{PORTA}", f"http://127.0.0.1:{PORTA}", f"http://{_ip_lan()}:{PORTA}"]
_extras = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'https://app.diervick.com').split(',') if o.strip()]
ALLOWED_ORIGINS = list(dict.fromkeys(_locais + _extras))

# Habilita CORS para as rotas HTTP e WebSockets
CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

# Inicializa extensões
db.init_app(app)

socketio.init_app(
    app, 
    cors_allowed_origins=ALLOWED_ORIGINS, 
    supports_credentials=True
)

login_manager.init_app(app)
login_manager.login_view = 'auth.login'
limiter.init_app(app)

VERSION = "2.0.0"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- HANDLERS DE ERRO PADRONIZADOS EM JSON ---
@app.errorhandler(403)
def forbidden(e):
    return jsonify({"erro": "Sem permissão para acessar este recurso"}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({"erro": "Recurso não encontrado"}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"erro": f"Limite de requisições excedido: {e.description}"}), 429

@app.errorhandler(500)
def server_error(e):
    return jsonify({"erro": "Erro interno do servidor"}), 500

@app.route('/api/version')
def get_version(): 
    return {"version": VERSION}

@app.route('/health')
def health(): 
    return {"status": "ok", "version": VERSION}, 200

# Registra Blueprints
from routes import auth, admin, arquivos, tarefas, main
app.register_blueprint(auth.bp)
app.register_blueprint(admin.bp)
app.register_blueprint(arquivos.bp)
app.register_blueprint(tarefas.bp)
app.register_blueprint(main.bp)

import socket_events

def init_db():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
    with app.app_context():
        db.create_all()
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username='odk').first():
            hashed = generate_password_hash('xebiu')
            admin_user = User(
                username='odk', 
                password=hashed, 
                role='super_admin', 
                criado_por='system'
            )
            db.session.add(admin_user)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=PORTA, debug=False, allow_unsafe_werkzeug=True)