#!/usr/bin/env python3
"""
puzzle_configurator/config_manager.py — Gerenciamento do config.json

Leitura: do config.json real (/etc/timer-sdl/config.json — the web user can read it)
Escrita: NO SANDBOX (/sandbox/config/config.json) — o watcher root move para o destino.

Upload de som: salva em /sandbox/sfx/ — watcher move para /var/lib/timer-nicolau/sfx/
Reload: touch em /sandbox/reload/timer-sdl — watcher faz SIGHUP
"""

import json
import os
import tempfile
import shutil
import logging

logger = logging.getLogger(__name__)

# Caminhos fixos (NUNCA escrever fora do sandbox)
SANDBOX_CONFIG = '/sandbox/config/config.json'
SANDBOX_SFX = '/sandbox/sfx/'
SANDBOX_RELOAD = '/sandbox/reload/timer-sdl'
ACTUAL_CONFIG = '/etc/timer-sdl/config.json'
ACTUAL_SFX = '/var/lib/timer-nicolau/sfx/'


def _write_atomic(path, data):
    """Escreve arquivo no sandbox de forma atômica (temp + move)."""
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)
    
    content = json.dumps(data, indent=4, ensure_ascii=False) + '\n'
    fd, tmp = tempfile.mkstemp(dir=dir_path, prefix='.tmp_', suffix='.json')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(tmp, 0o644)
        shutil.move(tmp, path)
        return True
    except Exception as e:
        logger.error(f"Erro escrevendo {path}: {e}")
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class ConfigManager:
    """Gerencia config.json — lê do real, escreve no sandbox."""
    
    def __init__(self, config_path=None):
        self.config_path = config_path or ACTUAL_CONFIG
        self._data = None
    
    def read(self):
        """Lê o config.json REAL (/etc/timer-sdl/config.json). The web user can read it."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config não encontrado: {self.config_path}")
            return {}
        with open(self.config_path, 'r') as f:
            self._data = json.load(f)
        return self._data
    
    def save(self, data):
        """Salva config.json NO SANDBOX. O watcher move para o destino real."""
        _write_atomic(SANDBOX_CONFIG, data)
        self._data = data
        logger.info(f"Config salvo no sandbox: {SANDBOX_CONFIG}")
        return True
    
    def update_field(self, path, value):
        """Atualiza campo específico e salva no sandbox."""
        data = self.read()
        keys = path.split('.')
        d = data
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = self._coerce(value, d.get(keys[-1]))
        self.save(data)
    
    def _coerce(self, value, old_val):
        if old_val is None:
            return value
        if isinstance(old_val, bool):
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on', 'sim')
            return bool(value)
        if isinstance(old_val, int):
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        if isinstance(old_val, float):
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        return value
    
    def signal_reload(self):
        """Sinaliza watcher para recarregar o puzzle."""
        os.makedirs(os.path.dirname(SANDBOX_RELOAD), exist_ok=True)
        with open(SANDBOX_RELOAD, 'w') as f:
            f.write('1')
        logger.info("Sinal de reload enviado ao watcher")
        return True
    
    def get_sfx_list(self):
        """Lista arquivos no SFX real (the web user can read it)."""
        if not os.path.isdir(ACTUAL_SFX):
            return []
        files = []
        for f in sorted(os.listdir(ACTUAL_SFX)):
            full = os.path.join(ACTUAL_SFX, f)
            if os.path.isfile(full):
                ext = os.path.splitext(f)[1].lower()
                size_kb = os.path.getsize(full) // 1024
                files.append({'name': f, 'path': full, 'size_kb': size_kb, 'ext': ext})
        return files
