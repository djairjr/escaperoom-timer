#!/usr/bin/env python3
"""
puzzle_configurator/__init__.py — App Factory

Cria e configura a aplicação Flask.
"""

import os
import logging

# Configuração simples de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)


def create_app(setup_path='/opt/puzzle-configurator/setup.json'):
    """
    Cria a aplicação Flask configurada.
    
    Args:
        setup_path: path para setup.json com as configs do configurador
    
    Returns:
        Flask app
    """
    from flask import Flask
    from . import routes
    
    app = Flask(__name__,
                static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'),
                static_url_path='/static')
    # Portuguese messages reach the browser as "não", not "não".
    app.json.ensure_ascii = False

    # Carregar setup
    import json
    if os.path.exists(setup_path):
        with open(setup_path) as f:
            app.config['SETUP'] = json.load(f)
    else:
        # Fallback para desenvolvimento
        app.config['SETUP'] = {
            'project_name': 'Timer-Nicolau',
            'config_path': os.environ.get('CONFIG_PATH', '/etc/timer-sdl/config.json'),
            'service_name': os.environ.get('SERVICE_NAME', 'timer-sdl.service'),
            'sfx_path': os.environ.get('SFX_PATH', '/var/lib/timer-nicolau/sfx/'),
            'ap_prefix': 'Nicolau',
            'http_port': int(os.environ.get('HTTP_PORT', 80)),
            'http_password': os.environ.get('HTTP_PASSWORD', 'timersdl1234!'),
            'wifi_iface_ap': os.environ.get('WIFI_IFACE_AP', 'wlan0'),
            'wifi_iface_client': os.environ.get('WIFI_IFACE_CLIENT', 'wlan1'),
            'network_manager': 'systemd-networkd',
        }
    
    # Registrar blueprints/routes
    routes.register_routes(app)
    
    logger = logging.getLogger(__name__)
    setup = app.config['SETUP']
    logger.info(f"Configurador iniciado: {setup.get('project_name')}")
    logger.info(f"  Config: {setup.get('config_path')}")
    logger.info(f"  Service: {setup.get('service_name')}")
    logger.info(f"  SFX: {setup.get('sfx_path')}")
    
    return app
