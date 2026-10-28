#!/usr/bin/env python3
"""
puzzle-configurator — Servidor HTTP para Configuração Universal de Puzzles.

Entrypoint principal. Inicia o servidor Flask na porta configurada.

Uso:
    python3 server.py                          # Usa setup.json local
    python3 server.py --port 8080              # Porta customizada
    python3 server.py --setup /opt/setup.json  # Setup customizado
    python3 server.py --dev                    # Modo desenvolvimento (debug, reload)
    
Para deploy:
    puzzle-configurator.service (systemd)
"""

import sys
import os
import argparse

# Garantir que o pacote está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puzzle_configurator import create_app


def main():
    parser = argparse.ArgumentParser(
        description='Configurador Universal Web para Puzzles Escape Room'
    )
    parser.add_argument('--port', type=int, default=None,
                        help='Porta HTTP (default: do setup.json ou 80)')
    parser.add_argument('--setup', type=str, default='setup.json',
                        help='Path do setup.json (default: setup.json)')
    parser.add_argument('--dev', action='store_true',
                        help='Modo desenvolvimento (debug, reload, port 5000)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host para escutar (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    # Resolver path do setup.json
    setup_path = args.setup
    if not os.path.isabs(setup_path):
        setup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), setup_path)
    
    # Criar app
    app = create_app(setup_path=setup_path)
    setup = app.config.get('SETUP', {})
    
    # Determinar porta
    if args.port:
        port = args.port
    elif args.dev:
        port = 5000
    else:
        port = setup.get('http_port', 80)
    
    # Modo dev
    debug = args.dev
    
    project = setup.get('project_name', 'Puzzle')
    print(f"╔══════════════════════════════════════╗")
    print(f"║  puzzle-configurator v1.0.0          ║")
    print(f"║  Projeto: {project:<28s}║")
    print(f"║  Porta:   http://0.0.0.0:{port:<5d}               ║")
    print(f"║  Config:  {setup.get('config_path', 'N/A'):<25s}║")
    print(f"║  Service: {setup.get('service_name', 'N/A'):<25s}║")
    print(f"╚══════════════════════════════════════╝")
    
    app.run(host=args.host, port=port, debug=debug)


if __name__ == '__main__':
    main()
