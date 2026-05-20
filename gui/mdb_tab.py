# sarus_client/gui/mdb_tab.py
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.eri_importer import EriImporter
from mdb_reader import get_table_names


class MdbTab(ttk.Frame):
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.client = None
        self.current_mdb_path = None
        self.base_path = None          # вычисляется автоматически при выборе .mdb
        self.datasets_list = []        # список справочников [{id, name}]
        self.create_missing_var = tk.BooleanVar(value=False)   # ← ДОБАВЛЕНО
        self.create_params_var = tk.BooleanVar(value=False)
        self.stop_event = threading.Event()
        self.create_widgets()

    def create_widgets(self):
        # --- Справочник ЭРИ (загружается после авторизации) ---
        ttk.Label(self, text="Справочник ЭРИ:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.dataset_combo = ttk.Combobox(self, state="disabled", width=40)
        self.dataset_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # --- Файл .mdb ---
        ttk.Label(self, text="Файл .mdb:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mdb_path_entry = ttk.Entry(self, width=50)
        self.mdb_path_entry.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Button(self, text="Обзор...", command=self.browse_mdb).grid(row=1, column=2, padx=5)

        # --- Таблица (автозаполнение при выборе .mdb) ---
        ttk.Label(self, text="Таблица:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.table_combo = ttk.Combobox(self, state="readonly", width=40)
        self.table_combo.grid(row=2, column=1, sticky=tk.W, padx=5)


        # Чекбокс для параметров (новый)
        self.create_params_check = ttk.Checkbutton(
            self, text="Создавать отсутствующие параметры",
            variable=self.create_params_var
        )
        self.create_params_check.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=2)

    def set_client(self, client):
        self.client = client
        self.load_datasets()   # автоматически загружаем список справочников

    def browse_mdb(self):
        filename = filedialog.askopenfilename(filetypes=[("Access files", "*.mdb;*.accdb")])
        if filename:
            self.mdb_path_entry.delete(0, tk.END)
            self.mdb_path_entry.insert(0, filename)
            self.current_mdb_path = filename

            # Автоматически определяем базовую папку (родитель папки Mdb)
            self.base_path = self._find_base_path(filename)
            if self.base_path is None:
                self.main_window.log("⚠️ Не удалось определить базовую папку (не найдена папка 'Mdb' в пути)")
            else:
                self.main_window.log(f"Базовая папка: {self.base_path}")

            # Сразу загружаем список таблиц
            self.load_table_list()

    def _find_base_path(self, mdb_path):
        """Поднимается по дереву каталогов, пока не найдёт папку с именем 'Mdb',
        и возвращает её родительский каталог. Если не найдено – None."""
        current = os.path.dirname(mdb_path)
        while True:
            if os.path.basename(current).lower() == "mdb":
                return os.path.dirname(current)
            parent = os.path.dirname(current)
            if parent == current:      # достигнут корень
                break
            current = parent
        return None

    def load_datasets(self):
        self.dataset_combo.config(state="disabled")
        self.dataset_combo.set("Загрузка...")
        threading.Thread(target=self._load_datasets_task, daemon=True).start()

    def _load_datasets_task(self):
        try:
            datasets = self.client.get_eri_datasets_list()
            self.main_window.root.after(0, self._update_datasets, datasets)
        except Exception as e:
            self.main_window.log(f"Ошибка загрузки справочников: {e}")
            self.main_window.root.after(0, self._update_datasets, [])

    def _update_datasets(self, datasets):
        self.datasets_list = datasets
        names = [d["name"] for d in datasets]
        self.dataset_combo['values'] = names
        if names:
            self.dataset_combo.current(0)
        self.dataset_combo.config(state="readonly")
        self.main_window.log(f"Загружено справочников: {len(datasets)}")

    def load_table_list(self):
        mdb_path = self.mdb_path_entry.get().strip()
        if not mdb_path:
            return
        self.table_combo.config(state="disabled")
        threading.Thread(target=self._load_tables_task, args=(mdb_path,), daemon=True).start()

    def _load_tables_task(self, mdb_path):
        try:
            tables = get_table_names(mdb_path)
            self.main_window.root.after(0, self._update_table_combo, tables)
            self.main_window.log(f"Найдено таблиц: {len(tables)}")
        except Exception as e:
            self.main_window.log(f"Ошибка чтения таблиц: {e}")
            self.main_window.root.after(0, lambda: self.table_combo.config(state="readonly"))
        else:
            self.main_window.root.after(0, lambda: self.table_combo.config(state="readonly"))

    def _update_table_combo(self, tables):
        self.table_combo['values'] = tables
        if tables:
            self.table_combo.current(0)

    def start_import(self):
        if not self.client:
            messagebox.showwarning("Внимание", "Сначала авторизуйтесь")
            return

        selected_idx = self.dataset_combo.current()
        if selected_idx < 0 or not self.datasets_list:
            messagebox.showerror("Ошибка", "Выберите справочник ЭРИ")
            return
        eri_dataset_id = self.datasets_list[selected_idx]["id"]

        mdb_path = self.mdb_path_entry.get().strip()
        table = self.table_combo.get()
        base_path = self.base_path

        if not mdb_path or not table:
            messagebox.showerror("Ошибка", "Укажите .mdb и выберите таблицу")
            return
        if not base_path:
            messagebox.showerror("Ошибка", "Базовая папка не определена. Выберите .mdb, лежащий в папке Mdb.")
            return

        # Сброс флага остановки и подготовка кнопок
        self.stop_event.clear()
        self.main_window.disable_action_button()
        self.main_window.enable_stop_button()
        self.main_window.start_progress()

        create_missing = self.create_missing_var.get()
        create_params = self.create_params_var.get()

        threading.Thread(
            target=self._import_task,
            args=(eri_dataset_id, mdb_path, table, base_path, create_missing, create_params, self.stop_event),
            daemon=True
        ).start()

    def stop_import(self):
        """Устанавливает флаг остановки, поток сам завершится."""
        self.stop_event.set()
        self.main_window.log("⏹ Получен запрос на остановку импорта...")

    def _import_task(self, eri_dataset_id, mdb_path, table, base_path,
                     create_missing_classes, create_missing_params, stop_event):
        try:
            # Получаем имя справочника из выпадающего списка
            selected_name = self.dataset_combo.get()
            self.main_window.log("Получение метаданных справочника ЭРИ...")
            metadata = self.client.get_eri_metadata(eri_dataset_id)
            self.main_window.log("Метаданные получены")
            importer = EriImporter(self.client, eri_dataset_id, selected_name, metadata,
                                   log_callback=self.main_window.log)
            importer.import_from_mdb(
                mdb_path, table, base_path,
                create_missing_classes=create_missing_classes,
                create_missing_params=create_missing_params,
                stop_event=stop_event
            )
        except Exception as e:
            self.main_window.log(f"Критическая ошибка: {e}")
        finally:
            # Возвращаем интерфейс в исходное состояние
            self.main_window.root.after(0, self._import_finished)

    def _import_finished(self):
        self.main_window.stop_progress()
        self.main_window.enable_action_button()
        self.main_window.disable_stop_button()
        self.main_window.log("=== Импорт завершён ===")