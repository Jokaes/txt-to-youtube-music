"""Tkinter Graphical User Interface for TxtToYoutubeMusic."""

import os
import sys
import queue
import logging
import threading
import traceback
import webbrowser
import json
import datetime
from tkinter import messagebox, filedialog
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# Import from txt_to_ytmusic package
from .utils import read_song_queries
from .ytmusic_api import initialize_ytmusic, sanitize_auth_headers, validate_auth_headers
from .playlist_manager import create_playlist, add_item_to_playlist


class ThreadsafeConsoleInputRedirector:
    """Redirect stdout/stderr and print calls to the Queue."""
    def __init__(self, queue_obj, tag="normal"):
        self.queue = queue_obj
        self.tag = tag

    def write(self, text):
        if text.strip() or '\n' in text:
            self.queue.put(("log", (text, self.tag)))

    def flush(self):
        pass


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record) + '\n'
        tag = "info"
        if record.levelno >= logging.ERROR:
            tag = "error"
        elif record.levelno >= logging.WARNING:
            tag = "warning"
        self.log_queue.put(("log", (msg, tag)))


class YTMusicGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Txt To YouTube Music Playlist Creator")
        self.geometry("900x750")
        self.minsize(800, 600)
        
        # Configure overall dark theme colors
        self.colors = {
            "bg_dark": "#121212",
            "bg_card": "#1E1E1E",
            "bg_input": "#2D2D2D",
            "text_light": "#FFFFFF",
            "text_muted": "#A0A0A0",
            "accent_red": "#FF4C4C",
            "accent_red_active": "#E53935",
            "success_green": "#4CAF50",
            "warn_orange": "#FFC107",
            "border": "#333333"
        }
        
        self.configure(bg=self.colors["bg_dark"])
        
        # Background worker state variables
        self.worker_thread = None
        self.stop_requested = False
        self.gui_queue = queue.Queue()
        
        # Keep track of active playlist link
        self.playlist_url = None
        
        # Setup UI custom styles
        self.setup_styles()
        
        # Build UI layout
        self.create_widgets()
        
        # Set up a polling handler for queue events
        self.after(100, self.poll_queue)
        
        # If headers_auth.json doesn't exist, we will warn user gracefully later

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Frame styles
        style.configure("TFrame", background=self.colors["bg_dark"])
        style.configure("Card.TFrame", background=self.colors["bg_card"], borderwidth=1, relief="solid")
        style.configure("CardInner.TFrame", background=self.colors["bg_card"], borderwidth=0)
        
        # Label styles
        style.configure("TLabel", background=self.colors["bg_dark"], foreground=self.colors["text_light"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=self.colors["bg_dark"], foreground=self.colors["text_light"], font=("Segoe UI", 16, "bold"))
        style.configure("Sub.TLabel", background=self.colors["bg_dark"], foreground=self.colors["text_muted"], font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=self.colors["bg_card"], foreground=self.colors["text_light"], font=("Segoe UI", 10))
        style.configure("CardHeader.TLabel", background=self.colors["bg_card"], foreground=self.colors["text_light"], font=("Segoe UI", 12, "bold"))
        style.configure("Stat.TLabel", background=self.colors["bg_card"], foreground=self.colors["text_light"], font=("Segoe UI", 10, "bold"))
        
        # Entry/Combo styles
        style.configure("TEntry", fieldbackground=self.colors["bg_input"], foreground=self.colors["text_light"], bordercolor=self.colors["border"])
        style.map("TEntry", fieldbackground=[("active", self.colors["bg_input"]), ("disabled", self.colors["bg_dark"])])
        
        style.configure("TCombobox", fieldbackground=self.colors["bg_input"], foreground=self.colors["text_light"], selectbackground=self.colors["bg_input"])
        style.map("TCombobox", fieldbackground=[("readonly", self.colors["bg_input"])], foreground=[("readonly", self.colors["text_light"])])
        
        # Button styles
        style.configure("TButton", background=self.colors["bg_input"], foreground=self.colors["text_light"], bordercolor=self.colors["border"], font=("Segoe UI", 10, "bold"), padding=6)
        style.map("TButton", 
                  background=[("active", self.colors["border"]), ("disabled", self.colors["bg_dark"])],
                  foreground=[("disabled", self.colors["text_muted"])])
        
        # Red YouTube-like button style
        style.configure("Red.TButton", background=self.colors["accent_red"], foreground=self.colors["text_light"], bordercolor=self.colors["accent_red"], font=("Segoe UI", 11, "bold"), padding=8)
        style.map("Red.TButton", 
                  background=[("active", self.colors["accent_red_active"]), ("disabled", self.colors["bg_dark"])],
                  foreground=[("disabled", self.colors["text_muted"])])
        
        # Checkbutton styles
        style.configure("TCheckbutton", background=self.colors["bg_card"], foreground=self.colors["text_light"], font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", self.colors["bg_card"])])
        
        # Progressbar style
        style.configure("Red.Horizontal.TProgressbar", thickness=15, troughcolor=self.colors["bg_dark"], background=self.colors["accent_red"])

    def create_widgets(self):
        # Master container with grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.columnconfigure(0, weight=6)  # Left columns
        container.columnconfigure(1, weight=4)  # Right column (35-40%)
        container.rowconfigure(2, weight=1)     # Logs take rest
        
        # ==========================================
        # HEADER
        # ==========================================
        header_frame = ttk.Frame(container)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        header_frame.columnconfigure(2, weight=1)
        
        title_icon = ttk.Label(header_frame, text="🎵", font=("Segoe UI", 16), background=self.colors["accent_red"], foreground=self.colors["text_light"], padding=(8, 4))
        title_icon.grid(row=0, column=0, padx=(0, 10))
        
        title_lbl = ttk.Label(header_frame, text="Txt to YouTube Music", style="Header.TLabel")
        title_lbl.grid(row=0, column=1)
        
        subtitle_lbl = ttk.Label(header_frame, text="Create playlists effortlessly from list of song/search queries", style="Sub.TLabel")
        subtitle_lbl.grid(row=0, column=2, sticky="w", padx=15)

        # ==========================================
        # LEFT COLUMNS (File Config, Playlist, Progress)
        # ==========================================
        left_cols_frame = ttk.Frame(container)
        left_cols_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_cols_frame.columnconfigure(0, weight=1)
        left_cols_frame.columnconfigure(1, weight=1)
        left_cols_frame.rowconfigure(0, weight=1)
        
        # Top section of left cols (Cards 1 and 2 side by side)
        top_left_frame = ttk.Frame(left_cols_frame)
        top_left_frame.grid(row=0, column=0, columnspan=2, sticky="new")
        top_left_frame.columnconfigure(0, weight=1)
        top_left_frame.columnconfigure(1, weight=1)
        
        # Card 1: File Config
        input_card = ttk.Frame(top_left_frame, style="Card.TFrame", padding=15)
        input_card.grid(row=0, column=0, sticky="new", padx=(0, 5))
        input_card.columnconfigure(0, weight=1)
        
        ttk.Label(input_card, text="❶ File Configuration", style="CardHeader.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        
        ttk.Label(input_card, text="Songs File (.txt)", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 2))
        file_input_frame = ttk.Frame(input_card, style="CardInner.TFrame")
        file_input_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        file_input_frame.columnconfigure(0, weight=1)
        self.songs_file_var = tk.StringVar(value="songs.txt")
        self.songs_file_ent = ttk.Entry(file_input_frame, textvariable=self.songs_file_var)
        self.songs_file_ent.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(file_input_frame, text="📁 Browse", command=self.browse_songs_file).grid(row=0, column=1)
        
        ttk.Label(input_card, text="Auth JSON", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=(5, 2))
        auth_input_frame = ttk.Frame(input_card, style="CardInner.TFrame")
        auth_input_frame.grid(row=4, column=0, sticky="ew", pady=0)
        auth_input_frame.columnconfigure(0, weight=1)
        self.auth_file_var = tk.StringVar(value="headers_auth.json")
        self.auth_file_ent = ttk.Entry(auth_input_frame, textvariable=self.auth_file_var)
        self.auth_file_ent.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(auth_input_frame, text="📁 Browse", command=self.browse_auth_file).grid(row=0, column=1)
        
        # Card 2: Playlist details
        playlist_card = ttk.Frame(top_left_frame, style="Card.TFrame", padding=15)
        playlist_card.grid(row=0, column=1, sticky="new", padx=(5, 0))
        playlist_card.columnconfigure(0, weight=1)
        
        ttk.Label(playlist_card, text="❷ Playlist & Matching Options", style="CardHeader.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 15))
        
        ttk.Label(playlist_card, text="Playlist Title", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 2))
        self.auto_title_var = tk.BooleanVar(value=True)
        self.title_var = tk.StringVar(value="My YouTube Music Playlist")
        self.title_ent = ttk.Entry(playlist_card, textvariable=self.title_var, state="disabled")
        self.title_ent.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        
        self.auto_title_cb = ttk.Checkbutton(playlist_card, text="Auto-generate with timestamp", variable=self.auto_title_var, command=self.toggle_title_entry)
        self.auto_title_cb.grid(row=3, column=0, sticky="w", pady=(0, 10))
        
        ttk.Label(playlist_card, text="Description (optional)", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=(0, 2))
        self.desc_var = tk.StringVar()
        self.desc_ent = ttk.Entry(playlist_card, textvariable=self.desc_var, state="disabled")
        self.desc_ent.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(playlist_card, text="Visibility", style="Card.TLabel").grid(row=6, column=0, sticky="w", pady=(0, 2))
        self.privacy_var = tk.StringVar(value="Private")
        privacy_combo = ttk.Combobox(playlist_card, textvariable=self.privacy_var, values=["Private", "Public", "Unlisted"], state="readonly")
        privacy_combo.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        
        self.duplicates_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(playlist_card, text="Allow duplicates in playlist", variable=self.duplicates_var).grid(row=8, column=0, sticky="w", pady=2)
        
        self.perfect_match_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(playlist_card, text="Only add perfect text matches (case-insensitive)", variable=self.perfect_match_var).grid(row=9, column=0, sticky="w", pady=2)

        # Progress Card
        progress_card = ttk.Frame(left_cols_frame, style="Card.TFrame", padding=15)
        progress_card.grid(row=1, column=0, columnspan=2, sticky="sew", pady=(15, 0))
        progress_card.columnconfigure(0, weight=1)
        
        prog_top_frame = ttk.Frame(progress_card, style="CardInner.TFrame")
        prog_top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        prog_top_frame.columnconfigure(0, weight=1)
        
        ttk.Label(prog_top_frame, text="📈 Progress", style="CardHeader.TLabel").grid(row=0, column=0, sticky="w")
        
        self.start_btn = ttk.Button(prog_top_frame, text="▷ Start Playlist Creation", style="Red.TButton", command=self.start_processing)
        self.start_btn.grid(row=0, column=1, padx=(10, 5))
        self.cancel_btn = ttk.Button(prog_top_frame, text="✕ Cancel", command=self.request_cancel, state="disabled")
        self.cancel_btn.grid(row=0, column=2)
        
        self.progress_bar = ttk.Progressbar(progress_card, orient="horizontal", mode="determinate", style="Red.Horizontal.TProgressbar")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=5)
        
        prog_bot_frame = ttk.Frame(progress_card, style="CardInner.TFrame")
        prog_bot_frame.grid(row=2, column=0, sticky="ew")
        prog_bot_frame.columnconfigure(1, weight=1)
        
        self.progress_pct_lbl = ttk.Label(prog_bot_frame, text="0% Complete", style="Sub.TLabel")
        self.progress_pct_lbl.grid(row=0, column=0, sticky="w")
        
        self.progress_txt_lbl = ttk.Label(prog_bot_frame, text="0 / 0 songs processed", style="Sub.TLabel")
        self.progress_txt_lbl.grid(row=0, column=1, sticky="e")

        # ==========================================
        # RIGHT COLUMN - AUTH SETUP & STATISTICS
        # ==========================================
        right_column = ttk.Frame(container)
        right_column.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        right_column.columnconfigure(0, weight=1)
        
        # Setup Auth Card
        auth_setup_card = ttk.Frame(right_column, style="Card.TFrame", padding=15)
        auth_setup_card.grid(row=0, column=0, sticky="new", pady=(0, 15))
        auth_setup_card.columnconfigure(0, weight=1)
        
        ttk.Label(auth_setup_card, text="🛡️ Authentication Assistant", style="CardHeader.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Label(
            auth_setup_card, 
            text="Need help logging in? Paste your copied browser headers directly to set up your credentials automatically.",
            style="Sub.TLabel",
            wraplength=280,
            justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(0, 15))
        
        ttk.Button(auth_setup_card, text="Configure Headers Auth Helper ↗", command=self.open_auth_assistant).grid(row=2, column=0, sticky="ew")
        
        # Stats Counter Card
        stats_card = ttk.Frame(right_column, style="Card.TFrame", padding=15)
        stats_card.grid(row=1, column=0, sticky="nsew")
        stats_card.columnconfigure(0, weight=1)
        stats_card.columnconfigure(1, weight=0)
        
        ttk.Label(stats_card, text="∿ Processing Status", style="CardHeader.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        
        # 1. Processed
        ttk.Label(stats_card, text="🎵 Songs Processed", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.progress_count_lbl = ttk.Label(stats_card, text="0 / 0", style="Stat.TLabel")
        self.progress_count_lbl.grid(row=1, column=1, sticky="e", pady=6)
        
        # 2. Added 
        ttk.Label(stats_card, text="✅ Successfully Added", style="Card.TLabel", foreground=self.colors["success_green"]).grid(row=2, column=0, sticky="w", pady=6)
        self.stat_added_lbl = ttk.Label(stats_card, text="0", style="Stat.TLabel", foreground=self.colors["success_green"])
        self.stat_added_lbl.grid(row=2, column=1, sticky="e", pady=6)
        
        # 3. Duplicates
        ttk.Label(stats_card, text="🟡 Duplicates Skipped", style="Card.TLabel", foreground=self.colors["warn_orange"]).grid(row=3, column=0, sticky="w", pady=6)
        self.stat_dup_lbl = ttk.Label(stats_card, text="0", style="Stat.TLabel", foreground=self.colors["warn_orange"])
        self.stat_dup_lbl.grid(row=3, column=1, sticky="e", pady=6)
        
        # 4. Not found
        ttk.Label(stats_card, text="🚫 Songs Not Found", style="Card.TLabel", foreground=self.colors["accent_red"]).grid(row=4, column=0, sticky="w", pady=6)
        self.stat_notfound_lbl = ttk.Label(stats_card, text="0", style="Stat.TLabel", foreground=self.colors["accent_red"])
        self.stat_notfound_lbl.grid(row=4, column=1, sticky="e", pady=6)
        
        # 5. Failed
        ttk.Label(stats_card, text="❌ Errors / Failed Additions", style="Card.TLabel", foreground=self.colors["accent_red"]).grid(row=5, column=0, sticky="w", pady=6)
        self.stat_failed_lbl = ttk.Label(stats_card, text="0", style="Stat.TLabel", foreground=self.colors["accent_red"])
        self.stat_failed_lbl.grid(row=5, column=1, sticky="e", pady=6)
        
        # 6. Elapsed
        ttk.Label(stats_card, text="🕒 Elapsed Time", style="Card.TLabel", foreground=self.colors["text_muted"]).grid(row=6, column=0, sticky="w", pady=6)
        self.stat_time_lbl = ttk.Label(stats_card, text="0s", style="Stat.TLabel", foreground=self.colors["text_muted"])
        self.stat_time_lbl.grid(row=6, column=1, sticky="e", pady=6)
        
        # Playlist Link Button
        self.playlist_btn = ttk.Button(stats_card, text="Open YouTube Music Playlist ↗", command=self.open_playlist_in_browser, state="disabled")
        stats_card.rowconfigure(7, weight=1)
        self.playlist_btn.grid(row=8, column=0, columnspan=2, sticky="sew", pady=(15, 0))

        # ==========================================
        # BOTTOM ROW - LIVE CONSOLE LOGS
        # ==========================================
        log_card = ttk.Frame(container, style="Card.TFrame", padding=15)
        log_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(15, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        
        log_top = ttk.Frame(log_card, style="CardInner.TFrame")
        log_top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        log_top.columnconfigure(0, weight=1)
        
        ttk.Label(log_top, text="</> Execution Console Logs", style="CardHeader.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(log_top, text="🗑️ Clear Logs", command=self.clear_console).grid(row=0, column=1, sticky="e")
        
        self.log_text = ScrolledText(
            log_card, 
            bg=self.colors["bg_dark"], 
            fg=self.colors["text_light"], 
            insertbackground=self.colors["text_light"],
            font=("Consolas", 10),
            padx=10,
            pady=10,
            borderwidth=0,
            relief="flat",
            height=8
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        
        # Define log tags for output color schemes
        self.log_text.tag_config("normal", foreground=self.colors["text_light"])
        self.log_text.tag_config("info", foreground=self.colors["text_muted"])
        self.log_text.tag_config("success", foreground=self.colors["success_green"])
        self.log_text.tag_config("warning", foreground=self.colors["warn_orange"])
        self.log_text.tag_config("error", foreground=self.colors["accent_red"])

    def toggle_title_entry(self):
        if self.auto_title_var.get():
            self.title_ent.configure(state="disabled")
            self.desc_ent.configure(state="disabled")
        else:
            self.title_ent.configure(state="normal")
            self.desc_ent.configure(state="normal")

    def browse_songs_file(self):
        filename = filedialog.askopenfilename(
            initialdir=".",
            title="Select Song List File",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            self.songs_file_var.set(filename)

    def browse_auth_file(self):
        filename = filedialog.askopenfilename(
            initialdir=".",
            title="Select Authentication JSON",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if filename:
            self.auth_file_var.set(filename)

    def write_console(self, text, tag="normal"):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def clear_console(self):
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")

    def open_playlist_in_browser(self):
        if self.playlist_url:
            webbrowser.open(self.playlist_url)

    def request_cancel(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_requested = True
            self.write_console("\n[GUI] Cancellation requested. Stopping after current song finishes...\n", "warning")
            self.cancel_btn.configure(state="disabled")

    def open_auth_assistant(self):
        # Open a secondary dialog
        assistant = tk.Toplevel(self)
        assistant.title("Authentication Assistant")
        assistant.geometry("600x550")
        assistant.configure(bg=self.colors["bg_dark"])
        assistant.transient(self)
        assistant.grab_set()
        
        lbl_style = ttk.Label(assistant, text="YouTube Music Authentication Assistant", style="Header.TLabel")
        lbl_style.pack(pady=10)
        
        instr_text = (
            "How to get authentication headers:\n"
            "1. Open YouTube Music (https://music.youtube.com) in Chrome/Firefox and log in.\n"
            "2. Open Developer Tools (press F12 or Ctrl+Shift+I) and head to the 'Network' tab.\n"
            "3. Refresh the page or click anything to trigger list items, then look for a request to 'browse' or 'search' or similar API calls.\n"
            "4. Right-click on that network request, select Copy -> Copy Request Headers (or raw request headers).\n"
            "5. Paste the entire block of headers into the text area below, then click Parse and Save."
        )
        ttk.Label(assistant, text=instr_text, justify="left", font=("Segoe UI", 9), foreground=self.colors["text_light"], wraplength=560).pack(pady=10, padx=15)
        
        textbox = ScrolledText(assistant, bg=self.colors["bg_card"], fg=self.colors["text_light"], insertbackground=self.colors["text_light"], height=15)
        textbox.pack(fill="both", expand=True, padx=15, pady=5)
        
        btn_frame = ttk.Frame(assistant)
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        def save_headers():
            raw_text = textbox.get(1.0, tk.END).strip()
            if not raw_text:
                messagebox.showerror("Error", "Please paste the request headers first.", parent=assistant)
                return
            
            try:
                headers = {}
                for line in raw_text.split('\n'):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    # Handle raw HTTP header lines like "Host: music.youtube.com"
                    if ':' in line_str:
                        parts = line_str.split(':', 1)
                        # Avoid saving pseudo-headers like :method, :path
                        key = parts[0].strip()
                        if key.startswith(':'):
                            continue
                        val = parts[1].strip()
                        headers[key] = val
                
                if not headers:
                    # Try to parse if it's already structured copy paste
                    # Check if it was pasted as a JSON
                    try:
                        headers = json.loads(raw_text)
                    except Exception:
                        pass
                
                if not headers or len(headers) < 3:
                    messagebox.showerror("Validation Failed", "Failed to detect request headers. Make sure you copy request headers from standard DevTools.", parent=assistant)
                    return

                try:
                    validate_auth_headers(headers)
                except ValueError as validation_error:
                    messagebox.showerror("Validation Failed", str(validation_error), parent=assistant)
                    return

                headers = sanitize_auth_headers(headers)
                
                # Save to selected Auth file
                target_file = self.auth_file_var.get()
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(headers, f, indent=4, ensure_ascii=False)
                
                messagebox.showinfo("Success", f"Authentication headers compiled and written to '{target_file}' successfully!", parent=assistant)
                assistant.destroy()
            except Exception as e:
                messagebox.showerror("Parsing Error", f"An unexpected error occurred: {e}", parent=assistant)
                
        ttk.Button(btn_frame, text="Parse headers & save to JSON", command=save_headers, style="Red.TButton").pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=assistant.destroy).pack(side="right")

    def start_processing(self):
        songs_file = self.songs_file_var.get()
        auth_file = self.auth_file_var.get()
        
        # Essential non-empty checks
        if not os.path.exists(songs_file):
            messagebox.showerror("Error", f"Songs file list does not exist: {songs_file}")
            return
        
        if not os.path.exists(auth_file):
            has_setup = messagebox.askyesno("Auth Missing", f"YouTube Music auth file '{auth_file}' was not found.\nWould you like to open the Headers assistant to configure it now?")
            if has_setup:
                self.open_auth_assistant()
            return
            
        # Reset UI element states
        self.clear_console()
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.songs_file_ent.configure(state="disabled")
        self.auth_file_ent.configure(state="disabled")
        self.playlist_btn.configure(state="disabled")
        
        self.stop_requested = False
        self.playlist_url = None
        
        # Load advanced params
        playlist_title = self.title_var.get().strip() if not self.auto_title_var.get() else None
        playlist_desc = self.desc_var.get().strip() if not self.auto_title_var.get() else None
        privacy_status = self.privacy_var.get().upper()
        allow_duplicates = self.duplicates_var.get()
        perfect_match = self.perfect_match_var.get()
        
        # Spin up safe background worker thread
        self.worker_thread = threading.Thread(
            target=self.run_background_task,
            args=(songs_file, auth_file, playlist_title, playlist_desc, privacy_status, allow_duplicates, perfect_match),
            daemon=True
        )
        self.worker_thread.start()

    def run_background_task(self, songs_file, auth_file, title, desc, privacy, allow_duplicates, perfect_match):
        """Threaded code that performs song additions and posts results to GUI queue."""
        log_queue = self.gui_queue
        
        # Hook system logs and redirect prints to GUI
        root_logger = logging.getLogger()
        gui_handler = QueueHandler(log_queue)
        gui_formatter = logging.Formatter('%(levelname)s - %(message)s')
        gui_handler.setFormatter(gui_formatter)
        gui_handler.setLevel(logging.INFO)
        root_logger.addHandler(gui_handler)
        
        sys.stdout = ThreadsafeConsoleInputRedirector(log_queue, "normal")
        sys.stderr = ThreadsafeConsoleInputRedirector(log_queue, "error")
        
        try:
            log_queue.put(("log", ("Starting Playlist Creation script...\n", "success")))
            
            # 1. Read song queries
            log_queue.put(("log", ("Reading song inquiries...\n", "normal")))
            song_queries = read_song_queries(songs_file)
            if not song_queries:
                log_queue.put(("log", (f"Error: No song queries found in '{songs_file}'\n", "error")))
                log_queue.put(("complete", {"success": False, "reason": "No songs in file"}))
                return
                
            total_songs = len(song_queries)
            log_queue.put(("update_stats", {"total": total_songs, "processed": 0, "added": 0, "duplicates": 0, "notfound": 0, "failed": 0}))
            
            # 2. Init API
            log_queue.put(("log", ("Initializing YTMusic API...\n", "normal")))
            try:
                # Initialize in isBackground/noninteractive mode since we are running headless-like in Python
                yt = initialize_ytmusic(auth_file, non_interactive=True)
            except Exception as e:
                log_queue.put(("log", (f"Authentication failure: {e}\n", "error")))
                log_queue.put(("complete", {"success": False, "reason": f"Auth failed: {str(e)}"}))
                return
                
            # 3. Create playlist
            log_queue.put(("log", ("Creating target playlist on YouTube Music...\n", "normal")))
            try:
                playlist_id, playlist_title = create_playlist(
                    yt,
                    privacy_status=privacy,
                    title=title,
                    description=desc,
                    non_interactive=True
                )
            except Exception as e:
                log_queue.put(("log", (f"Failed creating playlist: {e}\n", "error")))
                log_queue.put(("complete", {"success": False, "reason": f"Create playlist failed: {str(e)}"}))
                return
            
            playback_url = f"https://music.youtube.com/playlist?list={playlist_id}"
            log_queue.put(("playlist_created", playback_url))
            
            # 4. Cycle and add songs manually to capture detailed status updates
            from .ytmusic_api import search_song
            
            added_cnt = 0
            dup_cnt = 0
            notfound_cnt = 0
            failed_cnt = 0
            processed_cnt = 0
            cancelled = False
            
            unique_songs = set()
            start_time = datetime.datetime.now()
            
            for idx, query in enumerate(song_queries, start=1):
                if self.stop_requested:
                    cancelled = True
                    log_queue.put(("log", ("\nProcessing aborted by user.\n", "warning")))
                    break
                    
                log_queue.put(("log", (f"[{idx}/{total_songs}] Searching for search query: '{query}'\n", "normal")))
                
                try:
                    result = search_song(yt, query, perfect_match=perfect_match)
                except Exception as search_err:
                    log_queue.put(("log", (f"Search failure for '{query}': {search_err}\n", "error")))
                    failed_cnt += 1
                    processed_cnt += 1
                    self._send_realtime_stats(log_queue, total_songs, processed_cnt, added_cnt, dup_cnt, notfound_cnt, failed_cnt, start_time)
                    continue
                
                if not result:
                    notfound_cnt += 1
                    log_queue.put(("log", (f"Song not found for query '{query}' on YT Music\n", "error")))
                    processed_cnt += 1
                    self._send_realtime_stats(log_queue, total_songs, processed_cnt, added_cnt, dup_cnt, notfound_cnt, failed_cnt, start_time)
                    continue
                
                video_id = result.get('videoId')
                if not video_id:
                    failed_cnt += 1
                    log_queue.put(("log", (f"No playable video ID resolved for: {query}\n", "error")))
                    processed_cnt += 1
                    self._send_realtime_stats(log_queue, total_songs, processed_cnt, added_cnt, dup_cnt, notfound_cnt, failed_cnt, start_time)
                    continue
                
                # Check duplication & add item
                try:
                    status, unique_songs = add_item_to_playlist(
                        yt, playlist_id, video_id, query,
                        retries=0, allow_duplicates=allow_duplicates, unique_songs=unique_songs
                    )
                    
                    title_found = result.get('title', query)
                    artists = result.get('artists', [{}])
                    artist_found = artists[0].get('name', '') if artists else ''
                    
                    if status == "success":
                        added_cnt += 1
                        info_str = f"Added: '{title_found}' by {artist_found}" if artist_found else f"Added: '{title_found}'"
                        log_queue.put(("log", (f"{info_str}\n", "success")))
                    elif status == "duplicate":
                        dup_cnt += 1
                        log_queue.put(("log", (f"Duplicate skipped: '{query}'\n", "warning")))
                    else:
                        failed_cnt += 1
                        log_queue.put(("log", (f"Failed adding '{query}' to the playlist\n", "error")))
                        
                except Exception as e:
                    failed_cnt += 1
                    log_queue.put(("log", (f"Error during track addition '{query}': {e}\n", "error")))
                    
                processed_cnt += 1
                self._send_realtime_stats(log_queue, total_songs, processed_cnt, added_cnt, dup_cnt, notfound_cnt, failed_cnt, start_time)
            
            # Done adding
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            if cancelled:
                log_queue.put(("complete", {
                    "success": False,
                    "cancelled": True,
                    "added": added_cnt,
                    "duplicates": dup_cnt,
                    "notfound": notfound_cnt,
                    "failed": failed_cnt,
                    "processed": processed_cnt,
                    "total": total_songs,
                    "elapsed": elapsed,
                    "playlist_title": playlist_title,
                    "playlist_id": playlist_id,
                    "reason": "Playlist creation cancelled by user.",
                }))
                return

            log_queue.put(("complete", {
                "success": True, 
                "added": added_cnt, 
                "duplicates": dup_cnt, 
                "notfound": notfound_cnt, 
                "failed": failed_cnt,
                "elapsed": elapsed,
                "playlist_title": playlist_title,
                "playlist_id": playlist_id
            }))
            
        except BaseException as global_ex:
            log_queue.put(("log", (f"Fatal worker exception: {global_ex}\n", "error")))
            log_queue.put(("log", (traceback.format_exc(), "error")))
            log_queue.put(("complete", {"success": False, "reason": str(global_ex)}))
        finally:
            # Unhook redirectors safely
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            root_logger.removeHandler(gui_handler)

    def _send_realtime_stats(self, queue_obj, total, processed, added, duplicates, notfound, failed, start_time):
        elapsed = int((datetime.datetime.now() - start_time).total_seconds())
        queue_obj.put(("update_stats", {
            "total": total,
            "processed": processed,
            "added": added,
            "duplicates": duplicates,
            "notfound": notfound,
            "failed": failed,
            "elapsed": elapsed
        }))

    def poll_queue(self):
        """Periodically runs inside TK mainloop to pull and implement instructions from workers."""
        try:
            while True:
                msg_type, payload = self.gui_queue.get_nowait()
                if msg_type == "log":
                    text, tag = payload
                    self.write_console(text, tag)
                elif msg_type == "update_stats":
                    # Update counts labels nicely
                    total = payload.get("total", 0)
                    processed = payload.get("processed", 0)
                    added = payload.get("added", 0)
                    dup = payload.get("duplicates", 0)
                    notfound = payload.get("notfound", 0)
                    failed = payload.get("failed", 0)
                    elapsed = payload.get("elapsed", 0)
                    
                    self.progress_count_lbl.configure(text=f"{processed} / {total}")
                    self.stat_added_lbl.configure(text=f"{added}")
                    self.stat_dup_lbl.configure(text=f"{dup}")
                    self.stat_notfound_lbl.configure(text=f"{notfound}")
                    self.stat_failed_lbl.configure(text=f"{failed}")
                    self.stat_time_lbl.configure(text=f"{elapsed}s")
                    
                    # Update horizontal bar percentage and text
                    if total > 0:
                        pct = (processed / total) * 100
                        self.progress_bar["value"] = pct
                        self.progress_pct_lbl.configure(text=f"{int(pct)}% Complete")
                        self.progress_txt_lbl.configure(text=f"{processed} / {total} songs processed")
                elif msg_type == "playlist_created":
                    self.playlist_url = payload
                    self.playlist_btn.configure(state="normal")
                    self.write_console(f"Playlist target ready: {self.playlist_url}\n", "success")
                elif msg_type == "complete":
                    self.worker_thread = None
                    self.cancel_btn.configure(state="disabled")
                    self.start_btn.configure(state="normal")
                    self.songs_file_ent.configure(state="normal")
                    self.auth_file_ent.configure(state="normal")
                    
                    if payload.get("success", False):
                        p_title = payload.get("playlist_title", "Custom Playlist")
                        msg = (
                            f"Congratulations!\n"
                            f"Playlist '{p_title}' created successfully.\n"
                            f"Successfully Added: {payload.get('added')} songs.\n"
                            f"Skipped Duplicates: {payload.get('duplicates')} songs.\n"
                            f"Failed/Not Found: {payload.get('failed') + payload.get('notfound')} songs.\n\n"
                            f"Click 'Open YouTube Music Playlist' to load it."
                        )
                        messagebox.showinfo("Creation Completed", msg)
                    elif payload.get("cancelled", False):
                        p_title = payload.get("playlist_title", "Custom Playlist")
                        msg = (
                            f"Playlist '{p_title}' was cancelled before all songs were processed.\n"
                            f"Processed: {payload.get('processed', 0)} / {payload.get('total', 0)} songs.\n"
                            f"Successfully Added: {payload.get('added', 0)} songs.\n"
                            f"Skipped Duplicates: {payload.get('duplicates', 0)} songs.\n"
                            f"Failed/Not Found: {payload.get('failed', 0) + payload.get('notfound', 0)} songs."
                        )
                        messagebox.showinfo("Creation Cancelled", msg)
                    else:
                        reason = payload.get("reason", "Unknown internal error")
                        messagebox.showerror("Failed", f"Playlist processing ended incomplete:\n{reason}")
                        
                self.gui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            # Poll every 100ms
            self.after(100, self.poll_queue)


def launch_gui():
    """Entry point to launch the graphical dashboard."""
    app = YTMusicGUI()
    app.mainloop()
