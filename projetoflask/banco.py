"""Tudo que fala com o banco SQLite fica AQUI (SQL puro, sem ORM).

Regras que valem para todas as funções:
  * Os valores vão sempre nos "?" e nunca dentro da string do SQL.
    Isso impede SQL injection.
  * Toda resenha guarda o usuario_id do dono, e as consultas de editar/excluir
    filtram por ele: ninguém mexe na resenha de outra pessoa.
"""
import sqlite3
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "instance"
CAMINHO = PASTA / "resenhas.db"


def conectar():
    con = sqlite3.connect(CAMINHO)
    con.row_factory = sqlite3.Row            # permite usar linha["titulo"]
    con.execute("PRAGMA foreign_keys = ON")  # o SQLite deixa desligado por padrão
    return con


def _consultar(sql, params=(), um=False):
    """SELECT: devolve uma linha (um=True) ou uma lista de linhas."""
    con = conectar()
    try:
        cursor = con.execute(sql, params)
        return cursor.fetchone() if um else cursor.fetchall()
    finally:
        con.close()


def _executar(sql, params=()):
    """INSERT / UPDATE / DELETE: devolve (id_inserido, linhas_afetadas)."""
    con = conectar()
    try:
        with con:  # confirma (commit) se der certo e desfaz (rollback) se der erro
            cursor = con.execute(sql, params)
            return cursor.lastrowid, cursor.rowcount
    finally:
        con.close()


def criar_tabelas():
    PASTA.mkdir(exist_ok=True)
    con = conectar()
    try:
        with con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome       TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    senha_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS resenhas (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL
                               REFERENCES usuarios(id) ON DELETE CASCADE,
                    titulo     TEXT NOT NULL,
                    genero     TEXT NOT NULL,
                    texto      TEXT NOT NULL,
                    criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
    finally:
        con.close()


# ---------------------------------------------------------------- usuários
def criar_usuario(nome, senha_hash):
    """Levanta sqlite3.IntegrityError se o nome já existir."""
    novo_id, _ = _executar(
        "INSERT INTO usuarios (nome, senha_hash) VALUES (?, ?)", (nome, senha_hash)
    )
    return novo_id


def buscar_usuario_por_nome(nome):
    return _consultar("SELECT * FROM usuarios WHERE nome = ?", (nome,), um=True)


# ------------------------------------------------------- resenhas (CRUD)
def criar_resenha(usuario_id, titulo, genero, texto):  # C - Create
    novo_id, _ = _executar(
        "INSERT INTO resenhas (usuario_id, titulo, genero, texto) VALUES (?, ?, ?, ?)",
        (usuario_id, titulo, genero, texto),
    )
    return novo_id


def listar_resenhas(usuario_id):  # R - Read (todas)
    return _consultar(
        "SELECT * FROM resenhas WHERE usuario_id = ? ORDER BY criado_em DESC, id DESC",
        (usuario_id,),
    )


def buscar_resenha(resenha_id, usuario_id):  # R - Read (uma)
    return _consultar(
        "SELECT * FROM resenhas WHERE id = ? AND usuario_id = ?",
        (resenha_id, usuario_id),
        um=True,
    )


def atualizar_resenha(resenha_id, usuario_id, titulo, genero, texto):  # U - Update
    _, afetadas = _executar(
        "UPDATE resenhas SET titulo = ?, genero = ?, texto = ? WHERE id = ? AND usuario_id = ?",
        (titulo, genero, texto, resenha_id, usuario_id),
    )
    return afetadas == 1


def excluir_resenha(resenha_id, usuario_id):  # D - Delete
    _, afetadas = _executar(
        "DELETE FROM resenhas WHERE id = ? AND usuario_id = ?", (resenha_id, usuario_id)
    )
    return afetadas == 1


def titulos_do_usuario(usuario_id):
    """Títulos já resenhados (para não indicar de novo um livro que a pessoa já leu)."""
    linhas = _consultar("SELECT titulo FROM resenhas WHERE usuario_id = ?", (usuario_id,))
    return [linha["titulo"] for linha in linhas]
