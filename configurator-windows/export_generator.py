"""
export_generator.py — Gera o pacote de configuração para o Timer-Nicolau
Use: export_to_folder(destino, ui_state, sound_paths)
"""

import os, json, shutil
from datetime import datetime

from config_schema import (
    FIELDS, SOUND_KEYS, SOUND_DEFAULTS,
    sound_path_to_linux, validate_config, get_default_config
)


def generate_config(ui_state: dict) -> dict:
    """
    Monta o dict completo do config.json a partir do estado da UI.
    ui_state: dict com as chaves dos campos + 'sound_paths' para os sons
    """
    cfg = {}

    # Campos simples
    for f in FIELDS:
        key = f["key"]
        val = ui_state.get(key, f["default"])
        expected = f["type"]
        # Converte string → tipo esperado
        if expected == int:
            try:
                val = int(val)
            except (ValueError, TypeError):
                val = f["default"]
        elif expected == bool:
            if isinstance(val, str):
                val = val.lower() in ("true", "1", "on")
            val = bool(val)
        cfg[key] = val

    # Sound files
    sound_paths = ui_state.get("sound_paths", {})
    sf = {}
    for sk in SOUND_KEYS:
        win_path = sound_paths.get(sk, "")
        if win_path and win_path.strip():
            sf[sk] = sound_path_to_linux(win_path)
        else:
            sf[sk] = SOUND_DEFAULTS.get(sk, "")
    cfg["sound_files"] = sf

    # GPIO aninhado
    cfg["gpio_out_desarmado"] = {
        "line": int(cfg.pop("gpio_out_line", 21)),
        "active_high": bool(cfg.pop("gpio_out_active_high", True)),
    }

    return cfg


def export_to_folder(dest: str, config: dict, sound_windows_paths: dict, wifi: dict = None) -> str:
    """
    Gera o pacote no diretório 'dest':
      - config.json
      - sfx/*.mp3 (cópias)
      - wifi.json (só se houver SSID)
      - .timer-nicolau-config (vazio)
      - README.txt
    Retorna caminho da pasta criada ou lança exceção.
    """
    wifi = wifi or {}
    ssid = (wifi.get("ssid") or "").strip()
    wifi_pass = wifi.get("password") or ""
    if ssid and wifi_pass and not 8 <= len(wifi_pass) <= 63:
        raise ValueError("A senha do Wi-Fi deve ter de 8 a 63 caracteres (ou ficar vazia para rede aberta).")
    os.makedirs(dest, exist_ok=True)

    # Validar primeiro
    errors, warnings = validate_config(config)
    if errors:
        msg = "Erros de validação:\n" + "\n".join(errors)
        if warnings:
            msg += "\n\nAvisos:\n" + "\n".join(warnings)
        raise ValueError(msg)

    # 1. Escrever config.json
    json_path = os.path.join(dest, "config.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"config.json → {json_path}")

    # 2. Criar sfx/ e copiar .mp3
    sfx_dir = os.path.join(dest, "sfx")
    os.makedirs(sfx_dir, exist_ok=True)

    copied = 0
    for sk, win_path in sound_windows_paths.items():
        if not win_path or not win_path.strip():
            continue
        src = win_path.strip()
        if not os.path.isfile(src):
            print(f"  AVISO: Arquivo não encontrado: {src}")
            continue
        fname = os.path.basename(src)
        dst = os.path.join(sfx_dir, fname)
        shutil.copy2(src, dst)
        copied += 1
        print(f"  Som: {fname}")

    if copied == 0:
        print("  AVISO: Nenhum arquivo de som copiado")

    # 2b. wifi.json: the board joins this network (timer-sd-import on the board reads it)
    wifi_path = os.path.join(dest, "wifi.json")
    if ssid:
        with open(wifi_path, "w", encoding="utf-8") as f:
            json.dump({"ssid": ssid, "password": wifi_pass}, f, indent=2, ensure_ascii=False)
        print(f"wifi.json → {wifi_path}")
    elif os.path.exists(wifi_path):
        os.remove(wifi_path)  # do not leave an older network behind in a reused folder

    # 3. Criar marcador
    marker = os.path.join(dest, ".timer-nicolau-config")
    with open(marker, "w") as f:
        pass  # vazio
    print(f"Marcador: .timer-nicolau-config")

    # 4. README.txt
    room = config.get("room_name", "SALA A")
    readme_path = os.path.join(dest, "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"""Configuração Timer-Nicolau — Sala: {room}
Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Este pacote contém:
  - config.json    → configuração do dispositivo (substitui a configuração inteira)
  - sfx/           → arquivos de som
  - wifi.json      → rede Wi-Fi: {'incluída: ' + ssid if ssid else 'não incluída'}
  - .timer-nicolau-config  → marcador de identificação

COMO USAR:
1. Copie os arquivos (ou esta pasta inteira) para um cartão SD (FAT32 ou exFAT).
   Os arquivos podem ficar na raiz do cartão ou dentro de uma pasta.
2. Com a placa DESLIGADA, insira o cartão. Inserir com a placa ligada pode reiniciá-la.
3. Ligue a placa. Em cerca de 15 segundos a configuração é aplicada e o timer reinicia.
4. O resultado fica no cartão, em TIMER-NICOLAU-RESULTADO.txt (abra no computador).
   O cartão pode ficar na placa: o mesmo conteúdo não é aplicado duas vezes.

Wi-Fi: com o cabo de rede ligado, a placa usa o cabo; o Wi-Fi fica salvo e entra
quando o cabo for desconectado. Sem cabo e sem Wi-Fi conhecido, a placa abre a rede
"Nicolau-XXXX" (senha: a do configurador web); conecte e abra http://192.168.4.1
""")
    print(f"README.txt → {readme_path}")

    return dest
