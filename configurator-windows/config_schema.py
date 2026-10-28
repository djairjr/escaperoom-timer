"""
config_schema.py — Schema do config.json do Timer-Nicolau
Uso: validar e gerar configuração a partir do estado da UI
"""

import json, os

# ============================================================
# Definição de cada campo: nome, tipo, default, faixa, descrição
# ============================================================
FIELDS = [
    # ---- Temporização ----
    {"key": "timer_duration_sec",     "type": int,    "default": 3600, "min": 60,   "max": 7200, "tab": "Geral",      "label": "Duração (s)"},
    {"key": "trap_pause_seconds",     "type": int,    "default": 3,    "min": 0,    "max": 10,    "tab": "Geral",      "label": "Pausa do 1º botão (s)"},
    {"key": "accel_multiplier",       "type": int,    "default": 2,    "min": 1,    "max": 5,    "tab": "Geral",      "label": "Multiplicador Acel."},
    {"key": "victory_timeout_sec",    "type": int,    "default": 600,  "min": 5,    "max": 3600, "tab": "Geral",      "label": "Timeout Vitória (s)"},

    # ---- Display ----
    {"key": "brightness_pct",         "type": int,    "default": 80,   "min": 0,    "max": 100,  "tab": "Display",    "label": "Brilho (%)"},
    {"key": "room_name",              "type": str,    "default": "SALA A",            "tab": "Display",    "label": "Nome da Sala"},
    {"key": "idle_message",           "type": str,    "default": "AMBIENTE\\nSEGURO", "tab": "Display",    "label": "Mensagem IDLE"},
    {"key": "victory_message",        "type": str,    "default": "ACESSO\\nLIBERADO", "tab": "Display",    "label": "Mensagem Vitória"},
    {"key": "game_over_message",      "type": str,    "default": "BOMBA EXPLODIU",    "tab": "Display",    "label": "Mensagem Game Over"},

    # ---- Áudio ----
    {"key": "sounds_enabled",         "type": bool,   "default": True,                "tab": "Áudio",      "label": "Sons Ativados"},
    {"key": "custom_sounds_enabled",  "type": bool,   "default": True,                "tab": "Áudio",      "label": "Sons Customizados"},
    {"key": "background_music_enabled","type": bool,  "default": False,               "tab": "Áudio",      "label": "Música de Fundo"},
    {"key": "sound_volume",           "type": int,    "default": 64,   "min": 0,    "max": 128,  "tab": "Áudio",      "label": "Volume"},

    # ---- GPIO ----
    {"key": "gpio_out_line",          "type": int,    "default": 21,   "min": 0,    "max": 27,   "tab": "GPIO",       "label": "Pino Desarme (line)"},
    {"key": "gpio_out_active_high",   "type": bool,   "default": True,                "tab": "GPIO",       "label": "Active High"},

    # ---- MQTT ----
    {"key": "mqtt_broker",            "type": str,    "default": "",                  "tab": "MQTT",       "label": "Broker"},
    {"key": "mqtt_port",              "type": int,    "default": 1883, "min": 0,    "max": 65535,"tab": "MQTT",       "label": "Porta"},
    {"key": "mqtt_username",          "type": str,    "default": "",                  "tab": "MQTT",       "label": "Usuário"},
    {"key": "mqtt_password",          "type": str,    "default": "",                  "tab": "MQTT",       "label": "Senha"},
    {"key": "mqtt_topic_prefix",      "type": str,    "default": "nicolau/timer/",   "tab": "MQTT",       "label": "Prefixo Tópico"},
    {"key": "ha_discovery_prefix",    "type": str,    "default": "homeassistant",     "tab": "MQTT",       "label": "HA Discovery Prefix"},

    # ---- Avançado ----
    {"key": "log_verbosity",          "type": int,    "default": 1,    "min": 0,    "max": 3,    "tab": "Avançado",   "label": "Log Verbosity"},
]

