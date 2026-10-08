import os
import subprocess
import threading
from datetime import datetime
from flask import request
from flask_login import current_user
from flask_socketio import join_room, disconnect
from extensions import socketio, usuarios_online
from utils import registrar_log, HIERARCHY

@socketio.on('connect')
def handle_connect(auth):
    # Rejeita na hora conexões não autenticadas
    if not current_user.is_authenticated:
        registrar_log('SOCKET_REJECTED', f'Tentativa de conexão anônima. SID: {request.sid}')
        return False  # Cancela o Handshake WebSocket

    # Mapeia a sessão do usuário
    usuarios_online[request.sid] = {
        'username': current_user.username,
        'role': current_user.role
    }

    # Entra na room INDIVIDUAL com nome do usuário (Resolve o bug de múltiplas abas!)
    join_room(current_user.username)

    # Entra na room STAFF usando a hierarquia unificada
    if HIERARCHY.get(current_user.role, 0) >= 1:
        join_room('staff')

    _broadcast_online()
    registrar_log('SOCKET_CONNECT', f'User: {current_user.username}, SID: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in usuarios_online:
        user_data = usuarios_online.pop(request.sid)
        _broadcast_online()
        registrar_log('SOCKET_DISCONNECT', f'User: {user_data["username"]}')


def _broadcast_online():
    # Agrupa usuários únicos online (mesmo que tenham 10 abas abertas)
    users_unicos = sorted(list({v['username'] for v in usuarios_online.values()}))
    socketio.emit('update_online', {
        "total": len(users_unicos),
        "users": users_unicos
    })


@socketio.on('enviar_mensagem')
def handle_message(data):
    if not current_user.is_authenticated:
        return

    texto = (data.get('msg') or data.get('mensagem') or data.get('texto') or '').strip()
    if not texto:
        return

    user = current_user.username
    payload = {
        'usuario': user,
        'msg': texto,
        'timestamp': datetime.now().isoformat(),
        'privado': False
    }

    # Tratamento para MENSAGEM PRIVADA (@usuario mensagem)
    if texto.startswith('@'):
        partes = texto.split(' ', 1)
        alvo = partes[0][1:].strip()
        msg_limpa = partes[1].strip() if len(partes) > 1 else ""

        if not msg_limpa:
            return

        payload['msg'] = msg_limpa
        payload['privado'] = True
        payload['para'] = alvo

        # Verifica se o alvo está online (procurando na lista de usuários online)
        usuarios_conectados = {v['username'] for v in usuarios_online.values()}

        if alvo in usuarios_conectados:
            # Emite direto nas ROOMS do alvo e do remetente (Funciona em TODAS as abas de ambos!)
            socketio.emit('receber_mensagem', payload, room=alvo)
            if alvo != user:
                socketio.emit('receber_mensagem', payload, room=user)
        else:
            # Notifica o remetente que o usuário alvo está offline
            socketio.emit('receber_mensagem', {
                'usuario': 'Sistema',
                'msg': f'Usuário @{alvo} está offline ou não existe.',
                'timestamp': datetime.now().isoformat(),
                'privado': True,
                'sistema': True
            }, room=request.sid)
    else:
        # Mensagem Pública Broadcast (Para todo mundo)
        socketio.emit('receber_mensagem', payload)


@socketio.on('executar_comando')
def handle_comando(data):
    if not current_user.is_authenticated or current_user.role != 'super_admin':
        socketio.emit('terminal_output', {
            'tipo': 'erro',
            'saida': 'Acesso negado. Apenas super_admin pode executar comandos.\n'
        }, room=request.sid)
        return

    comando = data.get('comando', '').strip()
    if not comando:
        return

    registrar_log('TERMINAL_EXEC', f'CMD: {comando}')

    # Dispara a thread para não travar a aplicação
    thread = threading.Thread(
        target=_executar_comando_thread, 
        args=(comando, request.sid, current_user.username)
    )
    thread.daemon = True
    thread.start()


def _executar_comando_thread(comando, sid, username):
    try:
        socketio.emit('terminal_output', {
            'tipo': 'comando',
            'saida': f'{username}@servindex:~$ {comando}\n'
        }, room=sid)

        cwd = os.getcwd()

        # Executa o subprocesso com stdout/stderr pipe
        processo = subprocess.Popen(
            comando,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd
        )

        # Leitura linha a linha sem travar a captura de novos comandos
        while True:
            linha = processo.stdout.readline()
            if not linha and processo.poll() is not None:
                break
            if linha:
                socketio.emit('terminal_output', {
                    'tipo': 'saida',
                    'saida': linha
                }, room=sid)
                socketio.sleep(0.001)  # Cede o controle ao Event Loop do SocketIO

        processo.stdout.close()
        return_code = processo.wait()

        socketio.emit('terminal_output', {
            'tipo': 'fim',
            'saida': f'\n[Processo finalizado com código {return_code}]\n'
        }, room=sid)

    except Exception as e:
        socketio.emit('terminal_output', {
            'tipo': 'erro',
            'saida': f'Erro ao executar: {str(e)}\n'
        }, room=sid)
