import sqlite3
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "instance"
CAMINHO = PASTA / "resenhas.db"

class ConexaoBD:
    def __enter__(self):
        PASTA.mkdir(exist_ok=True)
        self.conexao = sqlite3.connect(CAMINHO)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.execute("PRAGMA foreign_keys = ON")
        return self.conexao

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conexao:
            if exc_type is None:
                self.conexao.commit()
            else:
                self.conexao.rollback()
            self.conexao.close()

def criar_tabelas():
    with ConexaoBD() as bd:
        bd.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nome       TEXT NOT NULL UNIQUE COLLATE NOCASE,
                senha_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS resenhas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                titulo     TEXT NOT NULL,
                genero     TEXT NOT NULL,
                texto      TEXT NOT NULL,
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

class Usuario:
    def __init__(self, nome, senha_hash, id=None):
        self.id = id
        self.nome = nome
        self.senha_hash = senha_hash

    def guardar(self):
        with ConexaoBD() as bd:
            cursor = bd.execute("INSERT INTO usuarios (nome, senha_hash) VALUES (?, ?)", (self.nome, self.senha_hash))
            self.id = cursor.lastrowid
        return self.id

    @classmethod
    def buscar_por_nome(cls, nome):
        with ConexaoBD() as bd:
            linha = bd.execute("SELECT * FROM usuarios WHERE nome = ?", (nome,)).fetchone()
            if linha:
                return cls(id=linha["id"], nome=linha["nome"], senha_hash=linha["senha_hash"])
            return None

class Resenha:
    def __init__(self, usuario_id, titulo, genero, texto, id=None, criado_em=None):
        self.id = id
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.genero = genero
        self.texto = texto
        self.criado_em = criado_em

    def guardar(self):
        with ConexaoBD() as bd:
            if self.id is None:
                cursor = bd.execute(
                    "INSERT INTO resenhas (usuario_id, titulo, genero, texto) VALUES (?, ?, ?, ?)",
                    (self.usuario_id, self.titulo, self.genero, self.texto)
                )
                self.id = cursor.lastrowid
            else:
                bd.execute(
                    "UPDATE resenhas SET titulo = ?, genero = ?, texto = ? WHERE id = ? AND usuario_id = ?",
                    (self.titulo, self.genero, self.texto, self.id, self.usuario_id)
                )
        return self.id

    @classmethod
    def listar_do_usuario(cls, usuario_id):
        with ConexaoBD() as bd:
            linhas = bd.execute("SELECT * FROM resenhas WHERE usuario_id = ? ORDER BY criado_em DESC, id DESC", (usuario_id,)).fetchall()
            return [cls(**dict(linha)) for linha in linhas]

    @classmethod
    def buscar(cls, resenha_id, usuario_id):
        with ConexaoBD() as bd:
            linha = bd.execute("SELECT * FROM resenhas WHERE id = ? AND usuario_id = ?", (resenha_id, usuario_id)).fetchone()
            if linha:
                return cls(**dict(linha))
            return None

    @classmethod
    def apagar(cls, resenha_id, usuario_id):
        with ConexaoBD() as bd:
            cursor = bd.execute("DELETE FROM resenhas WHERE id = ? AND usuario_id = ?", (resenha_id, usuario_id))
            return cursor.rowcount > 0

    @classmethod
    def titulos_do_usuario(cls, usuario_id):
        with ConexaoBD() as bd:
            linhas = bd.execute("SELECT titulo FROM resenhas WHERE usuario_id = ?", (usuario_id,)).fetchall()
            return [linha["titulo"] for linha in linhas]