# Required fields for an export. MQTT is optional: rooms without Home Assistant leave the broker
# empty.
REQUIRED_FIELDS = ["timer_duration_sec", "room_name"]

# Wi-Fi network the board joins (written to wifi.json on the card, never into config.json).
WIFI_FIELDS = [
    {"key": "wifi_ssid",     "type": str, "default": "", "label": "Rede Wi-Fi (SSID)"},
    {"key": "wifi_password", "type": str, "default": "", "label": "Senha do Wi-Fi"},
]

# Chaves dos sound_files
SOUND_KEYS = ["tick", "alarm", "victory", "button_press", "button_release",
              "penalty_alarm", "background_music"]

SOUND_DEFAULTS = {
    "tick": "/var/lib/timer-nicolau/sfx/tick.mp3",
    "alarm": "/var/lib/timer-nicolau/sfx/error.mp3",
    "victory": "/var/lib/timer-nicolau/sfx/sucess.mp3",
    "button_press": "/var/lib/timer-nicolau/sfx/keypress.mp3",
    "button_release": "/var/lib/timer-nicolau/sfx/keypress.mp3",
    "penalty_alarm": "/var/lib/timer-nicolau/sfx/boom.mp3",
    "background_music": "/var/lib/timer-nicolau/sfx/armed.mp3",
}

# ============================================================
# Funções
# ============================================================

def get_default_config() -> dict:
    """Retorna um dict com todos os defaults"""
    cfg = {}
    for f in FIELDS:
        cfg[f["key"]] = f["default"]
    cfg["sound_files"] = dict(SOUND_DEFAULTS)
    return cfg


def validate_config(cfg: dict) -> tuple:
    """
    Valida um dict de configuração.
    Retorna (errors, warnings) — ambas listas de strings.
    errors vazia = pode exportar.
    """
    errors = []
    warnings = []

    # Campos obrigatórios
    for r in REQUIRED_FIELDS:
        if r not in cfg or (isinstance(cfg[r], str) and cfg[r].strip() == ""):
            field_label = next((f["label"] for f in FIELDS if f["key"] == r), r)
            errors.append(f"Campo obrigatório '{field_label}' não preenchido")

    # Tipo e range
    for f in FIELDS:
        key = f["key"]
        if key not in cfg:
            continue
        val = cfg[key]
        expected = f["type"]

        if expected == int:
            if not isinstance(val, int):
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    errors.append(f"'{f['label']}' deve ser um número inteiro")
                    continue
            lo, hi = f.get("min"), f.get("max")
            if lo is not None and val < lo:
                errors.append(f"'{f['label']}' mínimo {lo}")
            if hi is not None and val > hi:
                errors.append(f"'{f['label']}' máximo {hi}")

        elif expected == bool:
            if not isinstance(val, bool):
                errors.append(f"'{f['label']}' deve ser liga/desliga")

    broker = str(cfg.get("mqtt_broker", "")).strip()
    if broker and not (1 <= int(cfg.get("mqtt_port", 0) or 0) <= 65535):
        errors.append("'Porta' MQTT deve estar entre 1 e 65535 quando há Broker")

    # room_name com espaços → warning (não bloqueia)
    room = cfg.get("room_name", "")
    if " " in room:
        warnings.append(f"'{room}' contém espaços — no HA vira '{room.replace(' ', '_')}'")

    return errors, warnings


def sound_path_to_linux(windows_path: str) -> str:
    """Converte um path (Windows ou Unix) para /var/lib/timer-nicolau/sfx/<filename>"""
    if not windows_path or windows_path.strip() == "":
        return ""
    path = windows_path.strip()
    # Suporta \\ e / como separadores (Windows rodando em WSL)
    filename = path.replace("\\", "/").split("/")[-1]
    if not filename:
        return ""
    return f"/var/lib/timer-nicolau/sfx/{filename}"
