from app.db import DatabaseConnection
from app.models.resenha import _escapar_like

STATUS = {"quero_ler": "Quero ler", "lendo": "Lendo", "lido": "Lido"}
PRIORIDADES = {1: "Alta", 2: "Média", 3: "Baixa"}


class ItemLeitura:
    """Livro/HQ da Lista de Leitura do usuário. Pode vir de uma resenha (resenha_id, opcional)."""

    def __init__(self, usuario_id, titulo, autor, status="quero_ler", prioridade=2, observacao="",
                 resenha_id=None, id=None, criado_em=None, resenha_titulo=None):
        self.id = id
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.autor = autor
        self.status = status
        self.prioridade = prioridade
        self.observacao = observacao or ""
        self.resenha_id = resenha_id
        self.criado_em = criado_em
        self.resenha_titulo = resenha_titulo  # preenchido pelo JOIN na listagem

    @property
    def status_texto(self):
        return STATUS.get(self.status, self.status)

    @property
    def prioridade_texto(self):
        return PRIORIDADES.get(self.prioridade, str(self.prioridade))

    # ------------------------------------------------------------ escrita
    def salvar(self):
        with DatabaseConnection() as db:
            db.cursor.execute(
                """INSERT INTO itens_leitura
                       (usuario_id, resenha_id, titulo, autor, status, prioridade, observacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (self.usuario_id, self.resenha_id, self.titulo, self.autor,
                 self.status, self.prioridade, self.observacao),
            )
            self.id = db.cursor.lastrowid
        return self.id

    def atualizar(self):
        with DatabaseConnection() as db:
            db.cursor.execute(
                """UPDATE itens_leitura
                      SET titulo = ?, autor = ?, status = ?, prioridade = ?, observacao = ?
                    WHERE id = ? AND usuario_id = ?""",
                (self.titulo, self.autor, self.status, self.prioridade, self.observacao,
                 self.id, self.usuario_id),
            )
            return db.cursor.rowcount > 0

    def excluir(self):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "DELETE FROM itens_leitura WHERE id = ? AND usuario_id = ?", (self.id, self.usuario_id)
            )
            return db.cursor.rowcount > 0

    # ------------------------------------------------------------ leitura
    @classmethod
    def buscar_por_id(cls, item_id, usuario_id):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "SELECT * FROM itens_leitura WHERE id = ? AND usuario_id = ?", (item_id, usuario_id)
            )
            linha = db.cursor.fetchone()
        return cls(**dict(linha)) if linha else None

    @classmethod
    def existe_titulo(cls, usuario_id, titulo):
        with DatabaseConnection() as db:
            db.cursor.execute(
                "SELECT 1 FROM itens_leitura WHERE usuario_id = ? AND titulo = ? COLLATE NOCASE LIMIT 1",
                (usuario_id, titulo),
            )
            return db.cursor.fetchone() is not None

    @classmethod
    def contar_por_usuario(cls, usuario_id, busca="", status=""):
        busca = (busca or "").strip()
        like = f"%{_escapar_like(busca)}%"
        with DatabaseConnection() as db:
            db.cursor.execute(
                """SELECT COUNT(*) FROM itens_leitura
                    WHERE usuario_id = ?
                      AND (? = '' OR titulo LIKE ? ESCAPE '\\' OR autor LIKE ? ESCAPE '\\')
                      AND (? = '' OR status = ?)""",
                (usuario_id, busca, like, like, status or "", status or ""),
            )
            return db.cursor.fetchone()[0]

    @classmethod
    def listar_por_usuario(cls, usuario_id, pagina=1, por_pagina=10, busca="", status=""):
        busca = (busca or "").strip()
        like = f"%{_escapar_like(busca)}%"
        with DatabaseConnection() as db:
            # JOIN com resenhas (relacionamento): mostra de qual resenha o livro veio, se houver.
            db.cursor.execute(
                """SELECT i.*, r.titulo AS resenha_titulo
                     FROM itens_leitura i
                     LEFT JOIN resenhas r ON r.id = i.resenha_id AND r.usuario_id = i.usuario_id
                    WHERE i.usuario_id = ?
                      AND (? = '' OR i.titulo LIKE ? ESCAPE '\\' OR i.autor LIKE ? ESCAPE '\\')
                      AND (? = '' OR i.status = ?)
                    ORDER BY i.prioridade ASC, i.criado_em DESC, i.id DESC
                    LIMIT ? OFFSET ?""",
                (usuario_id, busca, like, like, status or "", status or "",
                 por_pagina, (max(1, pagina) - 1) * por_pagina),
            )
            return [cls(**dict(linha)) for linha in db.cursor.fetchall()]
