import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import DatabaseConnection


class UsuarioJaExiste(Exception):
    """Levantada quando o username já está cadastrado (o controller não precisa conhecer sqlite3)."""


class Usuario:
    def __init__(self, username, senha_hash="", id=None):
        self.id = id
        self.username = username
        self.senha_hash = senha_hash

    # ---- senha (nunca em texto puro) ----
    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    # ---- persistência ----
    def salvar(self):
        try:
            with DatabaseConnection() as db:
                db.cursor.execute(
                    "INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)",
                    (self.username, self.senha_hash),
                )
                self.id = db.cursor.lastrowid
        except sqlite3.IntegrityError:
            raise UsuarioJaExiste(self.username)
        return self.id

    @classmethod
    def _de_linha(cls, linha):
        return cls(id=linha["id"], username=linha["username"], senha_hash=linha["senha_hash"])

    @classmethod
    def buscar_por_id(cls, usuario_id):
        with DatabaseConnection() as db:
            db.cursor.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
            linha = db.cursor.fetchone()
        return cls._de_linha(linha) if linha else None

    @classmethod
    def buscar_por_username(cls, username):
        with DatabaseConnection() as db:
            db.cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
            linha = db.cursor.fetchone()
        return cls._de_linha(linha) if linha else None
