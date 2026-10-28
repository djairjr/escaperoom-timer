#!/usr/bin/env python3
"""
Timer-Nicolau Configurator — Windows App (CustomTkinter)
Gera config.json + sfx + marcador para o Timer-Nicolau
"""
import sys, os, json, platform

# Detecta Windows para mensagens mais úteis
IS_WINDOWS = platform.system() == "Windows"

# Verifica customtkinter
try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:
    print("ERRO: customtkinter não está instalado.")
    print("Instale com: pip install customtkinter")
    print("Recomendado: criar um ambiente virtual primeiro.")
    sys.exit(1)

# Adiciona o diretório do app ao path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config_schema import FIELDS, WIFI_FIELDS, SOUND_KEYS, SOUND_DEFAULTS, validate_config
from export_generator import generate_config, export_to_folder


ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class TimerConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Timer-Nicolau Configurator")
        self.geometry("920x700")
        self.minsize(800, 600)

        # Estado da UI
        self.ui_state = {}        # valores dos campos
        self.sound_paths = {}     # paths windows dos arquivos de som
        self._init_ui_state()

        # ============================================================
        # Layout principal
        # ============================================================
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Timer-Nicolau Configurator",
                     font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Gera config.json + sons + marcador para SD card",
                     font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="w")

        # TabView
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Criar abas
        self.tab_names = ["Geral", "Display", "Áudio", "Wi-Fi", "MQTT", "GPIO", "Avançado"]
        self.tabs = {}
        for name in self.tab_names:
            self.tabs[name] = self.tabview.add(name)

        # Preencher cada aba
        self._build_tab_geral()
        self._build_tab_display()
        self._build_tab_audio()
        self._build_tab_wifi()
        self._build_tab_mqtt()
        self._build_tab_gpio()
        self._build_tab_advanced()

        # ============================================================
        # Footer com botão de export
        # ============================================================
        footer = ctk.CTkFrame(self, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(footer, text="Pronto", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=0, column=0, sticky="w", padx=10)

        self.export_btn = ctk.CTkButton(footer, text="Generate & Export",
                                        command=self._on_export,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        height=36, width=180)
        self.export_btn.grid(row=0, column=1, padx=10, pady=8)

    # ================================================================
    # Estado inicial
    # ================================================================
    def _init_ui_state(self):
        for f in FIELDS:
            self.ui_state[f["key"]] = f["default"]
            if f["type"] == bool:
                self.ui_state[f["key"]] = bool(f["default"])
        for sk in SOUND_KEYS:
            self.sound_paths[sk] = ""
        for f in WIFI_FIELDS:
            self.ui_state[f["key"]] = f["default"]

    # ================================================================
    # Helpers de widgets
    # ================================================================
    def _make_slider_row(self, parent, row, field_key, label_text,
                         from_, to, resolution=1):
        """Cria uma linha com label + slider + label valor"""
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text=label_text, width=180, anchor="w").grid(row=0, column=0, padx=(5, 10))

        initial = self.ui_state.get(field_key, int((from_ + to) / 2))
        var = ctk.IntVar(value=initial)
        val_label = ctk.CTkLabel(f, text=str(initial), width=50)

        def make_callback(key, lbl):
            def cb(v):
                val = int(float(v))
                lbl.configure(text=str(val))
                self.ui_state[key] = val
            return cb

        slider = ctk.CTkSlider(f, from_=from_, to=to, number_of_steps=int((to - from_) / resolution),
                               variable=var, command=make_callback(field_key, val_label))
        slider.grid(row=0, column=1, sticky="ew", padx=5)

        val_label.grid(row=0, column=2, padx=5)

        return var, slider, val_label

    def _make_text_row(self, parent, row, field_key, label_text, is_password=False, height=28):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text=label_text, width=180, anchor="w").grid(row=0, column=0, padx=(5, 10))

        entry = ctk.CTkEntry(f, height=height, show="*" if is_password else "")
        entry.insert(0, str(self.ui_state.get(field_key, "")))
        entry.grid(row=0, column=1, sticky="ew", padx=5)
        entry.bind("<KeyRelease>", lambda e, k=field_key: self._on_text(k, e.widget.get()))

        return entry

    def _on_text(self, key, value):
        self.ui_state[key] = value

    def _make_checkbox_row(self, parent, row, field_key, label_text):
        var = ctk.BooleanVar(value=self.ui_state.get(field_key, False))
        cb = ctk.CTkCheckBox(parent, text=label_text, variable=var,
                              command=lambda: self._on_check(field_key, var.get()))
        cb.grid(row=row, column=0, sticky="w", pady=3, padx=5)
        return var, cb

    def _on_check(self, key, value):
        self.ui_state[key] = value

    def _make_spin_row(self, parent, row, field_key, label_text, from_, to):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", pady=3, padx=5)
        f.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(f, text=label_text, width=180, anchor="w").grid(row=0, column=0, padx=(5, 10))

        var = ctk.IntVar(value=self.ui_state.get(field_key, from_))
        spin = ctk.CTkEntry(f, width=80)
        spin.insert(0, str(var.get()))
        spin.grid(row=0, column=1, padx=5)
        spin.bind("<KeyRelease>", lambda e, k=field_key: self._on_spin(k, e.widget.get()))

        # Mini botões +/-
        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.grid(row=0, column=2)
        ctk.CTkButton(btn_frame, text="▲", width=30, height=22,
                       command=lambda: self._spin_up(spin, var, field_key, to)).grid(row=0, column=0)
        ctk.CTkButton(btn_frame, text="▼", width=30, height=22,
                       command=lambda: self._spin_down(spin, var, field_key, from_)).grid(row=0, column=1)

        return var, spin

    def _on_spin(self, key, text):
        try:
            self.ui_state[key] = int(text)
        except ValueError:
            pass

    def _spin_up(self, entry, var, key, max_):
        val = min(var.get() + 1, max_)
        var.set(val)
        entry.delete(0, "end")
        entry.insert(0, str(val))
        self.ui_state[key] = val

    def _spin_down(self, entry, var, key, min_):
        val = max(var.get() - 1, min_)
        var.set(val)
        entry.delete(0, "end")
        entry.insert(0, str(val))
        self.ui_state[key] = val

    def _make_sound_row(self, parent, row, sound_key, label_text):
        """Linha com label + path label + botão '...' para selecionar arquivo"""
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text=label_text, width=180, anchor="w").grid(row=0, column=0, padx=(5, 10))

        path_label = ctk.CTkLabel(f, text="(não selecionado)", fg_color=("gray85", "gray20"),
                                   corner_radius=4, anchor="w", height=28)
        path_label.grid(row=0, column=1, sticky="ew", padx=5)

        def _pick():
            path = filedialog.askopenfilename(
                title=f"Selecionar: {label_text}",
                filetypes=[("Arquivos MP3", "*.mp3"), ("Todos", "*.*")]
            )
            if path:
                path_label.configure(text=os.path.basename(path))
                self.sound_paths[sound_key] = path
            else:
                path_label.configure(text="(não selecionado)")
                self.sound_paths[sound_key] = ""

        ctk.CTkButton(f, text="...", width=32, command=_pick).grid(row=0, column=2, padx=3)

    # ================================================================
    # Construção das Tabs
    # ================================================================

    def _build_tab_geral(self):
        t = self.tabs["Geral"]
        t.grid_columnconfigure(0, weight=1)

        row = 0
        # room_name
        f = ctk.CTkFrame(t)
        f.grid(row=row, column=0, sticky="ew", pady=5, padx=5)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text="Nome da Sala", width=180, anchor="w").grid(row=0, column=0, padx=(5, 10))
        entry = ctk.CTkEntry(f)
        entry.insert(0, self.ui_state.get("room_name", "SALA A"))
        entry.grid(row=0, column=1, sticky="ew", padx=5)
        entry.bind("<KeyRelease>", lambda e: self._on_text("room_name", e.widget.get()))
        ctk.CTkLabel(f, text="Espaços viram _ no HA", font=ctk.CTkFont(size=10),
                     text_color="gray").grid(row=0, column=2, padx=5)

        row += 1
        # timer_duration_sec
        self._make_slider_row(t, row, "timer_duration_sec",
                                            "Duração (s)", 60, 7200, 60)

        row += 1
        self._make_slider_row(t, row, "trap_pause_seconds",
                                               "Pausa do 1º botão (s)", 0, 10, 1)


        row += 1
        self._make_slider_row(t, row, "accel_multiplier",
                                               "Multiplicador Acel.", 1, 5, 1)

        row += 1
        self._make_slider_row(t, row, "victory_timeout_sec",
                                               "Timeout Vitória (s)", 5, 3600, 5)

    def _build_tab_display(self):
        t = self.tabs["Display"]
        t.grid_columnconfigure(0, weight=1)

        row = 0
        # Mensagens multi-linha com \n
        for key, label, h in [
            ("idle_message", "Mensagem IDLE", 3),
            ("victory_message", "Mensagem Vitória", 3),
            ("game_over_message", "Mensagem Game Over", 3),
        ]:
            f = ctk.CTkFrame(t)
            f.grid(row=row, column=0, sticky="ew", pady=5, padx=5)
            f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(f, text=label, width=180, anchor="w").grid(row=0, column=0, padx=(5, 10), sticky="n")
            textbox = ctk.CTkTextbox(f, height=60)
            textbox.grid(row=0, column=1, sticky="ew", padx=5)
            textbox.insert("1.0", self.ui_state.get(key, ""))
            textbox.bind("<KeyRelease>", lambda e, k=key:
                         self._on_text(k, e.widget.get("1.0", "end-1c")))
            ctk.CTkLabel(f, text="Use \\n para\nquebrar linha",
                         font=ctk.CTkFont(size=10), text_color="gray",
                         justify="left").grid(row=0, column=2, padx=5, sticky="n")
            row += 1

        row += 1
        # brightness
        self._make_slider_row(t, row, "brightness_pct",
                                            "Brilho (%)", 0, 100, 5)

    def _build_tab_audio(self):
        t = self.tabs["Áudio"]
        t.grid_columnconfigure(0, weight=1)

        # Scrollable dentro da aba de audio
        scroll = ctk.CTkScrollableFrame(t)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        t.grid_rowconfigure(0, weight=1)

        row = 0
        # Toggles
        for key, label in [
            ("sounds_enabled", "Sons Ativados"),
            ("custom_sounds_enabled", "Sons Customizados"),
            ("background_music_enabled", "Música de Fundo"),
        ]:
            self._make_checkbox_row(scroll, row, key, label)
            row += 1

        row += 1
        # Volume slider
        self._make_slider_row(scroll, row, "sound_volume",
                                            "Volume", 0, 128, 1)

        row += 1
        # Separador
        ctk.CTkLabel(scroll, text="── Arquivos de Som ──",
                     font=ctk.CTkFont(size=12)).grid(row=row, column=0, pady=10)
        row += 1

        # File pickers para cada som
        sound_labels = {
            "tick": "Tick", "alarm": "Alarme", "victory": "Vitória",
            "button_press": "Pressão Botão", "button_release": "Soltar Botão",
            "penalty_alarm": "Alarme Penalidade", "background_music": "Música Fundo",
        }
        for sk in SOUND_KEYS:
            self._make_sound_row(scroll, row, sk, sound_labels.get(sk, sk))
            row += 1

    def _build_tab_wifi(self):
        t = self.tabs["Wi-Fi"]
        t.grid_columnconfigure(0, weight=1)

        self._make_text_row(t, 0, "wifi_ssid", "Rede Wi-Fi (SSID)")
        self._make_text_row(t, 1, "wifi_password", "Senha do Wi-Fi", is_password=True)
        ctk.CTkLabel(t, justify="left", anchor="w", text_color="gray",
                     text="Opcional. Deixe em branco para não mudar o Wi-Fi da placa.\n"
                          "Com o cabo de rede ligado, a placa usa o cabo; o Wi-Fi\n"
                          "fica salvo e entra quando o cabo for desconectado.").grid(
            row=2, column=0, sticky="w", padx=10, pady=10)

    def _build_tab_mqtt(self):
        t = self.tabs["MQTT"]
        t.grid_columnconfigure(0, weight=1)

        row = 0
        self._make_text_row(t, row, "mqtt_broker", "Broker")
        row += 1
        self._make_text_row(t, row, "mqtt_port", "Porta")
        row += 1
        self._make_text_row(t, row, "mqtt_username", "Usuário")
        row += 1
        self._make_text_row(t, row, "mqtt_password", "Senha", is_password=True)
        row += 1
        self._make_text_row(t, row, "mqtt_topic_prefix", "Prefixo Tópico")
        row += 1
        self._make_text_row(t, row, "ha_discovery_prefix", "HA Discovery Prefix")

    def _build_tab_gpio(self):
        t = self.tabs["GPIO"]
        t.grid_columnconfigure(0, weight=1)

        row = 0
        self._make_spin_row(t, row, "gpio_out_line", "Pino Desarme (line)", 0, 27)
        row += 1
        self._make_checkbox_row(t, row, "gpio_out_active_high", "Active High")

    def _build_tab_advanced(self):
        t = self.tabs["Avançado"]
        t.grid_columnconfigure(0, weight=1)

        row = 0
        self._make_slider_row(t, row, "log_verbosity",
                                            "Log Verbosity", 0, 3, 1)

    # ================================================================
    # Export
    # ================================================================
    def _on_export(self):
        """Gera o pacote no diretório escolhido pelo usuário"""
        dest = filedialog.askdirectory(title="Selecionar pasta de destino (SD card)")
        if not dest:
            return

        self.status_label.configure(text="Gerando configuração...")
        self.export_btn.configure(state="disabled")
        self.update()

        try:
            # Montar config completa
            cfg = generate_config(self.ui_state)

            # Verificar warnings antes de exportar
            from config_schema import validate_config
            _errs, warns = validate_config(cfg)

            # Salvar
            wifi = {"ssid": self.ui_state.get("wifi_ssid", "").strip(),
                    "password": self.ui_state.get("wifi_password", "")}
            export_to_folder(dest, cfg, self.sound_paths, wifi)

            msg = (f"Configuração exportada!\n\n{dest}\n\n"
                   "Copie para o cartão SD, insira o cartão com a placa DESLIGADA e ligue a placa.\n"
                   "O resultado fica em TIMER-NICOLAU-RESULTADO.txt no cartão.")
            if warns:
                msg += "\n\nAvisos:\n" + "\n".join(warns)

            self.status_label.configure(
                text=f"✓ Configuração exportada para: {dest}")
            messagebox.showinfo("Sucesso", msg)

        except ValueError as e:
            self.status_label.configure(text="✗ Erro de validação")
            messagebox.showerror("Erro de Validação", str(e))
        except Exception as e:
            self.status_label.configure(text=f"✗ Erro: {e}")
            messagebox.showerror("Erro", f"Falha ao exportar:\n{e}")
        finally:
            self.export_btn.configure(state="normal")


if __name__ == "__main__":
    app = TimerConfigApp()
    app.mainloop()
