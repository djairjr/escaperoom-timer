#!/usr/bin/env python3
"""
puzzle_configurator/routes.py — Rotas da API REST e Páginas

Autenticação: POST /login com cookie httponly. NUNCA na URL.
"""

import json
import os
import logging
from flask import request, jsonify, current_app, make_response, redirect

from .form_generator import FormGenerator
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


def _get_setup(key, default=None):
    return current_app.config.get('SETUP', {}).get(key, default)


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
        
        return render_login_page(error='Senha incorreta' if password else None)

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
            html = gen.generate(config_data)
            return html
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
            status_data = {
                'Projeto': setup.get('project_name', 'N/A'),
                'Config': 'OK' if os.path.exists(setup.get('config_path', '')) else 'ausente',
                'Servico': setup.get('service_name', 'N/A'),
                'Arquivos de Som': f"{len(cm.get_sfx_list())} arquivos",
                'Versao': '1.0.0',
            }
            import subprocess
            service = setup.get('service_name', '')
            if service:
                r = subprocess.run(['systemctl', 'is-active', service],
                                 capture_output=True, text=True, timeout=5)
                status_data['Status Puzzle'] = r.stdout.strip()
            
            # IP e Uptime
            r = subprocess.run(['ip', '-4', 'addr', 'show', 'end0'],
                             capture_output=True, text=True, timeout=5)
            import re
            m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', r.stdout)
            status_data['IP'] = m.group(1) if m else 'N/A'
            
            r = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
            status_data['Uptime'] = r.stdout.strip().replace('up ', '') if r.stdout else 'N/A'
            
            return jsonify(status_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

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
        error_html = ''
        if error:
            error_html = f'<p class="error" style="text-align:center;margin-bottom:12px">{error}</p>'
        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configurador - Login</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container login-page">
        <header>
            <img src="/static/logoNicolaudosBrinquedos.svg" alt="Nicolau dos Brinquedos" class="logo">
            <h1>Configurações</h1>
            <p class="subtitle">Nicolau dos Brinquedos &nbsp; @nicolaudosbrinquedos</p>
        </header>
        {error_html}
        <form method="POST" action="/login" class="login-form">
            <div class="form-group">
                <label for="password">Senha de Configuração</label>
                <input type="password" id="password" name="password" 
                       placeholder="Digite a senha" class="form-input" required autofocus>
            </div>
            <button type="submit" class="btn btn-primary">Entrar</button>
        </form>
    </div>
</body>
</html>'''

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
