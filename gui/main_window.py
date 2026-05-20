# sarus_client/gui/main_window.py
import os
import queue
import sys
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.mdb_tab import MdbTab


class MainWindow:
    """Главное окно приложения (только импорт из MDB)."""

    def __init__(self, root):
        self.root = root
        self.root.title("Конвертер ЭРИ в САРУС")
        self.root.geometry("800x650")
        self.root.resizable(True, True)

        self.queue = queue.Queue()
        self.client = None

        self.stop_btn = None

        self.create_widgets()
        self.update_log()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Вкладка импорта (занимает всё свободное пространство после лога)
        self.mdb_tab = MdbTab(main_frame, self)
        self.mdb_tab.grid(row=0, column=0, columnspan=3, sticky=tk.W + tk.E, pady=5)

        # Кнопка импорта
        self.action_btn = ttk.Button(main_frame, text="Импортировать",
                                     command=self.on_action, state=tk.DISABLED)
        self.action_btn.grid(row=1, column=1, pady=10)

        # Кнопка остановки импорта (изначально неактивна)
        self.stop_btn = ttk.Button(main_frame, text="Остановить импорт",
                                   command=self.on_stop, state=tk.DISABLED)
        self.stop_btn.grid(row=1, column=2, padx=5, pady=10)

        # Лог
        ttk.Label(main_frame, text="Лог:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.log_text = tk.Text(main_frame, width=80, height=20)
        self.log_text.grid(row=2, column=1, columnspan=2, pady=5, sticky=tk.NSEW)
        self.log_text.bind("<Key>", lambda e: "break")
        self.log_text.bind("<Button-3>", self.show_copy_menu)

        def copy_text(event=None):
            try:
                self.log_text.clipboard_clear()
                text = self.log_text.get("sel.first", "sel.last")
                self.log_text.clipboard_append(text)
            except tk.TclError:
                pass

        self.log_text.bind("<Control-c>", copy_text)
        self.log_text.bind("<Control-C>", copy_text)

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=1, pady=5, sticky=tk.EW)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def show_copy_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Копировать", command=self.copy_selection)
        menu.post(event.x_root, event.y_root)

    def copy_selection(self):
        try:
            self.log_text.clipboard_clear()
            text = self.log_text.get("sel.first", "sel.last")
            self.log_text.clipboard_append(text)
        except tk.TclError:
            pass

    def set_client(self, client):
        """Вызывается после успешной авторизации из LoginWindow."""
        self.client = client
        self.action_btn.config(state=tk.NORMAL)
        self.mdb_tab.set_client(client)
        self.log(f"✅ Подключено к {client.base_url}")

    def on_action(self):
        if not self.client:
            messagebox.showwarning("Внимание", "Сначала авторизуйтесь")
            return
        self.mdb_tab.start_import()

    def log(self, message):
        self.root.after(0, self._append_log, f"{message}\n")

    def _append_log(self, msg):
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)

    def start_progress(self):
        self.progress.start()

    def stop_progress(self):
        self.progress.stop()

    def enable_action_button(self):
        self.action_btn.config(state=tk.NORMAL)

    def disable_action_button(self):
        self.action_btn.config(state=tk.DISABLED)

    def on_stop(self):
        """Вызывается при нажатии кнопки «Остановить импорт»."""
        if self.mdb_tab:
            self.mdb_tab.stop_import()

    def enable_action_button(self):
        self.action_btn.config(state=tk.NORMAL)

    def disable_action_button(self):
        self.action_btn.config(state=tk.DISABLED)

    def enable_stop_button(self):
        self.stop_btn.config(state=tk.NORMAL)

    def disable_stop_button(self):
        self.stop_btn.config(state=tk.DISABLED)

    def update_log(self):
        while True:
            try:
                msg = self.queue.get_nowait()
                self._append_log(msg)
            except queue.Empty:
                break
        self.root.after(100, self.update_log)
