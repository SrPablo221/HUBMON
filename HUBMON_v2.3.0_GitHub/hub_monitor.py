"""HUBMON 2.3.0 — central de controle de monitor via DDC/CI.

Preserva os códigos de entrada confirmados no HUBMON original:
  HDMI / PS5       = 0x01
  DisplayPort / PC = 0x03

Volume físico do monitor: VCP 0x62 (depende do suporte do firmware).
Silenciamento: VCP de áudio via monitorcontrol, também opcional por modelo.

Requer Python 3.10+ e monitorcontrol 4.2.0+.
"""
from __future__ import annotations

import queue
import sys
import json
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from datetime import datetime
from typing import Any

try:
    from monitorcontrol import get_monitors
except ImportError:  # Permite que a interface mostre instruções em vez de fechar.
    get_monitors = None

APP_VERSION = "2.3.0"

# Mantidos exatamente como no HUBMON que já funcionou no PC do usuário.
INPUTS = {
    "HDMI — PS5": 0x01,
    "DisplayPort — PC": 0x03,
    "DisplayPort 1": 0x0F,
    "DisplayPort 2": 0x10,
    "HDMI 1": 0x11,
    "HDMI 2": 0x12,
}
INPUT_NAMES = {value: name for name, value in INPUTS.items()}

# Paleta neutra: grafite, cinza e azul discreto.
BG = "#0A0F18"
PANEL = "#111927"
PANEL_ALT = "#172235"
PANEL_HOVER = "#202F45"
BORDER = "#26364D"
FG = "#E8EEF8"
MUTED = "#94A6BD"
BLUE = "#2F80ED"
BLUE_HOVER = "#3C91FF"
GREEN = "#36C995"
RED = "#EE7181"
TRACK = "#29384E"


def _as_int(value: Any) -> int:
    """Converte valores e enums da biblioteca para int."""
    if hasattr(value, "value"):
        value = value.value
    return int(value)


def _safe_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    try:
        return str(value)
    except Exception:
        return fallback


