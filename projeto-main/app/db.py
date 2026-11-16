"""Gerenciador de contexto do banco (padrão obrigatório da Aula 15).

Uso nos Models:
    with DatabaseConnection() as db:
        db.cursor.execute("SELECT ... WHERE usuario_id = ?", (usuario_id,))
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# BANCO_DB é opcional: os testes usam para apontar para um banco temporário.
DB_PATH = os.environ.get("BANCO_DB") or os.path.join(BASE_DIR, "banco_dados.db")


class DatabaseConnection:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # acesso às colunas pelo nome: row['id']
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")  # ativa chaves estrangeiras
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()
