#!/usr/bin/env python3
"""
puzzle_configurator/routes.py — Rotas da API REST e Páginas

Autenticação: POST /login com cookie httponly. NUNCA na URL.
"""

import html
import json
import os
import re
import socket
import time
import logging
from flask import request, jsonify, current_app, make_response, redirect

from .form_generator import FormGenerator
from .config_manager import ConfigManager
from .i18n import Translator, detect_language

# Settings whose text is drawn on the TV: a typed "\n" means a line break.
MESSAGE_KEYS = ('idle_message', 'victory_message', 'game_over_message', 'room_name')

logger = logging.getLogger(__name__)


def _get_setup(key, default=None):
    return current_app.config.get('SETUP', {}).get(key, default)


def _tr():
    """Translator for the language of the current request."""
    return Translator(detect_language(request, current_app.config.get('SETUP', {})))


def _remember_language(resp):
    """?lang=xx on any page sticks through a cookie."""
    code = request.args.get('lang')
    if code:
        resp.set_cookie('lang', detect_language(request, current_app.config.get('SETUP', {})),
                        max_age=31536000, samesite='Lax')
    return resp


def _get_config_manager():
    return ConfigManager(_get_setup('config_path', '/etc/timer-sdl/config.json'))


def _check_auth(request):
    """Verifica autenticação apenas por cookie httponly."""
    password = _get_setup('http_password')
    if not password:
        return True
    remote_ip = request.remote_addr or ''
    if remote_ip.startswith('192.168.4.'):
        return True
    cookie = request.cookies.get('config_password', '')
    return cookie == password


