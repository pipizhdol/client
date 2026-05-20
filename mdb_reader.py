# sarus_client/mdb_reader.py
import pyodbc


def get_table_names(mdb_path):
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=' + mdb_path
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        tables = cursor.tables()
        table_names = [table.table_name for table in tables if table.table_type == 'TABLE']
        conn.close()
        return table_names
    except Exception as e:
        raise Exception(f"Ошибка подключения к .mdb: {e}")


def read_table_data(mdb_path, table_name):
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=' + mdb_path
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM [{table_name}]")
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        conn.close()
        return columns, rows
    except Exception as e:
        raise Exception(f"Ошибка чтения таблицы {table_name}: {e}")
