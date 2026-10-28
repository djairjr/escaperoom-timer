#!/usr/bin/env python3
"""
puzzle_configurator/json_parser.py — Parseador Genérico de config.json

Descobre a estrutura de qualquer JSON recursivamente, determinando:
  - Tipo de dados (number, string, bool, object, array, file_audio, file_path)
  - Hierarquia (campos aninhados como sound_files.tick)
  - Faixas (min/max para numbers)
  - Tamanho máximo para strings
  - Se um path de arquivo aponta para áudio (mp3/wav)

Uso:
    parser = JsonParser()
    schema = parser.parse(config_dict)
    # schema = { "timer_duration_sec": { "type": "number", "min": 0, ... },
    #            "sound_files.tick": { "type": "file_audio", "path": "/home/..." },
    #            "sounds_enabled": { "type": "bool" },
    #            "room_name": { "type": "string", "max_length": 64 } }
"""

import os
import re

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp'}

# Campos conhecidos que são sempre paths de arquivo
KNOWN_FILE_PATH_FIELDS = {
    'sound_files', 'sfx', 'audio_path', 'image_path', 'bg_path',
    'background_music', 'tick', 'alarm', 'victory', 'button_press',
    'button_release', 'penalty_alarm', 'logo_path'
}

# Campos que são sempre booleanos por convenção
KNOWN_BOOL_FIELDS = {
    'sounds_enabled', 'custom_sounds_enabled', 'background_music_enabled',
    'active_high', 'enabled', 'sound_enabled', 'debug', 'verbose'
}


# Order of the top-level fields in the form, most important first. The file's own order cannot be
# trusted: timer-sdl saves config.json through nlohmann::json, which sorts keys alphabetically, and
# then the game duration showed up near the end of the page. Keys not listed keep the file order,
# after these.
FIELD_ORDER = [
    'timer_duration_sec', 'accel_multiplier', 'trap_pause_seconds',
    'victory_timeout_sec', 'room_name', 'idle_message', 'victory_message', 'game_over_message',
    'brightness_pct', 'sounds_enabled', 'sound_volume', 'background_music_enabled',
    'custom_sounds_enabled', 'sound_files', 'mqtt_broker', 'mqtt_port', 'mqtt_username',
    'mqtt_password', 'mqtt_topic_prefix', 'ha_discovery_prefix', 'gpio_out_desarmado',
    'log_verbosity',
]


# Keys older config.json files may still carry that the game no longer uses; never shown in the form.
LEGACY_KEYS = {'penalty_seconds'}


def _ordered_items(data):
    rank = {key: i for i, key in enumerate(FIELD_ORDER)}
    return sorted(((k, v) for k, v in data.items() if k not in LEGACY_KEYS),
                  key=lambda kv: rank.get(kv[0], len(FIELD_ORDER)))


class FieldSchema:
    """Schema de um campo parseado."""
    
    def __init__(self, path, value, parent_key=None):
        self.path = path          # "sound_files.tick"
        self.key = path.split('.')[-1]
        self.parent_key = parent_key
        
        # Determinar tipo
        self.type, self.details = self._infer_type(value)
        
        # Metadados para o formulário
        self.label = self._make_label()
        self.placeholder = self._make_placeholder(value)
    
    def _infer_type(self, value):
        """Determina o tipo do campo a partir do valor."""
        vtype = type(value).__name__
        
        if value is None:
            return 'string', {'nullable': True, 'hint': 'campo nulo'}
        
        if isinstance(value, bool):
            return 'bool', {}
        
        if isinstance(value, int) and not isinstance(value, bool):
            # Determinar faixa provável
            details = {'min': 0, 'max': 999999}
            if 'duration' in self.key.lower() or 'timeout' in self.key.lower() or 'sec' in self.key.lower():
                details = {'min': 1, 'max': 9999, 'unit': 'segundos'}
            elif 'port' in self.key.lower():
                details = {'min': 1, 'max': 65535}
            elif 'volume' in self.key.lower():
                details = {'min': 0, 'max': 128}
            elif 'brightness' in self.key.lower():
                details = {'min': 0, 'max': 100}
            elif 'line' in self.key.lower() and 'gpio' in self.path.lower():
                details = {'min': 0, 'max': 255}
            elif 'delay' in self.key.lower() or 'pause' in self.key.lower():
                details = {'min': 0, 'max': 60, 'unit': 'segundos'}
            elif 'multiplier' in self.key.lower():
                details = {'min': 1, 'max': 10}
            elif 'verbosity' in self.key.lower():
                details = {'min': 0, 'max': 3}
            return 'number', details
        
        if isinstance(value, float):
            details = {'min': 0, 'max': 999999, 'step': 0.1}
            if 'volume' in self.key.lower():
                details = {'min': 0, 'max': 1.0, 'step': 0.01}
            return 'number', details
        
        if isinstance(value, str):
            # Verificar se é um path de arquivo
            if self._is_file_path(value):
                ext = os.path.splitext(value)[1].lower()
                if ext in AUDIO_EXTENSIONS:
                    return 'file_audio', {'current_path': value}
                elif ext in IMAGE_EXTENSIONS:
                    return 'file_image', {'current_path': value}
                else:
                    return 'file_path', {'current_path': value}
            
            # Verificar se é uma string com \n (multi-linha)
            if '\\n' in value or '\n' in value:
                return 'text', {'max_length': 256, 'multiline': True}
            
            # Strings especiais por nome do campo
            if 'password' in self.key.lower() or 'senha' in self.key.lower():
                return 'password', {'max_length': 128}
            
            # Strings comuns
            max_len = min(max(len(value) * 2, 32), 512)
            return 'string', {'max_length': max_len}
        
        if isinstance(value, dict):
            return 'section', {'children_count': len(value)}
        
        if isinstance(value, list):
            return 'array', {'length': len(value)}
        
        return 'string', {}
    
    def _is_file_path(self, value):
        """Heurística para detectar se string é um path de arquivo."""
        if not value or len(value) < 5:
            return False
        
        # Tem extensão de arquivo conhecida
        ext = os.path.splitext(value)[1].lower()
        if ext and len(ext) <= 5:
            # Deve parecer um path (contém / ou \) ou a chave é de arquivo
            if '/' in value or '\\' in value:
                return True
            if self.key in KNOWN_FILE_PATH_FIELDS or self.parent_key in KNOWN_FILE_PATH_FIELDS:
                return True
        
        return False
    
    def _make_label(self):
        """Converte nome técnico em label legível."""
        name = self.key.replace('_', ' ').replace('-', ' ')
        # Capitalizar palavras
        words = name.split()
        label = ' '.join(w.capitalize() for w in words)
        # Ajustes específicos
        label = label.replace('Mqtt', 'MQTT').replace('Ha ', 'HA ')
        label = label.replace('Ssh', 'SSH').replace('Gpio', 'GPIO')
        label = label.replace('Ssid', 'SSID').replace('Wpa', 'WPA')
        label = label.replace('Tcp', 'TCP').replace('Tls', 'TLS')
        label = label.replace('Sdl2', 'SDL2').replace('Kmsdrm', 'KMSDRM')
        return label
    
    def _make_placeholder(self, value):
        """Placeholder amigável."""
        if value is None:
            return ''
        s = str(value)
        if len(s) > 40:
            return s[:37] + '...'
        return s
    
    def to_dict(self):
        d = {
            'path': self.path,
            'key': self.key,
            'type': self.type,
            'label': self.label,
            'placeholder': self.placeholder,
        }
        d.update(self.details)
        return d


