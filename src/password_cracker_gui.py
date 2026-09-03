#!/usr/bin/env python3
"""
------------------------------------------------------------
password_cracker_gui.py - lightweight GUI front end

Uses only tkinter (Python's standard-library GUI toolkit) - no
extra packages to install. Shares its attack logic with the CLI
via password_cracker_core.py, so keep all three files together in
the same folder.

Design notes:
    - The dictionary + brute-force attack runs on a background
    thread so the window never freezes, even on a long brute
    force. Tkinter widgets are only ever touched from the main
    thread; the worker thread only pushes strings onto queues,
    which the main thread polls on a timer.

    - The core logic only asks for confirmation on a password once
    it actually needs brute force (i.e. the dictionary attack
    already failed on it) - not for every password up front.
    Because that confirm() call happens on the worker thread, but
    messagebox dialogs are only safe on the main thread, the
    confirm callback puts a request on confirm_request_queue and
    then blocks on confirm_response_queue.get() until the main
    thread's poller shows the dialog and answers it.

    - Stop button sets a threading event that the core loop checks
    between guesses, so a running search can be cancelled instead
    of having to kill the whole program.
------------------------------------------------------------
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from password_cracker_core import (
    DEFAULT_DICTIONARY_PATH,
    PasswordInfo,
    run_attack,
    validate_password,
)

DONE_SENTINEL = "\0__ATTACK_DONE__\0"

# ---- Palette ----------------------------------------------------------
BG_APP = "#0d1117"
BG_CHROME = "#161b22"
BG_CARD = "#11161d"
BORDER = "#21262d"
BORDER_ACCENT = "#1f4d33"

TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_DIM = "#586069"

ACCENT = "#3fb950"
ACCENT_BRIGHT = "#56d364"
ACCENT_ACTIVE = "#2ea043"
ACCENT_DISABLED = "#215026"

DANGER = "#f85149"
DANGER_BG = "#2d1315"
DANGER_BG_ACTIVE = "#3d1a1c"
DANGER_DISABLED = "#4a2224"

LOG_BG = "#010409"
LOG_FG = "#c9d1d9"
LOG_SUCCESS = "#56d364"
LOG_WARN = "#e3b341"
LOG_ERROR = "#f85149"
LOG_INFO = "#79c0ff"
LOG_MUTED = "#6e7681"

TRAFFIC_DOTS = ("#ff5f56", "#ffbd2e", "#27c93f")

CURSOR_BLINK_MS = 530


def _pick_font(candidates: list[str], fallback: str) -> str:
    """Return the first font family from candidates that's actually
    installed, so the GUI looks right on Windows/Mac/Linux without
    guessing wrong and silently falling back to something generic."""
    available = set(tkfont.families())
    for name in candidates:
        if name in available:
            return name
    return fallback


def _ascii_banner(lines: list[str], padding: int = 2) -> str:
    """Build a box-drawn ASCII banner from lines of text, computing the
    box width from content rather than hand-counting characters, so it
    stays aligned no matter what the text says."""
    width = max(len(line) for line in lines) + padding * 2
    top = "\u250c" + "\u2500" * width + "\u2510"
    bottom = "\u2514" + "\u2500" * width + "\u2518"
    middle = []
    for line in lines:
        total_pad = width - len(line)
        left = total_pad // 2
        right = total_pad - left
        middle.append("\u2502" + " " * left + line + " " * right + "\u2502")
    return "\n".join([top, *middle, bottom])


class PasswordCrackerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("password_cracker.py")
        self._size_window()
        self.root.minsize(560, 560)
        self.root.configure(bg=BG_APP)

        self.mono_font = _pick_font(
            ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"], "TkFixedFont"
        )

        self.passwords: list[str] = []
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.confirm_request_queue: queue.Queue[tuple[str, int]] = queue.Queue()
        self.confirm_response_queue: queue.Queue[bool] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._cursor_on = True

        self._build_style()
        self._build_widgets()
        self._poll_log_queue()
        self._blink_cursor()

    # ---- Window sizing -------------------------------------------------------

    def _size_window(self) -> None:
        """Size the window relative to the actual screen instead of a fixed
        guess, so the log panel is visible by default without a manual
        resize, on small and large displays alike."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = max(620, min(760, int(screen_w * 0.5)))
        height = max(680, min(900, int(screen_h * 0.82)))

        x = (screen_w - width) // 2
        y = max(20, (screen_h - height) // 3)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ---- Style -------------------------------------------------------------

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TFrame", background=BG_APP)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("Chrome.TFrame", background=BG_CHROME)

        style.configure(
            "TLabel", background=BG_APP, foreground=TEXT_PRIMARY, font=(self.mono_font, 10)
        )
        style.configure(
            "Card.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY, font=(self.mono_font, 10)
        )
        style.configure(
            "Banner.TLabel",
            background=BG_APP,
            foreground=ACCENT_BRIGHT,
            font=(self.mono_font, 11),
        )
        style.configure(
            "Subheader.TLabel", background=BG_APP, foreground=TEXT_SECONDARY, font=(self.mono_font, 9)
        )
        style.configure(
            "SectionTitle.TLabel",
            background=BG_CARD,
            foreground=ACCENT,
            font=(self.mono_font, 9, "bold"),
        )
        style.configure(
            "Caption.TLabel",
            background=BG_CARD,
            foreground=TEXT_DIM,
            font=(self.mono_font, 8),
        )

        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#0d1117",
            font=(self.mono_font, 10, "bold"),
            padding=(16, 9),
            borderwidth=0,
            focuscolor=ACCENT,
        )
        style.map(
            "Accent.TButton",
            background=[("disabled", ACCENT_DISABLED), ("active", ACCENT_ACTIVE)],
            foreground=[("disabled", TEXT_DIM)],
        )

        style.configure(
            "Secondary.TButton",
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            font=(self.mono_font, 10),
            padding=(12, 8),
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            focuscolor=BORDER,
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#1c2128")],
            bordercolor=[("active", ACCENT)],
        )

        style.configure(
            "Danger.TButton",
            background=DANGER_BG,
            foreground=DANGER,
            font=(self.mono_font, 10, "bold"),
            padding=(14, 8),
            borderwidth=1,
            relief="solid",
            bordercolor="#5a2226",
            focuscolor=DANGER_BG,
        )
        style.map(
            "Danger.TButton",
            background=[("disabled", DANGER_BG), ("active", DANGER_BG_ACTIVE)],
            foreground=[("disabled", DANGER_DISABLED)],
        )

        style.configure(
            "TEntry",
            fieldbackground="#0d1117",
            foreground=TEXT_PRIMARY,
            insertcolor=ACCENT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
            font=(self.mono_font, 10),
        )
        style.map("TEntry", bordercolor=[("focus", ACCENT)])

        style.configure(
            "TCheckbutton",
            background=BG_CARD,
            foreground=TEXT_SECONDARY,
            font=(self.mono_font, 9),
        )
        style.map("TCheckbutton", background=[("active", BG_CARD)])

        style.configure(
            "Terminal.Horizontal.TProgressbar",
            troughcolor=BG_APP,
            background=ACCENT,
            bordercolor=BG_APP,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=6,
        )

    def _card(self, parent: tk.Widget, title: str) -> ttk.Frame:
        """A dark panel with a hairline border and a "$ section_name"
        style title - the basic building block the layout is made of."""
        outer = tk.Frame(parent, bg=BORDER_ACCENT)
        outer.pack(fill="x", pady=(0, 14))
        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        ttk.Label(card, text=f"$ {title}", style="SectionTitle.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        return card

    # ---- UI construction -----------------------------------------------

    def _build_widgets(self) -> None:
        # Decorative fake-terminal chrome bar (traffic-light dots + a
        # fake path) sitting under the real OS titlebar - purely cosmetic.
        chrome = tk.Frame(self.root, bg=BG_CHROME, height=34)
        chrome.pack(fill="x", side="top")
        chrome.pack_propagate(False)

        dots = tk.Frame(chrome, bg=BG_CHROME)
        dots.pack(side="left", padx=12)
        for color in TRAFFIC_DOTS:
            dot = tk.Canvas(dots, width=12, height=12, bg=BG_CHROME, highlightthickness=0)
            dot.create_oval(2, 2, 11, 11, fill=color, outline="")
            dot.pack(side="left", padx=3)

        tk.Label(
            chrome,
            text="guest@localhost: ~/password-cracker",
            bg=BG_CHROME,
            fg=TEXT_SECONDARY,
            font=(self.mono_font, 9),
        ).pack(side="left")

        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)

        # --- Header: ASCII banner + blinking prompt cursor ---
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))

        banner_text = _ascii_banner(["PASSWORD CRACK-TIME ESTIMATOR"])
        ttk.Label(
            header, text=banner_text, style="Banner.TLabel", justify="left"
        ).pack(anchor="w")

        prompt_row = ttk.Frame(outer)
        prompt_row.pack(fill="x", pady=(4, 16))
        tk.Label(
            prompt_row,
            text="guest@cracker:~$ dictionary attack, then brute force -",
            bg=BG_APP,
            fg=TEXT_SECONDARY,
            font=(self.mono_font, 9),
        ).pack(side="left")
        tk.Label(
            prompt_row,
            text=" runs locally",
            bg=BG_APP,
            fg=TEXT_SECONDARY,
            font=(self.mono_font, 9),
        ).pack(side="left")
        self.cursor_label = tk.Label(
            prompt_row, text="\u2588", bg=BG_APP, fg=ACCENT, font=(self.mono_font, 9)
        )
        self.cursor_label.pack(side="left", padx=(2, 0))

        # --- Passwords card ---
        pw_card = self._card(outer, "passwords_to_test")

        entry_row = ttk.Frame(pw_card, style="Card.TFrame")
        entry_row.pack(fill="x")

        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(entry_row, textvariable=self.password_var, show="*")
        self.password_entry.pack(side="left", fill="x", expand=True, ipady=2)
        self.password_entry.bind("<Return>", lambda _e: self._add_password())

        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            entry_row, text="show", variable=self.show_var, command=self._toggle_show
        ).pack(side="left", padx=(10, 10))

        ttk.Button(
            entry_row, text="[ + ADD ]", style="Accent.TButton", command=self._add_password
        ).pack(side="left")

        list_row = ttk.Frame(pw_card, style="Card.TFrame")
        list_row.pack(fill="x", pady=(12, 0))

        list_border = tk.Frame(list_row, bg=BORDER)
        list_border.pack(side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(
            list_border,
            height=5,
            bg="#0d1117",
            fg=TEXT_PRIMARY,
            font=(self.mono_font, 10),
            borderwidth=0,
            highlightthickness=0,
            selectbackground=ACCENT,
            selectforeground="#0d1117",
            activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True, padx=1, pady=1)

        ttk.Button(
            list_row, text="[ REMOVE ]", style="Secondary.TButton", command=self._remove_selected
        ).pack(side="left", padx=(10, 0), anchor="n")

        # --- Wordlist card ---
        dict_card = self._card(outer, "wordlist_path")
        dict_row = ttk.Frame(dict_card, style="Card.TFrame")
        dict_row.pack(fill="x")

        self.dict_path_var = tk.StringVar(value=str(DEFAULT_DICTIONARY_PATH))
        ttk.Entry(dict_row, textvariable=self.dict_path_var).pack(
            side="left", fill="x", expand=True, ipady=2
        )
        ttk.Button(
            dict_row, text="[ BROWSE ]", style="Secondary.TButton", command=self._browse_dictionary
        ).pack(side="left", padx=(10, 0))

        ttk.Label(
            dict_card,
            text="# auto-detected next to this program - works on any machine, "
            "no path to edit.",
            style="Caption.TLabel",
            wraplength=520,
        ).pack(anchor="w", pady=(6, 0))

        # --- Controls row ---
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))

        self.start_button = ttk.Button(
            controls, text="[ \u25b6 START ]", style="Accent.TButton", command=self._start_attack
        )
        self.start_button.pack(side="left")

        self.stop_button = ttk.Button(
            controls,
            text="[ \u25a0 STOP ]",
            style="Danger.TButton",
            command=self._stop_attack,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        ttk.Button(
            controls, text="[ CLEAR_LOG ]", style="Secondary.TButton", command=self._clear_log
        ).pack(side="right")

        self.progress = ttk.Progressbar(
            outer, mode="indeterminate", style="Terminal.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", pady=(0, 14))

        # --- Log card ---
        log_outer = tk.Frame(outer, bg=BORDER_ACCENT)
        log_outer.pack(fill="both", expand=True)
        log_card = tk.Frame(log_outer, bg=LOG_BG)
        log_card.pack(fill="both", expand=True, padx=1, pady=1)

        log_header = tk.Frame(log_card, bg=LOG_BG)
        log_header.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(
            log_header,
            text="$ tail -f activity.log",
            bg=LOG_BG,
            fg=ACCENT,
            font=(self.mono_font, 9, "bold"),
        ).pack(side="left")

        text_frame = tk.Frame(log_card, bg=LOG_BG)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.log_widget = tk.Text(
            text_frame,
            state="disabled",
            wrap="word",
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            selectbackground="#1f2937",
            font=(self.mono_font, 9),
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=4,
        )
        log_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_widget.yview)
        self.log_widget.configure(yscrollcommand=log_scroll.set)
        self.log_widget.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log_widget.tag_configure("success", foreground=LOG_SUCCESS)
        self.log_widget.tag_configure("warn", foreground=LOG_WARN)
        self.log_widget.tag_configure("error", foreground=LOG_ERROR)
        self.log_widget.tag_configure("info", foreground=LOG_INFO)
        self.log_widget.tag_configure("muted", foreground=LOG_MUTED)

    # ---- Decorative blinking cursor -----------------------------------------

    def _blink_cursor(self) -> None:
        self._cursor_on = not self._cursor_on
        self.cursor_label.configure(fg=ACCENT if self._cursor_on else BG_APP)
        self.root.after(CURSOR_BLINK_MS, self._blink_cursor)

    # ---- Password list management -----------------------------------------

    def _toggle_show(self) -> None:
        self.password_entry.configure(show="" if self.show_var.get() else "*")
        self._refresh_listbox()

    def _refresh_listbox(self) -> None:
        """Rebuild the list display from self.passwords. Entries are
        labeled "password_1", "password_2", etc. so they're distinguishable
        at a glance - same-length passwords used to render as identical
        rows of dots with no way to tell them apart. When "show" is
        checked, the actual password is shown alongside its number."""
        show = self.show_var.get()
        self.listbox.delete(0, "end")
        for i, pw in enumerate(self.passwords, start=1):
            label = f"  password_{i}: {pw}" if show else f"  password_{i}"
            self.listbox.insert("end", label)

    def _add_password(self) -> None:
        pw = self.password_var.get().strip()
        if not validate_password(pw):
            messagebox.showerror(
                "Invalid password",
                "Password must be non-empty and use only letters, digits, "
                "and !@#$*_",
            )
            return
        self.passwords.append(pw)
        self._refresh_listbox()
        self.password_var.set("")
        self.password_entry.focus_set()

    def _remove_selected(self) -> None:
        for index in reversed(self.listbox.curselection()):
            del self.passwords[index]
        self._refresh_listbox()

    def _browse_dictionary(self) -> None:
        path = filedialog.askopenfilename(title="Select wordlist file")
        if path:
            self.dict_path_var.set(path)

    def _clear_log(self) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

    # ---- Logging (thread-safe via queue) -----------------------------------

    def _log(self, message: str) -> None:
        # Called from the worker thread - never touch widgets here directly.
        self.log_queue.put(message)

    @staticmethod
    def _classify(message: str) -> str:
        """Pick a log color by message content - purely cosmetic, doesn't
        affect any logic, just makes the log easier to scan at a glance."""
        lower = message.lower()
        if "was not cracked" in lower or "skip" in lower or "too long" in lower:
            return "warn"
        if "was cracked" in lower:
            return "success"
        if "error" in lower or "cancelled" in lower:
            return "error"
        if lower.startswith(("running ", "starting", "dictionary attack complete", "attempts so far")):
            return "info"
        return "muted"

    def _poll_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == DONE_SENTINEL:
                    self._on_attack_finished()
                    continue
                self.log_widget.configure(state="normal")
                self.log_widget.insert("end", "> " + message + "\n", self._classify(message))
                self.log_widget.see("end")
                self.log_widget.configure(state="disabled")
        except queue.Empty:
            pass

        # Handle any pending "this brute force could take a long time"
        # confirmation requests from the worker thread. Only reaches here
        # once the dictionary attack has already failed on that password -
        # showing the dialog on the main thread is safe.
        try:
            while True:
                pw, keyspace = self.confirm_request_queue.get_nowait()
                proceed = messagebox.askyesno(
                    "Large search",
                    f"The dictionary attack didn't find '{'*' * len(pw)}' "
                    f"({len(pw)} characters). Brute forcing it could take up "
                    f"to {keyspace:,} guesses and may run for a very long "
                    "time.\n\nContinue with brute force for it?",
                )
                self.confirm_response_queue.put(proceed)
        except queue.Empty:
            pass

        self.root.after(100, self._poll_log_queue)

    # ---- Attack control -----------------------------------------------------

    def _start_attack(self) -> None:
        if not self.passwords:
            messagebox.showwarning("No passwords", "Add at least one password to test first.")
            return

        dictionary_path = Path(self.dict_path_var.get().strip() or str(DEFAULT_DICTIONARY_PATH))
        password_infos = [PasswordInfo(password=pw) for pw in self.passwords]

        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress.start(12)
        self._log(f"starting run against {len(password_infos)} password(s)...")

        def confirm(pw: str, keyspace: int) -> bool:
            # Runs on the worker thread: hand off to the main thread via
            # the queues above and block until it answers.
            self.confirm_request_queue.put((pw, keyspace))
            return self.confirm_response_queue.get()

        def worker() -> None:
            try:
                run_attack(
                    password_infos,
                    dictionary_path,
                    log=self._log,
                    confirm=confirm,
                    should_stop=self.stop_event.is_set,
                )
            except Exception as exc:  # keep the GUI alive even on a surprise error
                self._log(f"error: {exc}")
            finally:
                self.log_queue.put(DONE_SENTINEL)

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _stop_attack(self) -> None:
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self._log("stop requested - finishing current guess...")

    def _on_attack_finished(self) -> None:
        self.progress.stop()
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    PasswordCrackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()