class Hub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"HUBMON · Central de Monitor · v{APP_VERSION}")
        self.configure(bg=BG)
        self.geometry("980x770")
        self.minsize(820, 680)
        self.option_add("*Font", ("Segoe UI", 10))

        self.monitor_infos: list[dict[str, Any]] = []
        self.task_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self.task_number = 0
        self.pending_volume_after: str | None = None
        self.updating_volume = False
        self.volume_dragging = False
        self.last_read_volume: int | None = None
        self.advanced_open = False
        self.current_input_code: int | None = None
        self.current_mute_state: bool | None = None
        self.last_read_brightness: int | None = None
        self.updating_brightness = False
        self.brightness_dragging = False
        self.pending_brightness_after: str | None = None
        self.config_path = Path(os.environ.get("APPDATA", str(Path.home()))) / "HUBMON" / "settings.json"
        self.settings = self._load_settings()
        self.library_path = self.config_path.parent / "ps5_library.json"
        self.ps5_library = self._load_game_library()
        self.library_window = None

        self._configure_styles()
        self._build_ui()

        self.worker = threading.Thread(target=self._worker_loop, name="HUBMON-DDC", daemon=True)
        self.worker.start()
        self.after(100, self._poll_results)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(180, self.detectar)
        self._enable_dark_title_bar()

    # -------------------------- UI --------------------------
    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Hub.TCombobox",
            fieldbackground=PANEL_ALT,
            background=PANEL_ALT,
            foreground=FG,
            arrowcolor=FG,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
        )
        style.map(
            "Hub.TCombobox",
            fieldbackground=[("readonly", PANEL_ALT), ("disabled", PANEL)],
            foreground=[("readonly", FG), ("disabled", MUTED)],
            selectbackground=[("readonly", PANEL_ALT)],
            selectforeground=[("readonly", FG)],
        )

    def _build_ui(self):
        page = tk.Frame(self, bg=BG)
        page.pack(fill="both", expand=True, padx=20, pady=(14, 12))
        page.grid_columnconfigure(0, weight=1)

        # Topo / marca
        header = tk.Frame(page, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(1, weight=1)
        logo = tk.Frame(header, bg=BLUE, width=46, height=46)
        logo.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        logo.grid_propagate(False)
        tk.Label(logo, text="H", bg=BLUE, fg="white", font=("Segoe UI", 23, "bold")).place(relx=.5, rely=.45, anchor="center")
        tk.Label(header, text="HUBMON", bg=BG, fg=FG, font=("Segoe UI", 19, "bold")).grid(row=0, column=1, sticky="sw")
        tk.Label(header, text="Central de controle do monitor  ·  DDC/CI", bg=BG, fg=MUTED, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="nw")
        self.status_dot = tk.Label(header, text="●", bg=BG, fg=MUTED, font=("Segoe UI", 12))
        self.status_dot.grid(row=0, column=2, sticky="e", padx=(10, 5))
        self.status_var = tk.StringVar(value="Inicializando…")
        tk.Label(header, textvariable=self.status_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).grid(row=0, column=3, sticky="e")

        # Seletor de monitor
        device = self._card(page, padding=12)
        device.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        device.grid_columnconfigure(1, weight=1)
        tk.Label(device, text="MONITOR DDC/CI", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.combo = ttk.Combobox(device, state="readonly", style="Hub.TCombobox", width=45)
        self.combo.grid(row=0, column=1, sticky="ew")
        self.combo.bind("<<ComboboxSelected>>", self._on_monitor_selected)
        self._button(device, "⟳  Detectar novamente", self.detectar, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=13).grid(row=0, column=2, padx=(10, 0))

        # Área principal em duas colunas
        main = tk.Frame(page, bg=BG)
        main.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        main.grid_columnconfigure(0, weight=11, uniform="main")
        main.grid_columnconfigure(1, weight=10, uniform="main")
        main.grid_rowconfigure(0, weight=1)

        # Card de entrada de vídeo
        inputs = self._card(main, padding=16)
        inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._eyebrow(inputs, "01  /  VÍDEO")
        tk.Label(inputs, text="Trocar entrada", bg=PANEL, fg=FG, font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(5, 2))
        tk.Label(inputs, text="Escolha qual aparelho aparece no Valak.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 14))

        self.ps5_btn = self._button(inputs, "🎮   MODO PS5   ·   HDMI", lambda: self.trocar(0x01), bg="#29333F", fg=FG, hover="#354250", padx=12, pady=13, font=("Segoe UI", 11, "bold"))
        self.ps5_btn.pack(fill="x", pady=(0, 8))
        self.pc_btn = self._button(inputs, "▣   MODO PC   ·   DISPLAYPORT", lambda: self.trocar(0x03), bg="#263A4D", fg=FG, hover="#314A61", padx=12, pady=13, font=("Segoe UI", 11, "bold"))
        self.pc_btn.pack(fill="x", pady=(0, 12))

        current = tk.Frame(inputs, bg=PANEL_ALT, padx=10, pady=8)
        current.pack(fill="x", side="bottom")
        tk.Label(current, text="ENTRADA ATUAL", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.input_status_var = tk.StringVar(value="Não verificada")
        tk.Label(current, textvariable=self.input_status_var, bg=PANEL_ALT, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="right")
        profiles = tk.Frame(inputs, bg=PANEL)
        profiles.pack(fill="x", pady=(10, 0))
        tk.Label(profiles, text="PERFIS", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))
        profile_buttons = tk.Frame(profiles, bg=PANEL)
        profile_buttons.pack(fill="x")
        self._button(profile_buttons, "Salvar perfil PS5", lambda: self.save_profile("ps5"), bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=8, pady=6).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._button(profile_buttons, "Salvar perfil PC", lambda: self.save_profile("pc"), bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=8, pady=6).pack(side="left", fill="x", expand=True, padx=(4, 0))
        self._button(inputs, "▦  Biblioteca de jogos PS5", self.open_game_library, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=8).pack(fill="x", pady=(9, 0))

        # Card de volume
        audio = self._card(main, padding=16)
        audio.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._eyebrow(audio, "02  /  ÁUDIO")
        audio_title = tk.Frame(audio, bg=PANEL)
        audio_title.pack(fill="x", pady=(5, 2))
        tk.Label(audio_title, text="Volume do monitor", bg=PANEL, fg=FG, font=("Segoe UI", 16, "bold")).pack(side="left")
        self.volume_value_var = tk.StringVar(value="— %")
        tk.Label(audio_title, textvariable=self.volume_value_var, bg=PANEL, fg=GREEN, font=("Segoe UI", 17, "bold")).pack(side="right")
        tk.Label(audio, text="Envia comandos DDC/CI ao monitor; a resposta do registro não garante mudança audível.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=350, justify="left").pack(anchor="w", pady=(0, 10))

        scale_wrap = tk.Frame(audio, bg=PANEL, pady=4)
        scale_wrap.pack(fill="x")
        tk.Label(scale_wrap, text="🔉", bg=PANEL, fg=MUTED, font=("Segoe UI", 12)).pack(side="left", padx=(0, 8))
        self.volume_scale = tk.Scale(
            scale_wrap, from_=0, to=100, orient="horizontal", resolution=1,
            showvalue=False, bd=0, highlightthickness=0, relief="flat",
            bg=PANEL, fg=FG, troughcolor=TRACK, activebackground=BLUE_HOVER,
            sliderrelief="flat", sliderlength=20, width=12,
            command=self._on_volume_change,
        )
        self.volume_scale.set(35)
        self.volume_scale.pack(side="left", fill="x", expand=True)
        # During a mouse drag, do not send dozens of slow I²C writes. Send only
        # once on release; keyboard changes use a debounce in _on_volume_change.
        self.volume_scale.bind("<ButtonPress-1>", self._volume_drag_start, add="+")
        self.volume_scale.bind("<ButtonRelease-1>", self._volume_drag_end, add="+")
        self.volume_scale.bind("<KeyRelease>", self._volume_key_release, add="+")
        tk.Label(scale_wrap, text="🔊", bg=PANEL, fg=MUTED, font=("Segoe UI", 12)).pack(side="left", padx=(8, 0))

        self.volume_hint_var = tk.StringVar(value="Verificando suporte a volume DDC/CI…")
        tk.Label(audio, textvariable=self.volume_hint_var, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", pady=(2, 8))

        bright_header = tk.Frame(audio, bg=PANEL)
        bright_header.pack(fill="x", pady=(2, 0))
        tk.Label(bright_header, text="Brilho do monitor", bg=PANEL, fg=FG, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.brightness_value_var = tk.StringVar(value="— %")
        tk.Label(bright_header, textvariable=self.brightness_value_var, bg=PANEL, fg=FG, font=("Segoe UI", 13, "bold")).pack(side="right")
        self.brightness_scale = tk.Scale(audio, from_=0, to=100, orient="horizontal", resolution=1, showvalue=False, bd=0, highlightthickness=0, relief="flat", bg=PANEL, fg=FG, troughcolor=TRACK, activebackground=BLUE_HOVER, sliderrelief="flat", sliderlength=20, width=12, command=self._on_brightness_change)
        self.brightness_scale.set(50)
        self.brightness_scale.pack(fill="x", pady=(0, 2))
        self.brightness_scale.bind("<ButtonPress-1>", self._brightness_drag_start, add="+")
        self.brightness_scale.bind("<ButtonRelease-1>", self._brightness_drag_end, add="+")
        self.brightness_scale.bind("<KeyRelease>", self._brightness_key_release, add="+")
        self.brightness_hint_var = tk.StringVar(value="Verificando suporte a brilho DDC/CI…")
        tk.Label(audio, textvariable=self.brightness_hint_var, bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", pady=(0, 8))

        audio_actions = tk.Frame(audio, bg=PANEL)
        audio_actions.pack(fill="x", side="bottom")
        self.mute_btn = self._button(audio_actions, "◖  Silenciar", self.alternar_mudo, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=12, pady=9)
        self.mute_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self._button(audio_actions, "↻  Ler volume", self.ler_volume, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=12, pady=9).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Diagnóstico recolhível (mantém os recursos antigos, sem poluir a tela principal)
        self.advanced_toggle = self._button(page, "＋  Ferramentas avançadas e diagnóstico", self.toggle_advanced, bg=BG, fg=MUTED, hover=PANEL_HOVER, padx=10, pady=7, anchor="w")
        self.advanced_toggle.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.advanced_frame = self._card(page, padding=12)
        self._build_advanced(self.advanced_frame)
        # Recolhido por padrão. A área não ocupa espaço até o usuário pedir.

        # Log compacto sempre acessível
        self.log_card = self._card(page, padding=9)
        self.log_card.grid(row=4, column=0, sticky="nsew", pady=(0, 5))
        log_header = tk.Frame(self.log_card, bg=PANEL)
        log_header.pack(fill="x", pady=(0, 5))
        tk.Label(log_header, text="LOG DE ATIVIDADE", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        self._button(log_header, "Limpar", self.limpar_log, bg=PANEL_ALT, fg=MUTED, hover=PANEL_HOVER, padx=7, pady=2, font=("Segoe UI", 8)).pack(side="right")
        self.log = scrolledtext.ScrolledText(
            self.log_card, height=4, wrap="word", bg="#0B111B", fg="#B8C8DD",
            insertbackground=FG, selectbackground="#264B79", relief="flat",
            bd=0, font=("Consolas", 8), padx=8, pady=6,
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self.footer_label = tk.Label(page, text=f"HUBMON {APP_VERSION}  ·  Controle local do monitor via DDC/CI.", bg=BG, fg="#60718A", font=("Segoe UI", 8))
        self.footer_label.grid(row=5, column=0, sticky="e", pady=(3, 0))

    def _build_advanced(self, parent):
        self._eyebrow(parent, "FERRAMENTAS AVANÇADAS")
        tk.Label(parent, text="Entradas alternativas", bg=PANEL, fg=FG, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(4, 7))
        alt = tk.Frame(parent, bg=PANEL)
        alt.pack(fill="x")
        names = list(INPUTS.items())
        for i, (name, code) in enumerate(names):
            r, c = divmod(i, 3)
            self._button(alt, name, lambda v=code: self.trocar(v), bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=8, pady=6, font=("Segoe UI", 9)).grid(row=r, column=c, sticky="ew", padx=3, pady=3)
        for c in range(3):
            alt.grid_columnconfigure(c, weight=1)

        tools = tk.Frame(parent, bg=PANEL)
        tools.pack(fill="x", pady=(8, 0))
        self._button(tools, "Ler entrada atual", self.ler_entrada, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=9, pady=6).pack(side="left", padx=(0, 6))
        self._button(tools, "Ler capabilities", self.ler_caps, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=9, pady=6).pack(side="left", padx=(0, 12))
        tk.Label(tools, text="Código de entrada:", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.raw_entry = tk.Entry(tools, width=9, bg=PANEL_ALT, fg=FG, insertbackground=FG, relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE)
        self.raw_entry.pack(side="left", padx=6, ipady=5)
        self.raw_entry.insert(0, "0x01")
        self._button(tools, "Enviar", self.enviar_raw, bg="#34485D", fg="white", hover="#40566D", padx=10, pady=5).pack(side="left")
        tk.Label(parent, text="Os códigos alternativos são específicos de cada monitor. Use-os apenas se souber qual entrada deseja selecionar.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=820, justify="left").pack(anchor="w", pady=(9, 0))

    def _card(self, parent, padding=12):
        return tk.Frame(parent, bg=PANEL, padx=padding, pady=padding, highlightbackground=BORDER, highlightthickness=1, bd=0)

    @staticmethod
    def _eyebrow(parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")

    @staticmethod
    def _button(parent, text, command, *, bg, fg, hover, padx=10, pady=7, font=("Segoe UI", 9, "bold"), anchor="center"):
        button = tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg,
            activebackground=hover, activeforeground=fg,
            disabledforeground="#65758B", relief="flat", bd=0,
            padx=padx, pady=pady, font=font, cursor="hand2",
            highlightthickness=0, anchor=anchor,
        )
        # Keep hover styling local to the button.
        button.bind("<Enter>", lambda _e, b=button, color=hover: b.configure(bg=color) if str(b["state"]) != "disabled" else None)
        button.bind("<Leave>", lambda _e, b=button, color=bg: b.configure(bg=color) if str(b["state"]) != "disabled" else None)
        return button

    def _enable_dark_title_bar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = self.winfo_id()
            value = ctypes.c_int(1)
            # Attribute 20 (Windows 11/modern Windows 10); fallback 19 on older builds.
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            if result != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    # --------------------- Monitor worker --------------------
    def _submit(self, action: str, **args):
        self.task_number += 1
        token = self.task_number
        self.task_queue.put((token, action, args))
        return token

    def _worker_loop(self):
        while True:
            task = self.task_queue.get()
            if task is None:
                break
            token, action, args = task
            try:
                result = self._execute_action(action, args)
                self.result_queue.put((token, action, True, result))
            except Exception as exc:
                self.result_queue.put((token, action, False, f"{type(exc).__name__}: {exc}"))

    @staticmethod
    def _read_monitor_info(index, monitor):
        info: dict[str, Any] = {
            "index": index,
            "name": f"Monitor {index + 1}",
            "model": "",
            "input": None,
            "volume": None,
            "volume_error": None,
            "brightness": None,
            "brightness_error": None,
            "mute": None,
            "mute_error": None,
            "caps": None,
        }
        with monitor:
            try:
                caps = monitor.get_vcp_capabilities()
                info["caps"] = caps
                model = caps.get("model") or caps.get("name")
                if model and str(model).strip() not in ("?", "Unknown", "None"):
                    info["model"] = str(model).strip()
                    info["name"] = f"Monitor {index} — {info['model']}"
            except Exception:
                caps = {}
            try:
                info["input"] = _as_int(monitor.get_input_source())
            except Exception:
                pass
            try:
                info["volume"] = max(0, min(100, _as_int(monitor.get_volume())))
            except Exception as exc:
                info["volume_error"] = str(exc)
            try:
                info["brightness"] = max(0, min(100, _as_int(monitor.get_luminance())))
            except Exception as exc:
                info["brightness_error"] = str(exc)
            try:
                # No monitorcontrol 4.2+, mode 1 = mute on; 2 = mute off.
                info["mute"] = (_as_int(monitor.get_audio_mute_mode()) == 1)
            except Exception as exc:
                info["mute_error"] = str(exc)
        return info

    def _execute_action(self, action: str, args: dict[str, Any]):
        if get_monitors is None:
            raise RuntimeError("A dependência monitorcontrol não está instalada. Execute INSTALAR.bat.")

        if action == "detect":
            monitors = get_monitors()
            infos = []
            for index, monitor in enumerate(monitors):
                try:
                    infos.append(self._read_monitor_info(index + 1, monitor))
                except Exception as exc:
                    infos.append({"index": index, "name": f"Monitor {index + 1} — leitura parcial", "model": "", "input": None, "volume": None, "volume_error": str(exc), "mute": None, "mute_error": None, "caps": None})
            return infos

        monitors = get_monitors()
        index = int(args.get("monitor_index", 0))
        if index < 0 or index >= len(monitors):
            raise RuntimeError("Monitor selecionado não encontrado. Clique em Detectar novamente.")
        monitor = monitors[index]

        if action == "inspect_monitor":
            return self._read_monitor_info(index + 1, monitor)

        if action == "apply_profile":
            profile = args.get("profile", "pc")
            values = args.get("values", {})
            result = {"profile": profile, "input": None, "brightness": None, "volume": None, "warnings": []}
            with monitor:
                try:
                    monitor.set_input_source(int(values.get("input", 0x01 if profile == "ps5" else 0x03)))
                    result["input"] = _as_int(monitor.get_input_source())
                except Exception as exc:
                    result["warnings"].append(f"entrada: {exc}")
                if "brightness" in values:
                    try:
                        monitor.set_luminance(int(values["brightness"]))
                        result["brightness"] = _as_int(monitor.get_luminance())
                    except Exception as exc:
                        result["warnings"].append(f"brilho: {exc}")
                if "volume" in values:
                    try:
                        monitor.set_volume(int(values["volume"]))
                        result["volume"] = _as_int(monitor.get_volume())
                    except Exception as exc:
                        result["warnings"].append(f"volume: {exc}")
            return result

        with monitor:
            if action == "switch_input":
                value = int(args["value"])
                monitor.set_input_source(value)
                try:
                    actual = _as_int(monitor.get_input_source())
                except Exception:
                    actual = None
                return {"requested": value, "actual": actual}

            if action == "read_input":
                return _as_int(monitor.get_input_source())

            if action == "read_caps":
                return monitor.get_vcp_capabilities()

            if action == "get_volume":
                return max(0, min(100, _as_int(monitor.get_volume())))

            if action == "set_volume":
                value = max(0, min(100, int(args["value"])))
                first_error = None
                retry_error = None
                write_ok = False
                try:
                    monitor.set_volume(value)
                    write_ok = True
                except Exception as exc:
                    first_error = f"{type(exc).__name__}: {exc}"
                    # Some displays intermittently fail a DDC/I²C write. Retry once
                    # after a short pause; avoid aggressive repeated bus traffic.
                    time.sleep(0.18)
                    try:
                        monitor.set_volume(value)
                        write_ok = True
                    except Exception as retry_exc:
                        retry_error = f"{type(retry_exc).__name__}: {retry_exc}"
                try:
                    actual = max(0, min(100, _as_int(monitor.get_volume())))
                except Exception:
                    actual = None
                return {
                    "requested": value,
                    "actual": actual,
                    "write_ok": write_ok,
                    "first_error": first_error,
                    "retry_error": retry_error,
                }

            if action == "get_brightness":
                return max(0, min(100, _as_int(monitor.get_luminance())))

            if action == "set_brightness":
                value = max(0, min(100, int(args["value"])))
                monitor.set_luminance(value)
                try:
                    actual = max(0, min(100, _as_int(monitor.get_luminance())))
                except Exception:
                    actual = None
                return {"requested": value, "actual": actual}

            if action == "toggle_mute":
                current = _as_int(monitor.get_audio_mute_mode())
                new_value = 2 if current == 1 else 1
                monitor.set_audio_mute_mode(new_value)
                try:
                    actual = _as_int(monitor.get_audio_mute_mode()) == 1
                except Exception:
                    actual = new_value == 1
                return {"muted": actual}

            if action == "raw_input":
                value = int(args["value"])
                if not 0 <= value <= 255:
                    raise ValueError("O código VCP deve estar entre 0 e 255.")
                # The original code field sent input-source values, so keep that behavior.
                monitor.set_input_source(value)
                try:
                    actual = _as_int(monitor.get_input_source())
                except Exception:
                    actual = None
                return {"requested": value, "actual": actual}

        raise ValueError(f"Ação desconhecida: {action}")

    def _poll_results(self):
        try:
            while True:
                item = self.result_queue.get_nowait()
                self._handle_result(*item)
        except queue.Empty:
            pass
        try:
            self.after(100, self._poll_results)
        except tk.TclError:
            pass

    # ----------------------- UI actions ----------------------
    def detectar(self):
        self._cancel_pending_volume()
        self._set_status("Detectando monitores…", MUTED)
        self._submit("detect")

    def _on_monitor_selected(self, _event=None):
        self._cancel_pending_volume()
        index = self.combo.current()
        if index < 0 or index >= len(self.monitor_infos):
            return
        self._apply_monitor_info(self.monitor_infos[index])
        self._set_status("Atualizando monitor…", MUTED)
        self._submit("inspect_monitor", monitor_index=index)

    def trocar(self, code):
        index = self.combo.current()
        if index < 0:
            self._set_status("Selecione um monitor primeiro", RED)
            self._log("Nenhum monitor selecionado. Clique em Detectar novamente.")
            return
        name = INPUT_NAMES.get(code, f"Código {code:#04x}")
        self._set_status(f"Enviando comando: {name}…", MUTED)
        self._submit("switch_input", monitor_index=index, value=code)

    def _load_game_library(self):
        """Carrega uma biblioteca local; não consulta servidores da Sony."""
        try:
            if self.library_path.exists():
                data = json.loads(self.library_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("games"), list):
                    games = []
                    for item in data["games"]:
                        if isinstance(item, dict) and str(item.get("title", "")).strip():
                            games.append({
                                "title": str(item.get("title", "")).strip()[:120],
                                "notes": str(item.get("notes", ""))[:500],
                                "favorite": bool(item.get("favorite", False)),
                                "current": bool(item.get("current", False)),
                            })
                    return games
        except Exception:
            pass
        return []

    def _save_game_library(self):
        try:
            self.library_path.parent.mkdir(parents=True, exist_ok=True)
            self.library_path.write_text(json.dumps({"version": 1, "games": self.ps5_library}, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            messagebox.showerror("HUBMON", f"Não foi possível salvar a biblioteca local.\n{exc}", parent=self)
            return False

    def open_game_library(self):
        if self.library_window is not None and self.library_window.winfo_exists():
            self.library_window.deiconify()
            self.library_window.lift()
            self.library_window.focus_force()
            self._refresh_game_library()
            return
        win = tk.Toplevel(self)
        self.library_window = win
        win.title("HUBMON · Biblioteca PS5")
        win.configure(bg=BG)
        win.geometry("700x570")
        win.minsize(600, 480)
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        tk.Label(win, text="Biblioteca local de jogos", bg=BG, fg=FG, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(win, text="Organize sua coleção offline. No PS5 original, a inicialização do jogo ainda é manual.", bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=650, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        search_row = tk.Frame(win, bg=BG)
        search_row.pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(search_row, text="Buscar", bg=BG, fg=MUTED).pack(side="left", padx=(0, 8))
        self.library_search_var = tk.StringVar()
        search = ttk.Entry(search_row, textvariable=self.library_search_var)
        search.pack(side="left", fill="x", expand=True)
        self.library_search_var.trace_add("write", lambda *_: self._refresh_game_library())
        list_frame = tk.Frame(win, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self.library_list = tk.Listbox(list_frame, bg=PANEL, fg=FG, selectbackground="#2A4D73", selectforeground=FG, relief="flat", bd=0, font=("Segoe UI", 10), activestyle="none", exportselection=False)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.library_list.yview)
        self.library_list.configure(yscrollcommand=scrollbar.set)
        self.library_list.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y")
        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 8))
        self._button(actions, "+ Adicionar", self.add_library_game, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=7).pack(side="left", padx=(0, 6))
        self._button(actions, "Editar", self.edit_library_game, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=7).pack(side="left", padx=6)
        self._button(actions, "★ Favorito", self.toggle_library_favorite, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=7).pack(side="left", padx=6)
        self._button(actions, "Remover", self.remove_library_game, bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=7).pack(side="left", padx=6)
        bottom = tk.Frame(win, bg=BG)
        bottom.pack(fill="x", padx=18, pady=(0, 16))
        self._button(bottom, "Marcar como jogo atual", self.set_current_library_game, bg="#263A4D", fg=FG, hover="#314A61", padx=10, pady=8).pack(side="left", fill="x", expand=True, padx=(0, 5))
        self._button(bottom, "Mudar monitor para PS5", lambda: self.trocar(0x01), bg=PANEL_ALT, fg=FG, hover=PANEL_HOVER, padx=10, pady=8).pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.library_list.bind("<Double-Button-1>", lambda _e: self.set_current_library_game())
        self._refresh_game_library()
        search.focus_set()

    def _filtered_game_indexes(self):
        search_var = getattr(self, "library_search_var", None)
        query = search_var.get().strip().casefold() if search_var is not None else ""
        return [i for i, game in enumerate(self.ps5_library) if query in game["title"].casefold() or query in game.get("notes", "").casefold()]

    def _refresh_game_library(self):
        if not hasattr(self, "library_list") or not self.library_list.winfo_exists():
            return
        self.library_list.delete(0, "end")
        self._library_visible_indexes = self._filtered_game_indexes()
        for i in self._library_visible_indexes:
            game = self.ps5_library[i]
            prefix = "▶  " if game.get("current") else ("★  " if game.get("favorite") else "   ")
            suffix = "  · JOGANDO (marcação manual)" if game.get("current") else ("  · Favorito" if game.get("favorite") else "")
            self.library_list.insert("end", prefix + game["title"] + suffix)
        if not self._library_visible_indexes:
            self.library_list.insert("end", "Nenhum jogo cadastrado. Clique em + Adicionar.")

    def _selected_library_game_index(self):
        if not hasattr(self, "library_list"):
            return None
        selection = self.library_list.curselection()
        if not selection:
            return None
        row = selection[0]
        indexes = getattr(self, "_library_visible_indexes", [])
        return indexes[row] if row < len(indexes) else None

    def add_library_game(self):
        title = simpledialog.askstring("Adicionar jogo", "Nome do jogo:", parent=self.library_window)
        if not title or not title.strip():
            return
        title = title.strip()[:120]
        if any(g["title"].casefold() == title.casefold() for g in self.ps5_library):
            messagebox.showinfo("HUBMON", "Esse jogo já está cadastrado.", parent=self.library_window)
            return
        notes = simpledialog.askstring("Observações", "Observações opcionais (edição, progresso etc.):", parent=self.library_window) or ""
        self.ps5_library.append({"title": title, "notes": notes[:500], "favorite": False, "current": False})
        if self._save_game_library():
            self._refresh_game_library()
            self._log(f"Jogo adicionado à biblioteca local: {title}")

    def edit_library_game(self):
        idx = self._selected_library_game_index()
        if idx is None:
            messagebox.showinfo("HUBMON", "Selecione um jogo primeiro.", parent=self.library_window)
            return
        game = self.ps5_library[idx]
        title = simpledialog.askstring("Editar jogo", "Nome do jogo:", initialvalue=game["title"], parent=self.library_window)
        if not title or not title.strip():
            return
        notes = simpledialog.askstring("Editar observações", "Notas opcionais:", initialvalue=game.get("notes", ""), parent=self.library_window)
        game["title"] = title.strip()[:120]
        game["notes"] = (notes or "")[:500]
        if self._save_game_library(): self._refresh_game_library()

    def toggle_library_favorite(self):
        idx = self._selected_library_game_index()
        if idx is None:
            messagebox.showinfo("HUBMON", "Selecione um jogo primeiro.", parent=self.library_window)
            return
        self.ps5_library[idx]["favorite"] = not self.ps5_library[idx].get("favorite", False)
        if self._save_game_library(): self._refresh_game_library()

    def remove_library_game(self):
        idx = self._selected_library_game_index()
        if idx is None:
            messagebox.showinfo("HUBMON", "Selecione um jogo primeiro.", parent=self.library_window)
            return
        title = self.ps5_library[idx]["title"]
        if messagebox.askyesno("Remover jogo", f"Remover '{title}' da biblioteca local?", parent=self.library_window):
            del self.ps5_library[idx]
            if self._save_game_library(): self._refresh_game_library()

    def set_current_library_game(self):
        idx = self._selected_library_game_index()
        if idx is None:
            messagebox.showinfo("HUBMON", "Selecione um jogo primeiro.", parent=self.library_window)
            return
        for game in self.ps5_library:
            game["current"] = False
        self.ps5_library[idx]["current"] = True
        if self._save_game_library():
            self._refresh_game_library()
            title = self.ps5_library[idx]["title"]
            self._log(f"Jogo atual definido manualmente na biblioteca: {title}")
            messagebox.showinfo("HUBMON", f"'{title}' foi marcado como jogo atual.\n\nNo PS5 original, esta marcação é manual; o HUBMON ainda não consegue detectar o jogo em execução.", parent=self.library_window)

    def _load_settings(self):
        defaults = {"profiles": {"ps5": {"input": 0x01}, "pc": {"input": 0x03}}}
        try:
            if self.config_path.exists():
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    defaults.update(loaded)
                    defaults.setdefault("profiles", {"ps5": {"input": 0x01}, "pc": {"input": 0x03}})
        except Exception:
            pass
        return defaults

    def _save_settings_file(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            self._log(f"Não foi possível salvar as configurações: {exc}")
            return False

    def save_profile(self, profile):
        if self.combo.current() < 0:
            self._set_status("Selecione um monitor primeiro", RED)
            return
        data = {"input": 0x01 if profile == "ps5" else 0x03}
        if self.last_read_brightness is not None:
            data["brightness"] = self.last_read_brightness
        if self.last_read_volume is not None:
            data["volume"] = self.last_read_volume
        self.settings.setdefault("profiles", {})[profile] = data
        if self._save_settings_file():
            self._log(f"Perfil {profile.upper()} salvo com entrada e valores atualmente lidos.")
            self._set_status(f"Perfil {profile.upper()} salvo", GREEN)

    def apply_profile(self, profile):
        data = self.settings.get("profiles", {}).get(profile, {})
        index = self.combo.current()
        if index < 0:
            self._set_status("Selecione um monitor primeiro", RED)
            return
        self._submit("apply_profile", monitor_index=index, profile=profile, values=data)
        self._set_status(f"Aplicando perfil {profile.upper()}…", MUTED)

    def _on_brightness_change(self, raw_value):
        if self.updating_brightness:
            return
        value = max(0, min(100, int(float(raw_value))))
        self.brightness_value_var.set(f"{value} %")
        self.brightness_hint_var.set("Aguardando envio ao monitor…")
        self._cancel_pending_brightness()
        index = self.combo.current()
        if index < 0 or self.brightness_dragging:
            return
        self.pending_brightness_after = self.after(650, lambda v=value, i=index: self._send_brightness(v, i))

    def _brightness_drag_start(self, _event=None):
        self.brightness_dragging = True
        self._cancel_pending_brightness()

    def _brightness_drag_end(self, _event=None):
        self.brightness_dragging = False
        if not self.updating_brightness and self.combo.current() >= 0:
            self._send_brightness(int(float(self.brightness_scale.get())), self.combo.current())

    def _brightness_key_release(self, _event=None):
        if not self.updating_brightness and self.combo.current() >= 0:
            self._cancel_pending_brightness()
            value, index = int(float(self.brightness_scale.get())), self.combo.current()
            self.pending_brightness_after = self.after(250, lambda: self._send_brightness(value, index))

    def _send_brightness(self, value, index):
        self._cancel_pending_brightness()
        if index != self.combo.current():
            return
        self._submit("set_brightness", monitor_index=index, value=value)

    def _cancel_pending_brightness(self):
        if self.pending_brightness_after:
            try: self.after_cancel(self.pending_brightness_after)
            except tk.TclError: pass
            self.pending_brightness_after = None

    def _set_brightness_slider(self, value):
        self.updating_brightness = True
        try:
            value = max(0, min(100, int(value)))
            self.brightness_scale.set(value)
            self.brightness_value_var.set(f"{value} %")
        finally:
            self.updating_brightness = False

    def _on_volume_change(self, raw_value):
        if self.updating_volume:
            return
        value = max(0, min(100, int(float(raw_value))))
        self.volume_value_var.set(f"{value} %")
        self.volume_hint_var.set("Valor selecionado; aguardando o envio ao monitor…")
        self._cancel_pending_volume()
        index = self.combo.current()
        if index < 0 or self.volume_dragging:
            return
        # Keyboard/wheel changes use a debounce. Mouse drags are sent only on release.
        self.pending_volume_after = self.after(750, lambda v=value, i=index: self._send_volume(v, i))

    def _volume_drag_start(self, _event=None):
        self.volume_dragging = True
        self._cancel_pending_volume()

    def _volume_drag_end(self, _event=None):
        self.volume_dragging = False
        if self.updating_volume:
            return
        index = self.combo.current()
        if index < 0:
            return
        self._cancel_pending_volume()
        # Tk's Scale class binding may update its final value after this binding.
        self.after_idle(lambda i=index: self._commit_volume_after_drag(i))

    def _commit_volume_after_drag(self, index):
        if self.combo.current() != index or self.updating_volume:
            return
        value = max(0, min(100, int(float(self.volume_scale.get()))))
        self._send_volume(value, index)

    def _volume_key_release(self, _event=None):
        if self.updating_volume or self.volume_dragging:
            return
        self._cancel_pending_volume()
        index = self.combo.current()
        if index < 0:
            return
        value = max(0, min(100, int(float(self.volume_scale.get()))))
        self.pending_volume_after = self.after(750, lambda v=value, i=index: self._send_volume(v, i))

    def _send_volume(self, value, index):
        self.pending_volume_after = None
        if self.combo.current() != index:
            return
        self._set_status(f"Ajustando volume para {value}%…", MUTED)
        self._submit("set_volume", monitor_index=index, value=value)

    def _cancel_pending_volume(self):
        if self.pending_volume_after is not None:
            try:
                self.after_cancel(self.pending_volume_after)
            except tk.TclError:
                pass
            self.pending_volume_after = None

    def ler_volume(self):
        index = self.combo.current()
        if index < 0:
            self._log("Selecione um monitor para ler o volume.")
            return
        self._set_status("Lendo volume…", MUTED)
        self._submit("get_volume", monitor_index=index)

    def alternar_mudo(self):
        index = self.combo.current()
        if index < 0:
            self._log("Selecione um monitor para alternar o silenciamento.")
            return
        self._set_status("Alternando silenciamento…", MUTED)
        self._submit("toggle_mute", monitor_index=index)

    def ler_entrada(self):
        index = self.combo.current()
        if index < 0:
            self._log("Selecione um monitor primeiro.")
            return
        self._submit("read_input", monitor_index=index)

    def ler_caps(self):
        index = self.combo.current()
        if index < 0:
            self._log("Selecione um monitor primeiro.")
            return
        self._submit("read_caps", monitor_index=index)

    def enviar_raw(self):
        if self.combo.current() < 0:
            self._log("Selecione um monitor primeiro.")
            return
        value_text = self.raw_entry.get().strip()
        try:
            value = int(value_text, 0)
            if not 0 <= value <= 255:
                raise ValueError
        except ValueError:
            messagebox.showerror("Código inválido", "Informe um número de 0 a 255, por exemplo 0x01 ou 98.", parent=self)
            return
        # Preserve original input-source manual behavior, not a generic VCP write.
        self._submit("raw_input", monitor_index=self.combo.current(), value=value)

    def toggle_advanced(self):
        if self.advanced_open:
            self.advanced_frame.grid_forget()
            self.log_card.grid_configure(row=4)
            self.footer_label.grid_configure(row=5)
            self.advanced_toggle.configure(text="＋  Ferramentas avançadas e diagnóstico")
            self.advanced_open = False
        else:
            self.advanced_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
            self.log_card.grid_configure(row=5)
            self.footer_label.grid_configure(row=6)
            self.advanced_toggle.configure(text="−  Ocultar ferramentas avançadas")
            self.advanced_open = True

    def limpar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ---------------------- Result handling ------------------
    def _handle_result(self, token, action, ok, data):
        if not ok:
            msg = str(data)
            self._log(f"ERRO · {action}: {msg}")
            self._set_status("Comando não confirmado", RED)
            if action in ("get_volume", "set_volume"):
                self.volume_hint_var.set("A comunicação do volume falhou. O valor do controle não confirma o volume audível.")
                if action == "set_volume" and self.last_read_volume is not None:
                    self._set_volume_slider(self.last_read_volume)
            elif action in ("get_brightness", "set_brightness"):
                self.brightness_hint_var.set("Brilho DDC/CI indisponível neste monitor ou falha de comunicação.")
                if action == "set_brightness" and self.last_read_brightness is not None:
                    self._set_brightness_slider(self.last_read_brightness)
            elif action == "toggle_mute":
                self.volume_hint_var.set("O monitor não confirmou o comando de silenciamento. O suporte varia por modelo.")
            elif action == "detect":
                self.status_dot.configure(fg=RED)
                if "monitorcontrol" in msg.lower():
                    self._log("Execute INSTALAR.bat para instalar/atualizar a dependência necessária.")
            return

        if action == "detect":
            self.monitor_infos = data
            values = [info["name"] for info in data]
            self.combo.configure(values=values)
            if values:
                self.combo.current(0)
                self._apply_monitor_info(data[0])
                self.status_dot.configure(fg=GREEN)
                self._set_status(f"{len(values)} monitor(es) encontrado(s)", GREEN)
                self._log(f"{len(values)} monitor(es) DDC/CI detectado(s).")
                for info in data:
                    self._log(f"{info['name']} · entrada {self._input_name(info.get('input'))} · volume {str(info.get('volume'))+'%' if info.get('volume') is not None else 'não lido'}")
            else:
                self.status_dot.configure(fg=RED)
                self._set_status("Nenhum monitor detectado", RED)
                self._log("Nenhum monitor DDC/CI detectado. Confira o OSD, o cabo e execute HUBMON com as permissões necessárias.")
            return

        if action == "inspect_monitor":
            index = self.combo.current()
            if index >= 0 and index < len(self.monitor_infos):
                self.monitor_infos[index] = data
                self._apply_monitor_info(data)
                self._set_status("Monitor pronto", GREEN)
            return

        if action in ("switch_input", "raw_input"):
            value = data["requested"]
            actual = data.get("actual")
            name = INPUT_NAMES.get(value, f"código 0x{value:02X}")
            if action == "switch_input":
                self._log(f"Comando enviado: {name} (0x{value:02X}).")
            else:
                self._log(f"Código de entrada enviado: 0x{value:02X}.")
            if actual is not None:
                self._update_input_display(actual)
                self._log(f"Leitura de retorno: {self._input_name(actual)} (0x{actual:02X}).")
                self._set_status(f"Entrada: {self._input_name(actual)}", GREEN)
            else:
                self.input_status_var.set(f"Comando: {name}")
                self._set_status("Comando enviado; retorno indisponível", MUTED)
            if action == "switch_input" and value in (0x01, 0x03):
                profile = "ps5" if value == 0x01 else "pc"
                saved = self.settings.get("profiles", {}).get(profile, {})
                if "brightness" in saved or "volume" in saved:
                    self.after(150, lambda p=profile: self.apply_profile(p))
            return

        if action == "read_input":
            self._update_input_display(int(data))
            self._log(f"Entrada atual: {self._input_name(int(data))} (0x{int(data):02X}).")
            self._set_status("Entrada lida", GREEN)
            return

        if action == "apply_profile":
            self._log(f"Perfil {data['profile'].upper()} aplicado; entrada retornada: {self._input_name(data.get('input'))}.")
            if data.get("input") is not None:
                self._update_input_display(data["input"])
            if data.get("brightness") is not None:
                self.last_read_brightness = int(data["brightness"])
                self._set_brightness_slider(data["brightness"])
            if data.get("volume") is not None:
                self.last_read_volume = int(data["volume"])
                self._set_volume_slider(data["volume"])
            for warning in data.get("warnings", []): self._log(f"Aviso ao aplicar perfil: {warning}")
            self._set_status("Perfil aplicado com avisos" if data.get("warnings") else f"Perfil {data['profile'].upper()} aplicado", MUTED if data.get("warnings") else GREEN)
            return

        if action == "set_brightness":
            actual = data.get("actual")
            if actual is not None:
                self.last_read_brightness = int(actual)
                self._set_brightness_slider(actual)
                self.brightness_hint_var.set("Brilho lido novamente do monitor após o comando.")
                self._set_status("Brilho atualizado", GREEN)
                self._log(f"Brilho solicitado: {data['requested']}%; leitura após comando: {actual}%.")
            else:
                self.brightness_hint_var.set("Comando enviado, mas não foi possível ler o brilho de volta.")
                self._set_status("Brilho sem confirmação de leitura", MUTED)
                self._log(f"Comando de brilho {data['requested']}% enviado; sem leitura de retorno.")
            return

        if action == "read_caps":
            try:
                cmds = data.get("cmds", {}) if isinstance(data, dict) else {}
                has_volume = 0x62 in cmds or "98" in cmds
                has_input = 0x60 in cmds or "96" in cmds
                self._log(f"Capabilities: {data}")
                self._log(f"Capabilities anunciam VCP 0x62 (volume): {'sim' if has_volume else 'não/sem informação'}; VCP 0x60 (entrada): {'sim' if has_input else 'não/sem informação'}. A lista de capabilities pode ser incompleta.")
            except Exception:
                self._log(f"Capabilities: {data}")
            self._set_status("Diagnóstico concluído", GREEN)
            return

        if action == "get_volume":
            value = max(0, min(100, int(data)))
            self.last_read_volume = value
            self._set_volume_slider(value)
            self.volume_hint_var.set("O monitor reportou este valor via DDC/CI; a alteração audível precisa ser confirmada no próprio áudio.")
            self._log(f"Registro VCP 0x62 lido: {value}% (não confirma, por si só, o volume acústico).")
            self._set_status("Valor VCP lido", GREEN)
            return

        if action == "set_volume":
            requested = int(data["requested"])
            actual = data.get("actual")
            write_ok = bool(data.get("write_ok"))
            first_error = data.get("first_error")
            retry_error = data.get("retry_error")
            if first_error and write_ok:
                self._log("A primeira escrita DDC/CI falhou; a retentativa foi aceita.")
            elif first_error and retry_error:
                self._log(f"ERRO · set_volume: primeira tentativa: {first_error}; retentativa: {retry_error}")
            if actual is not None:
                self.last_read_volume = actual
                self._set_volume_slider(actual)
            if not write_ok:
                self.volume_hint_var.set("O monitor não aceitou a escrita de volume. O controle foi restaurado ao último valor lido.")
                self._log(f"Escrita não confirmada. Valor VCP lido depois da tentativa: {actual if actual is not None else 'indisponível'}%. Isso não prova alteração audível.")
                self._set_status("Escrita de volume falhou", RED)
            elif actual is None:
                self.volume_hint_var.set("O comando foi enviado, mas não houve leitura de retorno; volume audível não confirmado.")
                self._log(f"Comando VCP de volume {requested}% enviado; sem leitura de retorno e sem confirmação acústica.")
                self._set_status("Sem leitura de retorno", MUTED)
            elif actual != requested:
                self.volume_hint_var.set(f"Foi pedido {requested}%, mas o registro VCP retornou {actual}%. O áudio ainda não foi verificado.")
                self._log(f"Valor solicitado: {requested}%; valor VCP lido após escrita: {actual}%. Não confirmado como mudança audível.")
                self._set_status("Valor retornado diferente", RED)
            else:
                self.volume_hint_var.set("O registro VCP corresponde ao valor pedido, mas isso não garante mudança real no som. Teste durante áudio do PS5.")
                self._log(f"Registro VCP 0x62 retornou {actual}% após o comando; efeito no som não verificado.")
                self._set_status("Registro VCP atualizado", MUTED)
            return

        if action == "toggle_mute":
            self.current_mute_state = bool(data["muted"])
            self._update_mute_button()
            state = "silenciado" if self.current_mute_state else "com áudio ativo"
            self.volume_hint_var.set(f"Monitor {state} via DDC/CI.")
            self._log(f"Áudio do monitor: {state}.")
            self._set_status("Silenciamento atualizado", GREEN)
            return

    def _apply_monitor_info(self, info):
        self.current_input_code = info.get("input")
        self._update_input_display(self.current_input_code)
        volume = info.get("volume")
        if volume is not None:
            self.last_read_volume = int(volume)
            self._set_volume_slider(volume)
            self.volume_hint_var.set("Valor VCP lido do monitor; o suporte a ajuste audível depende do firmware.")
        else:
            self.last_read_volume = None
            self.volume_hint_var.set("Valor não lido. O controle depende do suporte do monitor ao DDC/CI.")
        brightness = info.get("brightness")
        if brightness is not None:
            self.last_read_brightness = int(brightness)
            self._set_brightness_slider(brightness)
            self.brightness_hint_var.set("Brilho reportado via DDC/CI.")
        else:
            self.last_read_brightness = None
            self.brightness_hint_var.set("Este monitor não respondeu à leitura de brilho; o controle pode não ser suportado.")
        self.current_mute_state = info.get("mute")
        self._update_mute_button()

    def _set_volume_slider(self, value):
        self.updating_volume = True
        try:
            value = max(0, min(100, int(value)))
            self.volume_scale.set(value)
            self.volume_value_var.set(f"{value} %")
        finally:
            self.updating_volume = False

    def _update_input_display(self, code):
        if code is None:
            self.input_status_var.set("Não verificada")
            self.current_input_code = None
        else:
            code = int(code)
            self.current_input_code = code
            self.input_status_var.set(self._input_name(code))
        if self.current_input_code == 0x01:
            self.ps5_btn.configure(highlightthickness=1, highlightbackground=BORDER)
            self.pc_btn.configure(highlightthickness=0)
        elif self.current_input_code == 0x03:
            self.pc_btn.configure(highlightthickness=1, highlightbackground=BLUE)
            self.ps5_btn.configure(highlightthickness=0)
        else:
            self.ps5_btn.configure(highlightthickness=0)
            self.pc_btn.configure(highlightthickness=0)

    def _update_mute_button(self):
        if self.current_mute_state is True:
            self.mute_btn.configure(text="◖  Restaurar áudio")
        else:
            self.mute_btn.configure(text="◖  Silenciar")

    @staticmethod
    def _input_name(code):
        if code is None:
            return "não lida"
        try:
            value = int(code)
        except (TypeError, ValueError):
            return str(code)
        return INPUT_NAMES.get(value, f"Entrada 0x{value:02X}")

    def _set_status(self, text, color=MUTED):
        self.status_var.set(text)
        self.status_dot.configure(fg=color)

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        # Keep the visible log bounded in long sessions.
        line_count = int(self.log.index("end-1c").split(".")[0])
        if line_count > 240:
            self.log.delete("1.0", f"{line_count - 200}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _close(self):
        self._cancel_pending_volume()
        self._cancel_pending_brightness()
        try:
            self.task_queue.put_nowait(None)
        except Exception:
            pass
        self.destroy()


def main():
    # Named Windows mutex prevents accidental duplicate HUBMON windows, which can
    # contend for the monitor's DDC/I²C bus. On other platforms, normal startup.
    mutex = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
            mutex = kernel32.CreateMutexW(None, False, r"Local\HUBMON_SingleInstance_v1")
            ERROR_ALREADY_EXISTS = 183
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                try:
                    ctypes.windll.user32.MessageBoxW(None, "O HUBMON já está aberto. Use a janela existente para evitar conflitos DDC/CI.", "HUBMON", 0x40)
                finally:
                    raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            mutex = None
    app = Hub()
    try:
        app.mainloop()
    finally:
        if mutex:
            try:
                ctypes.windll.kernel32.ReleaseMutex(mutex)
                ctypes.windll.kernel32.CloseHandle(mutex)
            except Exception:
                pass


if __name__ == "__main__":
    main()