class JsonParser:
    """Parseador recursivo que descobre a estrutura de qualquer JSON."""
    
    def parse(self, data, prefix=''):
        """
        Percorre recursivamente o JSON e retorna lista de FieldSchema.
        
        Args:
            data: dict ou list a ser parseado
            prefix: prefixo de caminho para campos aninhados
        
        Returns:
            list[FieldSchema] ordenada por caminho
        """
        fields = []
        
        if isinstance(data, dict):
            items = _ordered_items(data) if not prefix else data.items()
            for key, value in items:
                path = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    # Seção agrupadora
                    section = FieldSchema(path, value)
                    fields.append(section)
                    # Recursão nos filhos
                    fields.extend(self.parse(value, prefix=path))
                elif isinstance(value, list):
                    fields.append(FieldSchema(path, value))
                    # Para listas de objetos simples, mostrar primeiro item como exemplo
                    if value and isinstance(value[0], dict):
                        fields.extend(self.parse(value[0], prefix=f"{path}[0]"))
                else:
                    fields.append(FieldSchema(path, value, parent_key=prefix.split('.')[-1] if prefix else None))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                path = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    fields.extend(self.parse(item, prefix=path))
                else:
                    fields.append(FieldSchema(path, item))
        
        return fields
    
    def parse_to_dicts(self, data):
        """Retorna lista de dicts serializáveis para a API."""
        return [f.to_dict() for f in self.parse(data)]
    
    def group_by_section(self, data):
        """
        Agrupa campos por seção, retornando estrutura aninhada para o template.
        
        Retorna:
            [ { "section": "Timer", "fields": [FieldSchema, ...] },
              { "section": "MQTT", "fields": [...] }, ... ]
        """
        fields = self.parse(data)
        
        # Separar seções (objetos agrupadores) dos campos folha
        sections = []
        current_section = {'section': 'Geral', 'fields': []}
        
        for f in fields:
            if f.type == 'section':
                if current_section['fields']:
                    sections.append(current_section)
                current_section = {'section': f.label, 'fields': []}
            else:
                current_section['fields'].append(f)
        
        if current_section['fields']:
            sections.append(current_section)
        
        return sections


# === Demonstração ===
if __name__ == '__main__':
    import json, sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        # Teste com o config.json do Timer-Nicolau
        data = {
            "timer_duration_sec": 60,
            "trap_pause_seconds": 2,
            "sounds_enabled": True,
            "room_name": "SALA A",
            "idle_message": "PRESS\\nSTART",
            "mqtt_broker": "mqtt.example.lan",
            "mqtt_password": "secret",
            "sound_files": {
                "tick": "/var/lib/timer-nicolau/sfx/tick.mp3",
                "alarm": "/var/lib/timer-nicolau/sfx/error.mp3"
            },
            "gpio_out_desarmado": {
                "line": 21,
                "active_high": False
            }
        }
    
    parser = JsonParser()
    
    print("=== Fields (flat) ===")
    for f in parser.parse(data):
        d = f.to_dict()
        print(f"  {d['path']:40s} {d['type']:12s} label={d['label']}")
    
    print("\n=== Grouped by Section ===")
    for section in parser.group_by_section(data):
        print(f"\n--- {section['section']} ---")
        for f in section['fields']:
            d = f.to_dict()
            print(f"  {d['path']:40s} {d['type']:12s} {d['label']}")
