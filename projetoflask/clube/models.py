import math
import os
import sqlite3
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "instance"
# RESENHAS_DB permite apontar para outro banco (os testes usam isso para não tocar nos seus dados).
CAMINHO = Path(os.environ["RESENHAS_DB"]) if os.environ.get("RESENHAS_DB") else PASTA / "resenhas.db"

LIMITE_RESENHAS_POR_HORA = 10


class LimiteDeResenhas(Exception):
    """Levantada quando a pessoa já criou resenhas demais na última hora."""

    def __init__(self, minutos):
        super().__init__(f"Limite de {LIMITE_RESENHAS_POR_HORA} resenhas por hora atingido.")
        self.minutos = minutos


class ConexaoBD:
    def __enter__(self):
        CAMINHO.parent.mkdir(parents=True, exist_ok=True)
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
                nota       INTEGER CHECK (nota BETWEEN 1 AND 5),
                texto      TEXT NOT NULL,
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            -- Uma linha para cada resenha criada. Serve só para o limite por hora e fica
            -- separada de "resenhas" de propósito: apagar uma resenha não devolve a "vaga".
            CREATE TABLE IF NOT EXISTS registro_criacoes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_registro_criacoes
                ON registro_criacoes (usuario_id, criado_em);
            """
        )
        _migrar(bd)


def _migrar(bd):
    """Atualiza bancos criados por versões anteriores (sem a coluna 'nota')."""
    colunas = [coluna["name"] for coluna in bd.execute("PRAGMA table_info(resenhas)")]
    if "nota" not in colunas:
        # Fica NULL nas resenhas antigas ("sem nota"): inventar uma nota seria falsear o dado.
        bd.execute("ALTER TABLE resenhas ADD COLUMN nota INTEGER CHECK (nota BETWEEN 1 AND 5)")


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
    def __init__(self, usuario_id, titulo, genero, texto, nota=None, id=None, criado_em=None):
        self.id = id
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.genero = genero
        self.nota = nota
        self.texto = texto
        self.criado_em = criado_em

    def guardar(self):
        """INSERT se a resenha é nova, UPDATE se já existe. (Rotas novas usam criar_com_limite.)"""
        with ConexaoBD() as bd:
            if self.id is None:
                cursor = bd.execute(
                    "INSERT INTO resenhas (usuario_id, titulo, genero, nota, texto) VALUES (?, ?, ?, ?, ?)",
                    (self.usuario_id, self.titulo, self.genero, self.nota, self.texto)
                )
                self.id = cursor.lastrowid
            else:
                bd.execute(
                    "UPDATE resenhas SET titulo = ?, genero = ?, nota = ?, texto = ? WHERE id = ? AND usuario_id = ?",
                    (self.titulo, self.genero, self.nota, self.texto, self.id, self.usuario_id)
                )
        return self.id

    @classmethod
    def criar_com_limite(cls, usuario_id, titulo, genero, nota, texto):
        """Cria a resenha respeitando o limite por hora. Levanta LimiteDeResenhas se estourou."""
        with ConexaoBD() as bd:
            # BEGIN IMMEDIATE trava as escritas: "conferir o limite" e "inserir" viram uma
            # operação indivisível, então duas requisições simultâneas não furam o limite.
            bd.execute("BEGIN IMMEDIATE")
            bd.execute("DELETE FROM registro_criacoes WHERE criado_em <= datetime('now', '-1 hour')")
            total = bd.execute(
                "SELECT COUNT(*) FROM registro_criacoes WHERE usuario_id = ?", (usuario_id,)
            ).fetchone()[0]
            if total >= LIMITE_RESENHAS_POR_HORA:
                # Uma vaga abre quando a criação mais antiga completa 1 hora.
                segundos = bd.execute(
                    """SELECT CAST((julianday(criado_em, '+1 hour') - julianday('now')) * 86400 AS INTEGER)
                         FROM registro_criacoes WHERE usuario_id = ?
                        ORDER BY criado_em ASC, id ASC LIMIT 1 OFFSET ?""",
                    (usuario_id, total - LIMITE_RESENHAS_POR_HORA),
                ).fetchone()[0]
                raise LimiteDeResenhas(max(1, math.ceil(segundos / 60)))
            cursor = bd.execute(
                "INSERT INTO resenhas (usuario_id, titulo, genero, nota, texto) VALUES (?, ?, ?, ?, ?)",
                (usuario_id, titulo, genero, nota, texto),
            )
            bd.execute("INSERT INTO registro_criacoes (usuario_id) VALUES (?)", (usuario_id,))
            return cursor.lastrowid

    @classmethod
    def contar_do_usuario(cls, usuario_id):
        with ConexaoBD() as bd:
            return bd.execute("SELECT COUNT(*) FROM resenhas WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]

    @classmethod
    def listar_do_usuario(cls, usuario_id, pagina=1, por_pagina=None):
        """Sem por_pagina devolve tudo; com por_pagina devolve só a página pedida (LIMIT/OFFSET)."""
        sql = "SELECT * FROM resenhas WHERE usuario_id = ? ORDER BY criado_em DESC, id DESC"
        params = [usuario_id]
        if por_pagina is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [por_pagina, (max(1, pagina) - 1) * por_pagina]
        with ConexaoBD() as bd:
            linhas = bd.execute(sql, params).fetchall()
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
