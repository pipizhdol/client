# sarus_client/run_gui.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from gui.main_window import MainWindow
from gui.login_window import LoginWindow


def on_auth_success(client):
    """Колбэк из окна авторизации – передаём клиента в главное окно и показываем его."""
    main_app.set_client(client)
    root.deiconify()  # показать главное окно


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # скрываем до успешного входа

    main_app = MainWindow(root)

    # Запускаем окно авторизации поверх скрытого root
    login_window = LoginWindow(root, on_auth_success)

    root.mainloop()