def _auth_required(f):
    def wrapper(*args, **kwargs):
        if not _check_auth(request):
            return jsonify({'error': 'Não autorizado. Faça login primeiro.'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def register_routes(app):
    """Registra todas as rotas no app Flask."""

    # === LOGIN (POST only, sets httponly cookie) ===
    @app.route('/login', methods=['POST'])
    def login():
        password = _get_setup('http_password')
        body_password = request.form.get('password', '')
        
        if password and body_password == password:
            resp = make_response(('', 302))
            resp.headers['Location'] = '/'
            resp.set_cookie('config_password', password,
                           max_age=86400, httponly=True, samesite='Lax')
            return resp
        
        return render_login_page(error='login.wrong' if password else None)

    @app.route('/logout', methods=['POST'])
    def logout():
        resp = make_response(('', 302))
        resp.headers['Location'] = '/'
        resp.set_cookie('config_password', '', max_age=0, httponly=True, samesite='Lax')
        return resp

    @app.route('/check-auth')
    def check_auth():
        """Endpoint para o JS verificar se o cookie ainda é válido."""
        if _check_auth(request):
            return jsonify({'auth': True})
        return jsonify({'auth': False}), 401

    # === PÁGINA PRINCIPAL ===
    @app.route('/')
    def index():
        if not _check_auth(request):
            return render_login_page()
        
        try:
            cm = _get_config_manager()
            config_data = cm.read()
            gen = FormGenerator()
            html = gen.generate(config_data, tr=_tr())
            return _remember_language(make_response(html))
        except Exception as e:
            logger.error(f"Erro na página principal: {e}")
            return f"<h1>Erro</h1><p>{e}</p>", 500

    # === API: Config ===
    @app.route('/api/config', methods=['GET'])
    @_auth_required
    def api_get_config():
        try:
            return jsonify(_get_config_manager().read())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/config', methods=['POST'])
    @_auth_required
    def api_save_config():
        try:
            new_data = request.get_json(force=True)
            cm = _get_config_manager()
            # Merge: preserva campos que o formulario nao exibe
            # (sound_files, mqtt_*, gpio_out_desarmado, ha_discovery_prefix)
            existing = cm.read()
            # A typed "\\n" (backslash, n) in a screen message becomes a real line break, so config.json
            # holds one meaning only and the page shows it as a line break.
            for key in MESSAGE_KEYS:
                if isinstance(new_data.get(key), str):
                    new_data[key] = re.sub(r'\\+n', '\n', new_data[key]).replace('\r\n', '\n')
            merged = dict(existing)
            # Sobrescreve apenas os campos enviados, preserva o resto
            for k, v in new_data.items():
                if isinstance(v, dict) and k in existing and isinstance(existing[k], dict):
                    # Merge recursivo para objetos aninhados (sound_files, gpio_out_desarmado)
                    merged[k] = dict(existing[k])
                    merged[k].update(v)
                else:
                    merged[k] = v
            cm.save(merged)
            return jsonify({'status': 'ok', 'message': 'Configuração salva'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # === API: Upload de Som ===
    @app.route('/api/upload/<path:field_path>', methods=['POST'])
    @_auth_required
    def api_upload_sound(field_path):
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'Nenhum arquivo enviado'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Nome vazio'}), 400
            
            # Salvar NO SANDBOX — wather move para /var/lib/timer-nicolau/sfx/
            sandbox_sfx = '/sandbox/sfx/'
            os.makedirs(sandbox_sfx, exist_ok=True)
            
            filename = os.path.basename(file.filename)
            sandbox_path = os.path.join(sandbox_sfx, filename)
            file.save(sandbox_path)
            
            cm = _get_config_manager()
            # Salva caminho do DESTINO FINAL (/var/lib/timer-nicolau/sfx/), nao do sandbox
            final_sfx = '/var/lib/timer-nicolau/sfx/'
            final_path = os.path.join(final_sfx, filename)
            cm.update_field(field_path, final_path)
            
            logger.info(f"Upload: {filename}")
            return jsonify({'status': 'ok', 'message': f'{filename} enviado', 'path': final_path})
        except Exception as e:
            logger.error(f"Erro no upload: {e}")
            return jsonify({'error': str(e)}), 500

    # === API: WiFi ===
    @app.route('/api/wifi/scan', methods=['GET'])
    @_auth_required
    def api_wifi_scan():
        try:
            from .wifi_manager import WiFiManager
            wm = WiFiManager(
                iface_ap=_get_setup('wifi_iface_ap', 'wlan1'),
                iface_client=_get_setup('wifi_iface_client', 'wlan0'),
                ap_prefix=_get_setup('ap_prefix', 'Nicolau'))
            return jsonify(wm.scan_ssids())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/wifi/connect', methods=['POST'])
    @_auth_required
    def api_wifi_connect():
        try:
            body = request.get_json(force=True)
            ssid = body.get('ssid', '')
            password = body.get('password', '')
            if not ssid:
                return jsonify({'success': False, 'error': 'SSID obrigatório'}), 400
            from .wifi_manager import WiFiManager
            wm = WiFiManager(
                iface_ap=_get_setup('wifi_iface_ap', 'wlan1'),
                iface_client=_get_setup('wifi_iface_client', 'wlan0'),
                ap_prefix=_get_setup('ap_prefix', 'Nicolau'))
            return jsonify(wm.connect_client(ssid, password))
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/wifi/ap', methods=['POST'])
    @_auth_required
    def api_wifi_ap():
        try:
            from .wifi_manager import WiFiManager
            wm = WiFiManager(
                iface_ap=_get_setup('wifi_iface_ap', 'wlan1'),
                iface_client=_get_setup('wifi_iface_client', 'wlan0'),
                ap_prefix=_get_setup('ap_prefix', 'Nicolau'))
            status = wm.get_status()
            if status.get('ap_active'):
                wm.stop_ap()
                return jsonify({'success': True, 'active': False, 'message': 'AP desativado'})
            else:
                return jsonify(wm.start_ap())
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # === API: Status ===
    @app.route('/api/status', methods=['GET'])
    @_auth_required
    def api_status():
        try:
            setup = current_app.config.get('SETUP', {})
            cm = _get_config_manager()
            tr = _tr()
            status_data = {
                tr.t('status.project'): setup.get('project_name', 'N/A'),
                tr.t('status.config'): tr.t('status.config_ok') if os.path.exists(setup.get('config_path', '')) else tr.t('status.config_missing'),
                tr.t('status.service'): setup.get('service_name', 'N/A'),
                tr.t('status.sounds'): tr.t('status.sounds_value', len(cm.get_sfx_list())),
                tr.t('status.version'): '1.0.0',
            }
            import subprocess
            service = setup.get('service_name', '')
            if service:
                r = subprocess.run(['systemctl', 'is-active', service],
                                 capture_output=True, text=True, timeout=5)
                status_data[tr.t('status.puzzle')] = r.stdout.strip()
            
            # IP e Uptime
            r = subprocess.run(['ip', '-4', 'addr', 'show', 'end0'],
                             capture_output=True, text=True, timeout=5)
            import re
            m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', r.stdout)
            status_data[tr.t('status.ip')] = m.group(1) if m else 'N/A'
            
            r = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
            status_data[tr.t('status.uptime')] = r.stdout.strip().replace('up ', '') if r.stdout else 'N/A'
            
            return jsonify(status_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # === API: Remote control of the game (play, accel toggle, stop) ===
    # The game listens on a local datagram socket and publishes a small snapshot; this app only
    # sends one word and reads the file, so neither side waits for the other.
    @app.route('/api/game', methods=['GET'])
    @_auth_required
    def api_game():
        path = _get_setup('game_state_path', '/run/timer-nicolau/game.json')
        try:
            if time.time() - os.path.getmtime(path) > 5:
                return jsonify({'available': False})
            with open(path) as f:
                data = json.load(f)
            data['available'] = True
            return jsonify(data)
        except (OSError, ValueError):
            return jsonify({'available': False})

    @app.route('/api/control', methods=['POST'])
    @_auth_required
    def api_control():
        action = (request.get_json(silent=True) or {}).get('action', '')
        if action not in ('play', 'accel', 'stop', 'reset'):
            return jsonify({'success': False, 'error': 'acao invalida'}), 400
        sock_path = _get_setup('control_socket', '/run/timer-nicolau/control.sock')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.settimeout(1)
            sock.sendto(action.encode(), sock_path)
            return jsonify({'success': True})
        except OSError as e:
            return jsonify({'success': False, 'error': str(e)}), 503
        finally:
            sock.close()

    # === API: Reload ===
    @app.route('/api/reload', methods=['POST'])
    @_auth_required
    def api_reload():
        try:
            cm = _get_config_manager()
            cm.signal_reload()
            return jsonify({'status': 'ok', 'message': 'Sinal de reload enviado ao watcher'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # === PÁGINA DE LOGIN ===
    def render_login_page(error=None):
        tr = _tr()
        h = lambda key: html.escape(tr.t(key))
        error_html = ''
        if error:
            error_html = f'<p class="error" style="text-align:center;margin-bottom:12px">{h(error)}</p>'
        options = ''.join('<option value="%s"%s>%s</option>' % (html.escape(c), ' selected' if c == tr.lang else '', html.escape(n))
                          for c, n in tr.languages())
        page = f'''<!DOCTYPE html>
<html lang="{tr.lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{h('login.title')}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container login-page">
        <header>
            <img src="/static/logoNicolaudosBrinquedos.svg" alt="Nicolau dos Brinquedos" class="logo">
            <h1>{h('login.heading')}</h1>
            <p class="subtitle">Nicolau dos Brinquedos &nbsp; @nicolaudosbrinquedos</p>
            <label class="lang-picker">{h('lang.label')}: <select onchange="document.cookie='lang='+this.value+';path=/;max-age=31536000;SameSite=Lax';location.reload()">{options}</select></label>
        </header>
        {error_html}
        <form method="POST" action="/login" class="login-form">
            <div class="form-group">
                <label for="password">{h('login.password')}</label>
                <input type="password" id="password" name="password" 
                       placeholder="{h('login.placeholder')}" class="form-input" required autofocus>
            </div>
            <button type="submit" class="btn btn-primary">{h('login.enter')}</button>
        </form>
    </div>
</body>
</html>'''
        return _remember_language(make_response(page))

    # === CORS (apenas para static files) ===
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        if '/api/' in request.path:
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/') or request.path.startswith('/static/'):
            return jsonify({'error': 'Endpoint não encontrado'}), 404
        # On the access point every name resolves to the board, so phones probing for a captive
        # portal (/generate_204, /hotspot-detect.html, ...) and stale URLs all land here: send
        # them to the configurator instead of a JSON error.
        return redirect('/', code=302)

    logger.info(f"Rotas registradas: {len(app.url_map._rules)} endpoints")
