"""
╔══════════════════════════════════════════════════════════════════╗
║    GLOBAL OPS CONTROLLING COMMAND DECK (Demo Version)            ║
║    Unified Desktop Launcher for Operations Dashboards            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import threading
import webbrowser
import time
import customtkinter as ctk
from tkinter import messagebox
import queue

# ==============================================================================
# PALETTE "COMMAND DECK" — ADATTIVA
# ==============================================================================
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

BG_MAIN     = ("#F2F0EA", "#0B0D10")
BG_CARD     = ("#FFFFFF", "#1E222A")
BG_INPUT    = ("#F9FAFB", "#0D0E11")
BORDER      = ("#E5E7EB", "#2D3139")
TEXT_MAIN   = ("#111827", "#EDEFF2")
TEXT_MUTED  = ("#6B7280", "#9CA3AF")
BTN_TEXT    = ("#FFFFFF", "#0B0D10")

COLOR_ALPHA   = ("#1D4ED8", "#60A5FA")
COLOR_BETA    = ("#D97706", "#FBBF24")
COLOR_GLOBAL  = ("#15803D", "#4ADE80")
COLOR_EXCO    = ("#0F8C82", "#4FD1C5")

ACCENT_TEAL   = ("#0F8C82", "#4FD1C5")
ACCENT_BLUE   = ("#2450C2", "#5B8CFF")
ACCENT_ORANGE = ("#C9642A", "#FF7A33")
ACCENT_GREEN  = ("#059669", "#10B981")
COLOR_OK      = ("#16A34A", "#10B981")
COLOR_OFF     = ("#DC2626", "#EF4444")

FONT_HEAD = "Segoe UI Semibold"
FONT_MONO = "Consolas"

# ==============================================================================
# LINKS AL PORTFOLIO GITHUB PAGES
# Sostituisci questi URL con i tuoi veri link di GitHub Pages
# ==============================================================================
DASHBOARDS = {
    "ALPHA": {
        "title": "Efficiency Plant Alpha",
        "url": "https://giacomocame.github.io/business-operations-toolkit/01_plant_efficiency/",
        "color": COLOR_ALPHA,
    },
    "GLOBAL": {
        "title": "Supply Chain Deck",
        "url": "https://giacomocame.github.io/business-operations-toolkit/02_supply_chain_deck/",
        "color": COLOR_GLOBAL,
    },
    "EXCO": {
        "title": "Extra Consumptions",
        "url": "https://giacomocame.github.io/business-operations-toolkit/03_extra_consumptions/",
        "color": COLOR_EXCO,
    },
    "MAT": {
        "title": "Indirect Materials",
        "url": "https://giacomocame.github.io/business-operations-toolkit/04_indirect_materials_analytics/",
        "color": COLOR_BETA,
    }
}

# ==============================================================================
# REDIREZIONE CONSOLE -> CTkTextbox (Thread-safe)
# ==============================================================================
class ConsoleRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self._queue = queue.Queue()
        self._poll()

    def write(self, str_val):
        self._queue.put(str_val)

    def flush(self):
        pass

    def _poll(self):
        try:
            while True:
                str_val = self._queue.get_nowait()
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", str_val)
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
        except queue.Empty:
            pass
        self.text_widget.after(50, self._poll)


# ==============================================================================
# FINESTRA PRINCIPALE 
# ==============================================================================
class AppGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Operations Command Deck - TechCorp Global")
        self.geometry("1000x700")
        self.minsize(880, 600)
        self.configure(fg_color=BG_MAIN)

        self._main_thread_queue = queue.Queue()
        self._poll_main_thread_queue()

        self._build_ui()

        # Reindirizza stdout per mostrare log finti/reali nella GUI
        redirector = ConsoleRedirector(self.log_textbox)
        sys.stdout = redirector
        sys.stderr = redirector
        
        print("System Initialized. Welcome to the Operations Command Deck.")
        print("All modules loaded successfully in serverless mode.\n")

    def _run_on_main_thread(self, callable_):
        self._main_thread_queue.put(callable_)

    def _poll_main_thread_queue(self):
        try:
            while True:
                callable_ = self._main_thread_queue.get_nowait()
                callable_()
        except queue.Empty:
            pass
        self.after(50, self._poll_main_thread_queue)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. HEADER
        header_frame = ctk.CTkFrame(self, corner_radius=14, fg_color=BG_CARD, border_width=1, border_color=BORDER)
        header_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        lbl_title = ctk.CTkLabel(header_frame, text="🏭 OPERATIONS COMMAND DECK", font=ctk.CTkFont(family=FONT_HEAD, size=20, weight="bold"), text_color=TEXT_MAIN)
        lbl_title.grid(row=0, column=0, padx=20, pady=(12, 2), sticky="w")

        lbl_subtitle = ctk.CTkLabel(header_frame, text="Unified Operations & Analytics Launcher | Serverless Edition", font=ctk.CTkFont(family=FONT_MONO, size=12), text_color=TEXT_MUTED)
        lbl_subtitle.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        btn_all = ctk.CTkButton(header_frame, text="🚀 Simulate ETL Pipeline", fg_color=ACCENT_BLUE, text_color=BTN_TEXT, font=ctk.CTkFont(family=FONT_MONO, size=12, weight="bold"), corner_radius=999, command=self.simulate_etl)
        btn_all.grid(row=0, column=1, rowspan=2, padx=20, pady=12, sticky="e")

        # 2. CARDS 
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)

        self.card_widgets = {}
        for idx, (key, info) in enumerate(DASHBOARDS.items()):
            card = ctk.CTkFrame(cards_frame, corner_radius=14, fg_color=BG_CARD, border_width=1, border_color=BORDER)
            card.grid(row=0, column=idx, padx=5, pady=5, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)

            lbl_card_title = ctk.CTkLabel(card, text=info["title"], font=ctk.CTkFont(family=FONT_HEAD, size=14, weight="bold"), text_color=info["color"])
            lbl_card_title.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

            badge_frame = ctk.CTkFrame(card, fg_color=BG_INPUT, corner_radius=8)
            badge_frame.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

            lbl_status = ctk.CTkLabel(badge_frame, text="🟢 Live on GitHub Pages", font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), text_color=COLOR_OK)
            lbl_status.pack(padx=10, pady=6)

            btn_open = ctk.CTkButton(
                card, text="🌐 Launch Dashboard",
                fg_color=BG_INPUT, hover_color=BORDER, text_color=TEXT_MAIN,
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                corner_radius=10, border_width=1, border_color=BORDER,
                command=lambda u=info["url"]: webbrowser.open(u)
            )
            btn_open.grid(row=3, column=0, padx=15, pady=(20, 15), sticky="ew")

        # 3. PANNELLO LOG / CONSOLE
        log_frame = ctk.CTkFrame(self, corner_radius=14, fg_color=BG_CARD, border_width=1, border_color=BORDER)
        log_frame.grid(row=2, column=0, padx=15, pady=(10, 15), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        log_header.grid_columnconfigure(0, weight=1)

        lbl_log = ctk.CTkLabel(log_header, text="📋 SYSTEM CONSOLE & EXECUTION LOG", font=ctk.CTkFont(family=FONT_MONO, size=12, weight="bold"), text_color=TEXT_MUTED)
        lbl_log.grid(row=0, column=0, sticky="w")

        btn_clear = ctk.CTkButton(log_header, text="Clear Log", width=90, height=24, fg_color=BG_INPUT, text_color=TEXT_MAIN, border_width=1, border_color=BORDER, font=ctk.CTkFont(family=FONT_MONO, size=10, weight="bold"), command=self.clear_log)
        btn_clear.grid(row=0, column=1, sticky="e")

        self.log_textbox = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family=FONT_MONO, size=11), fg_color=BG_INPUT, text_color=ACCENT_TEAL, corner_radius=10, border_width=1, border_color=BORDER, wrap="word", state="disabled")
        self.log_textbox.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    def clear_log(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("0.0", "end")
        self.log_textbox.configure(state="disabled")

    def simulate_etl(self):
        def _task():
            print("🚀 Initiating simulated ETL Pipeline extraction...")
            time.sleep(1)
            print("📥 Connecting to ERP Database (Mocking connection)...")
            time.sleep(1.5)
            print("✅ Data extracted successfully (60 days history).")
            print("⚙️ Processing rolling aggregations via Pandas...")
            time.sleep(2)
            print("📊 Generating Serverless HTML Payloads...")
            time.sleep(1)
            print("✅ All processes complete. Dashboards are ready for viewing.\n")
            
        threading.Thread(target=_task, daemon=True).start()

if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()
