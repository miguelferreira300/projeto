"""Cria as tabelas (CREATE TABLE IF NOT EXISTS) e os dados iniciais.

Uso:  python iniciar_bd.py
Usuário de teste:  teste / teste123
"""
from app.db import DB_PATH, DatabaseConnection
from app.models.item_leitura import ItemLeitura
from app.models.resenha import Resenha
from app.models.usuario import Usuario

USUARIO_TESTE = "teste"
SENHA_TESTE = "teste123"


def criar_tabelas():
    with DatabaseConnection() as db:
        db.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL UNIQUE COLLATE NOCASE,
                senha_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resenhas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                titulo     TEXT NOT NULL,
                genero     TEXT NOT NULL,
                nota       INTEGER CHECK (nota BETWEEN 1 AND 5),
                texto      TEXT NOT NULL,
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
            );

            -- Uma linha para cada resenha criada: serve só para o limite por hora e fica separada
            -- de "resenhas" de propósito (apagar uma resenha não devolve a "vaga").
            CREATE TABLE IF NOT EXISTS registro_criacoes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_registro_criacoes ON registro_criacoes (usuario_id, criado_em);

            -- 2ª entidade: Lista de Leitura. resenha_id é opcional (livro indicado a partir de uma resenha).
            CREATE TABLE IF NOT EXISTS itens_leitura (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                resenha_id INTEGER,
                titulo     TEXT NOT NULL,
                autor      TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'quero_ler' CHECK (status IN ('quero_ler', 'lendo', 'lido')),
                prioridade INTEGER NOT NULL DEFAULT 2 CHECK (prioridade BETWEEN 1 AND 3),
                observacao TEXT NOT NULL DEFAULT '',
                criado_em  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
                FOREIGN KEY (resenha_id) REFERENCES resenhas (id) ON DELETE SET NULL
            );
            """
        )


def criar_dados_iniciais():
    """Cria o usuário de teste (com senha em hash) e alguns exemplos. Não duplica se já existir."""
    if Usuario.buscar_por_username(USUARIO_TESTE) is not None:
        return False

    usuario = Usuario(username=USUARIO_TESTE)
    usuario.definir_senha(SENHA_TESTE)
    usuario.salvar()

    resenha = Resenha(usuario.id, "O Hobbit", "fantasia", nota=5,
                      texto="Aventura clássica, cheia de dragões, anões e uma jornada inesquecível.")
    resenha.salvar()
    Resenha(usuario.id, "Watchmen", "quadrinhos", nota=4,
            texto="HQ densa e inteligente, que desconstrói a ideia de super-herói.").salvar()

    ItemLeitura(usuario.id, "O Senhor dos Anéis", "J. R. R. Tolkien", "lendo", 1,
                "Continuação natural de O Hobbit.", resenha_id=resenha.id).salvar()
    ItemLeitura(usuario.id, "Duna", "Frank Herbert", "quero_ler", 2).salvar()
    ItemLeitura(usuario.id, "Maus", "Art Spiegelman", "lido", 3).salvar()
    return True


if __name__ == "__main__":
    criar_tabelas()
    novo = criar_dados_iniciais()
    print(f"Banco pronto em: {DB_PATH}")
    print(f"Usuário de teste {'criado' if novo else 'já existia'}: {USUARIO_TESTE} / {SENHA_TESTE}")
