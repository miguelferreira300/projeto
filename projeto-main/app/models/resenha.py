import math

from app.db import DatabaseConnection

LIMITE_RESENHAS_POR_HORA = 10


class LimiteDeResenhas(Exception):
    """Levantada quando a pessoa já criou resenhas demais na última hora."""

    def __init__(self, minutos):
        super().__init__(f"Limite de {LIMITE_RESENHAS_POR_HORA} resenhas por hora atingido.")
        self.minutos = minutos


def _escapar_like(texto):
    """Faz % e _ digitados pelo usuário valerem como texto comum no LIKE."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parametros_filtro(busca, genero, nota):
    busca = (busca or "").strip()
    genero = (genero or "").strip()
    like = f"%{_escapar_like(busca)}%"
    return (busca, like, like, genero, genero, nota, nota)


class Resenha:
    def __init__(self, usuario_id, titulo, genero, texto, nota=None, id=None, criado_em=None):
        self.id = id
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.genero = genero
        self.nota = nota
        self.texto = texto
        self.criado_em = criado_em

    # ------------------------------------------------------------ escrita
    def salvar(self):
        """INSERT de uma resenha nova (sem checar o limite por hora; as rotas usam criar_com_limite)."""
        with DatabaseConnection() as db:
            db.cursor.execute(
                "INSERT INTO resenhas (usuario_id, titulo, genero, nota, texto) VALUES (?, ?, ?, ?, ?)",
                (self.usuario_id, self.titulo, self.genero, self.nota, self.texto),
            )
            self.id = db.cursor.lastrowid
        return self.id

    def atualizar(self):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "UPDATE resenhas SET titulo = ?, genero = ?, nota = ?, texto = ? "
                "WHERE id = ? AND usuario_id = ?",
                (self.titulo, self.genero, self.nota, self.texto, self.id, self.usuario_id),
            )
            return db.cursor.rowcount > 0

    def excluir(self):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "DELETE FROM resenhas WHERE id = ? AND usuario_id = ?", (self.id, self.usuario_id)
            )
            return db.cursor.rowcount > 0

    @classmethod
    def criar_com_limite(cls, usuario_id, titulo, genero, nota, texto):
        """Cria a resenha respeitando o limite por hora. Levanta LimiteDeResenhas se estourou."""
        with DatabaseConnection() as db:
            # BEGIN IMMEDIATE trava as escritas: "conferir o limite" e "inserir" viram uma
            # operação indivisível, então duas requisições simultâneas não furam o limite.
            db.cursor.execute("BEGIN IMMEDIATE")
            db.cursor.execute("DELETE FROM registro_criacoes WHERE criado_em <= datetime('now', '-1 hour')")
            db.cursor.execute("SELECT COUNT(*) FROM registro_criacoes WHERE usuario_id = ?", (usuario_id,))
            total = db.cursor.fetchone()[0]
            if total >= LIMITE_RESENHAS_POR_HORA:
                # Uma vaga abre quando a criação mais antiga completa 1 hora.
                db.cursor.execute(
                    """SELECT CAST((julianday(criado_em, '+1 hour') - julianday('now')) * 86400 AS INTEGER)
                         FROM registro_criacoes WHERE usuario_id = ?
                        ORDER BY criado_em ASC, id ASC LIMIT 1 OFFSET ?""",
                    (usuario_id, total - LIMITE_RESENHAS_POR_HORA),
                )
                segundos = db.cursor.fetchone()[0]
                raise LimiteDeResenhas(max(1, math.ceil(segundos / 60)))
            db.cursor.execute(
                "INSERT INTO resenhas (usuario_id, titulo, genero, nota, texto) VALUES (?, ?, ?, ?, ?)",
                (usuario_id, titulo, genero, nota, texto),
            )
            novo_id = db.cursor.lastrowid
            db.cursor.execute("INSERT INTO registro_criacoes (usuario_id) VALUES (?)", (usuario_id,))
            return novo_id

    # ------------------------------------------------------------ leitura
    @classmethod
    def buscar_por_id(cls, resenha_id, usuario_id):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "SELECT * FROM resenhas WHERE id = ? AND usuario_id = ?", (resenha_id, usuario_id)
            )
            linha = db.cursor.fetchone()
        return cls(**dict(linha)) if linha else None

    @classmethod
    def contar_por_usuario(cls, usuario_id, busca="", genero="", nota=None):
        with DatabaseConnection() as db:
            db.cursor.execute(
                """SELECT COUNT(*) FROM resenhas
                    WHERE usuario_id = ?
                      AND (? = '' OR titulo LIKE ? ESCAPE '\\' OR texto LIKE ? ESCAPE '\\')
                      AND (? = '' OR genero = ? COLLATE NOCASE)
                      AND (? IS NULL OR nota = ?)""",
                (usuario_id, *_parametros_filtro(busca, genero, nota)),
            )
            return db.cursor.fetchone()[0]

    @classmethod
    def listar_por_usuario(cls, usuario_id, pagina=1, por_pagina=10, busca="", genero="", nota=None):
        with DatabaseConnection() as db:
            db.cursor.execute(
                """SELECT * FROM resenhas
                    WHERE usuario_id = ?
                      AND (? = '' OR titulo LIKE ? ESCAPE '\\' OR texto LIKE ? ESCAPE '\\')
                      AND (? = '' OR genero = ? COLLATE NOCASE)
                      AND (? IS NULL OR nota = ?)
                    ORDER BY criado_em DESC, id DESC
                    LIMIT ? OFFSET ?""",
                (usuario_id, *_parametros_filtro(busca, genero, nota),
                 por_pagina, (max(1, pagina) - 1) * por_pagina),
            )
            return [cls(**dict(linha)) for linha in db.cursor.fetchall()]

    @classmethod
    def generos_do_usuario(cls, usuario_id):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "SELECT DISTINCT genero FROM resenhas WHERE usuario_id = ? ORDER BY genero COLLATE NOCASE",
                (usuario_id,),
            )
            return [linha["genero"] for linha in db.cursor.fetchall()]

    @classmethod
    def titulos_do_usuario(cls, usuario_id):
        with DatabaseConnection() as db:
            db.cursor.execute("SELECT titulo FROM resenhas WHERE usuario_id = ?", (usuario_id,))
            return [linha["titulo"] for linha in db.cursor.fetchall()]
