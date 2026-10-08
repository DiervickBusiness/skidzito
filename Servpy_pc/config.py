import os

class Config:
    # 1. Segurança de Sessão: Fixa a chave em dev. Em prod usa .env
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_fixa_servindex_2026')
    
    # 2. Banco de Dados
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///diervick.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 3. Diretórios e Armazenamento
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'storage'))
    # Raiz do gerenciador de arquivos. Mude com RAIZ_PADRAO no .env.
    # No Android (Termux) usa o armazenamento interno; no PC usa a pasta "storage" do projeto.
    _raiz_env = os.getenv('RAIZ_PADRAO')
    if _raiz_env:
        RAIZ_PADRAO = os.path.abspath(_raiz_env)
    elif os.path.isdir('/'):
        RAIZ_PADRAO = '/'
    else:
        RAIZ_PADRAO = UPLOAD_FOLDER

    # 4. Limite Global de Payload (100 MB)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024 

    # 5. Cookies: Muda automatico se for HTTPS
    IS_HTTPS = os.getenv('HTTPS', '0') == '1' # vamos setar isso no cloudflare
    
    SESSION_COOKIE_SAMESITE = 'None' if IS_HTTPS else 'Lax'
    SESSION_COOKIE_SECURE = True if IS_HTTPS else False
    SESSION_COOKIE_HTTPONLY = True

    # 6. Rate Limit
    RATELIMIT_STORAGE_URI = "memory://"