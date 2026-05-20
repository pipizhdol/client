# sarus_client/gui/login_window.py
import hashlib
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from config import default_config
from core.client import SarusClient


class LoginWindow(tk.Toplevel):
    """Окно авторизации: сервер, логин, пароль (пароль хешируется MD5 перед отправкой)."""

    def __init__(self, parent, on_success_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_success_callback = on_success_callback
        self.title("Авторизация в САРУС")
        self.geometry("400x220")
        self.resizable(False, False)
        self.grab_set()  # модальное окно
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Сервер
        ttk.Label(frame, text="Адрес сервера:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.server_var = tk.StringVar(value=default_config.base_url.replace("http://", "").replace("/v1", ""))
        server_entry = ttk.Entry(frame, textvariable=self.server_var, width=30)
        server_entry.grid(row=0, column=1, pady=5, padx=5)

        # Логин
        ttk.Label(frame, text="Логин:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.login_var = tk.StringVar(value=default_config.login)
        login_entry = ttk.Entry(frame, textvariable=self.login_var, width=30)
        login_entry.grid(row=1, column=1, pady=5, padx=5)

        # Пароль
        ttk.Label(frame, text="Пароль:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=self.password_var, width=30, show="*")
        password_entry.grid(row=2, column=1, pady=5, padx=5)

        # Кнопки
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="Авторизоваться", command=self.start_auth).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self._on_close).pack(side=tk.RIGHT, padx=5)

        # Индикатор прогресса (скрыт)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self.progress.grid_remove()

    def start_auth(self):
        server = self.server_var.get().strip()
        login = self.login_var.get().strip()
        password = self.password_var.get()  # не убираем пробелы, пароль может содержать их

        if not server or not login:
            messagebox.showerror("Ошибка", "Заполните адрес сервера и логин", parent=self)
            return

        self._set_ui_state("disabled")
        self.progress.grid()
        self.progress.start()

        threading.Thread(target=self._auth_task, args=(server, login, password), daemon=True).start()

    def _auth_task(self, server, login, password):
        md5_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
        try:
            client = SarusClient(server=server)
            client.authenticate(login=login, password=md5_hash)
            # Передаём клиент напрямую в after, без лямбды
            self.after(0, self._auth_success, client)
        except Exception as ex:
            # То же самое с сообщением об ошибке
            self.after(0, self._auth_failed, str(ex))

    def _auth_success(self, client):
        self.progress.stop()
        self.progress.grid_remove()
        self.on_success_callback(client)
        self.destroy()

    def _auth_failed(self, error_msg):
        self.progress.stop()
        self.progress.grid_remove()
        self._set_ui_state("normal")
        messagebox.showerror("Ошибка авторизации", f"Не удалось войти:\n{error_msg}", parent=self)

    def _set_ui_state(self, state):
        for child in self.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    def _on_close(self):
        # При закрытии окна авторизации — завершаем программу
        self.parent.destroy()
