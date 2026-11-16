"""Rodar na raiz do projeto:  python -m unittest discover -s tests -v
Usa um banco temporário e não acessa a internet."""
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
_tmp = tempfile.TemporaryDirectory()
os.environ["BANCO_DB"] = str(Path(_tmp.name) / "teste.db")  # ANTES de importar o app
sys.path.insert(0, str(RAIZ))

import iniciar_bd
from app import app as flask_app
from app.db import DB_PATH, DatabaseConnection
from app.models.item_leitura import ItemLeitura
from app.models.resenha import LIMITE_RESENHAS_POR_HORA, Resenha
from app.models.usuario import Usuario, UsuarioJaExiste
from app.utils import recomendacao


class Base(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        iniciar_bd.criar_tabelas()
        recomendacao.limpar_cache()
        flask_app.config["TESTING"] = True
        self.c = flask_app.test_client()

    def registrar(self, cliente=None, nome="ana", senha="segredo1"):
        return (cliente or self.c).post("/registro", data={"usuario": nome, "senha": senha})

    def criar_resenha(self, cliente=None, titulo="O Hobbit", genero="fantasia", nota="5",
                      texto="Aventura incrível com dragões!"):
        return (cliente or self.c).post("/resenha", data={"titulo": titulo, "genero": genero,
                                                           "nota": nota, "resenha": texto})

    def html(self, url, cliente=None):
        return (cliente or self.c).get(url).get_data(as_text=True)


# ---------------------------------------------------------------- banco / POO
class TestBanco(Base):
    def test_context_manager_faz_commit_e_rollback(self):
        with DatabaseConnection() as db:
            db.cursor.execute("INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)", ("a1", "x"))
        self.assertIsNotNone(Usuario.buscar_por_username("a1"))
        with self.assertRaises(RuntimeError):
            with DatabaseConnection() as db:
                db.cursor.execute("INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)", ("b2", "x"))
                raise RuntimeError("falha")
        self.assertIsNone(Usuario.buscar_por_username("b2"))

    def test_iniciar_bd_cria_usuario_de_teste_sem_duplicar(self):
        self.assertTrue(iniciar_bd.criar_dados_iniciais())
        self.assertFalse(iniciar_bd.criar_dados_iniciais())
        u = Usuario.buscar_por_username("teste")
        self.assertTrue(u.verificar_senha("teste123"))
        self.assertNotIn("teste123", u.senha_hash)
        r = self.c.post("/", data={"usuario": "teste", "senha": "teste123"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Watchmen", self.html("/resenhas"))
        self.assertIn("Maus", self.html("/leitura/"))

    def test_usuario_duplicado_levanta_excecao_propria(self):
        u = Usuario("ana"); u.definir_senha("segredo1"); u.salvar()
        with self.assertRaises(UsuarioJaExiste):
            Usuario("ANA", "x").salvar()

    def test_fk_e_cascade(self):
        with self.assertRaises(sqlite3.IntegrityError):
            Resenha(usuario_id=999, titulo="x", genero="yy", nota=3, texto="texto qualquer aqui").salvar()
        self.registrar()
        self.criar_resenha()
        with DatabaseConnection() as db:
            db.cursor.execute("DELETE FROM usuarios WHERE id = 1")
        self.assertEqual(Resenha.contar_por_usuario(1), 0)

    def test_set_null_ao_apagar_resenha_de_origem(self):
        self.registrar()
        self.criar_resenha()
        item = ItemLeitura(1, "Duna", "Frank Herbert", resenha_id=1)
        item.salvar()
        Resenha.buscar_por_id(1, 1).excluir()
        self.assertIsNone(ItemLeitura.buscar_por_id(item.id, 1).resenha_id)

    def test_controllers_sem_sql_e_models_sem_fstring_no_sql(self):
        for arq in (RAIZ / "app" / "controllers").glob("*.py"):
            texto = arq.read_text(encoding="utf-8")
            self.assertNotIn("sqlite3", texto, arq.name)
            self.assertIsNone(re.search(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b", texto), arq.name)
        for arq in (RAIZ / "app" / "models").glob("*.py"):
            self.assertIsNone(re.search(r'execute\(\s*f["\']', arq.read_text(encoding="utf-8")), arq.name)


# ------------------------------------------------------------ autenticação
class TestAcesso(Base):
    ROTAS = ("/resenhas", "/resenha", "/resenha/1/editar", "/resenha/1/indicacao",
             "/leitura/", "/leitura/novo", "/leitura/1/editar")

    def test_rotas_protegidas_redirecionam_para_login(self):
        for url in self.ROTAS:
            r = self.c.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertTrue(r.headers["Location"].endswith("/"), url)

    def test_registro_login_logout_e_sessao(self):
        r = self.registrar()
        self.assertEqual(r.status_code, 302)
        with self.c.session_transaction() as s:
            self.assertEqual(s["user_id"], 1)
            self.assertEqual(s["username"], "ana")
        self.assertEqual(self.c.get("/resenha").status_code, 200)
        self.c.get("/logout")
        with self.c.session_transaction() as s:
            self.assertNotIn("user_id", s)
        self.assertEqual(self.c.get("/resenha").status_code, 302)
        ruim = self.c.post("/", data={"usuario": "ana", "senha": "errada"})
        self.assertIn("inválidos", ruim.get_data(as_text=True))
        self.assertEqual(self.c.post("/", data={"usuario": "ANA", "senha": "segredo1"}).status_code, 302)

    def test_senha_nunca_em_texto_puro(self):
        self.registrar()
        self.assertNotIn("segredo1", Usuario.buscar_por_username("ana").senha_hash)

    def test_validacao_do_registro(self):
        self.registrar()
        dup = self.registrar(flask_app.test_client(), "Ana")
        self.assertIn("já está em uso", dup.get_data(as_text=True))
        curto = self.registrar(flask_app.test_client(), "ab", "123")
        self.assertEqual(curto.status_code, 400)
        self.assertIsNone(Usuario.buscar_por_username("ab"))

    def test_middleware_valida_no_banco(self):
        self.registrar()
        with DatabaseConnection() as db:
            db.cursor.execute("DELETE FROM usuarios")
        r = self.c.get("/resenhas")  # sessão ainda tem user_id, mas o usuário não existe mais
        self.assertEqual(r.status_code, 302)
        with self.c.session_transaction() as s:
            self.assertNotIn("user_id", s)

    def test_g_usuario_disponivel_na_rota(self):
        from flask import g, session
        from app.utils.auth_middleware import login_required

        @login_required
        def alvo():
            return g.usuario.username

        self.registrar()
        with flask_app.test_request_context():
            session["user_id"] = 1
            self.assertEqual(alvo(), "ana")


# ---------------------------------------------------------- cookies e flash
class TestCookiesFlashErros(Base):
    def test_cookie_ultimo_usuario(self):
        r = self.registrar()
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("ultimo_usuario=ana", cookie)
        self.assertIn("Max-Age=2592000", cookie)
        self.c.get("/logout")
        self.assertIn('value="ana"', self.html("/"))

    def test_cookie_de_tema(self):
        self.assertIn('data-tema="escuro"', self.html("/"))
        r = self.c.post("/tema", data={"tema": "claro"})
        self.assertIn("tema=claro", r.headers.get("Set-Cookie", ""))
        self.assertIn('data-tema="claro"', self.html("/"))
        r = self.c.post("/tema", data={"tema": "<script>"}, headers={"Referer": "http://evil.com/x"})
        self.assertIn("tema=escuro", r.headers.get("Set-Cookie", ""))
        self.assertNotIn("evil.com", r.headers["Location"])

    def test_flash_categorizado(self):
        self.registrar()
        self.assertIn("aviso-success", self.html("/resenha"))
        r = self.c.post("/resenha", data={"titulo": "", "genero": "x", "resenha": "curta"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("aviso-danger", r.get_data(as_text=True))

    def test_404_personalizado_e_log(self):
        with self.assertLogs(flask_app.logger, level="WARNING") as logs:
            r = self.c.get("/nao-existe")
        self.assertEqual(r.status_code, 404)
        self.assertIn("404 — Página não encontrada", r.get_data(as_text=True))
        self.assertTrue(any("404" in linha for linha in logs.output))

    def test_logger_registra_login_falha_e_crud(self):
        with self.assertLogs(flask_app.logger, level="INFO") as logs:
            self.registrar()
            self.criar_resenha()
            self.c.post("/resenha/1/excluir")
            self.c.get("/logout")
            self.c.post("/", data={"usuario": "ana", "senha": "errada"})
        saida = "\n".join(logs.output)
        for trecho in ("Novo usuário", "Resenha criada", "Resenha excluída", "Logout", "Falha de autenticação"):
            self.assertIn(trecho, saida)


# ------------------------------------------------------------------ resenhas
class TestResenhas(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_ciclo_completo(self):
        self.assertEqual(self.criar_resenha().status_code, 302)
        self.assertIn("O Hobbit", self.html("/resenhas"))
        r = self.c.post("/resenha/1/editar", data={"titulo": "O Hobbit 2", "genero": "aventura",
                                                   "nota": "3", "resenha": "Releitura ainda melhor."})
        self.assertEqual(r.status_code, 302)
        e = Resenha.buscar_por_id(1, 1)
        self.assertEqual((e.titulo, e.genero, e.nota), ("O Hobbit 2", "aventura", 3))
        self.assertEqual(self.c.post("/resenha/1/excluir").status_code, 302)
        self.assertIsNone(Resenha.buscar_por_id(1, 1))

    def test_validacao_servidor(self):
        r = self.criar_resenha(titulo="  ", genero="x", texto="curto", nota="9")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Resenha.contar_por_usuario(1), 0)
        self.assertIn("Informe o título", r.get_data(as_text=True))

    def test_excluir_so_por_post(self):
        self.criar_resenha()
        self.assertEqual(self.c.get("/resenha/1/excluir").status_code, 405)

    def test_isolamento_entre_usuarios(self):
        self.criar_resenha()
        outro = flask_app.test_client()
        self.registrar(outro, "bia", "segredo2")
        self.assertEqual(outro.get("/resenha/1/editar").status_code, 404)
        self.assertEqual(outro.get("/resenha/1/indicacao").status_code, 404)
        self.assertEqual(outro.post("/resenha/1/excluir").status_code, 404)
        self.assertEqual(Resenha.buscar_por_id(1, 1).titulo, "O Hobbit")
        self.assertNotIn("O Hobbit", self.html("/resenhas", outro))

    def test_sql_injection_e_xss(self):
        self.criar_resenha(titulo="'); DROP TABLE resenhas; --", texto="<script>alert(1)</script> texto longo")
        self.assertEqual(Resenha.contar_por_usuario(1), 1)
        h = self.html("/resenhas")
        self.assertNotIn("<script>alert(1)</script>", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertEqual(Resenha.contar_por_usuario(1, busca="' OR '1'='1"), 0)

    def test_busca_e_filtros(self):
        self.criar_resenha(titulo="O Hobbit", genero="fantasia", nota="5")
        self.criar_resenha(titulo="Watchmen", genero="quadrinhos", nota="4", texto="HQ muito inteligente.")
        self.criar_resenha(titulo="100% Fantasia", genero="Fantasia", nota="2", texto="Texto de teste longo.")
        self.assertEqual(Resenha.contar_por_usuario(1, busca="watch"), 1)
        self.assertEqual(Resenha.contar_por_usuario(1, genero="FANTASIA"), 2)
        self.assertEqual(Resenha.contar_por_usuario(1, nota=4), 1)
        self.assertEqual(Resenha.contar_por_usuario(1, busca="100%"), 1)   # % é literal
        self.assertEqual(Resenha.contar_por_usuario(1, busca="%"), 1)
        self.assertEqual(Resenha.contar_por_usuario(1, busca="inteligente", genero="quadrinhos", nota=4), 1)
        h = self.html("/resenhas?q=watch&nota=4")
        self.assertIn("Watchmen", h)
        self.assertNotIn("O Hobbit", h)
        self.assertEqual(self.c.get("/resenhas?nota=abc&pagina=xyz").status_code, 200)

    def test_paginacao_mantem_filtros(self):
        for i in range(12):
            Resenha(1, f"Livro {i:02d}", "fantasia", f"Resenha numero {i}", nota=3).salvar()
        h1 = self.html("/resenhas?genero=fantasia")
        self.assertIn("Página 1 de 2", h1)
        self.assertIn("genero=fantasia", h1.split("Próxima")[0].rsplit("href=", 1)[1])
        self.assertIn("Livro 00", self.html("/resenhas?genero=fantasia&pagina=2"))
        self.assertIn("Página 2 de 2", self.html("/resenhas?pagina=99"))

    def test_limite_por_hora(self):
        for i in range(LIMITE_RESENHAS_POR_HORA):
            self.assertEqual(self.criar_resenha(titulo=f"L{i}").status_code, 302)
        r = self.criar_resenha(titulo="extra")
        self.assertEqual(r.status_code, 429)
        self.assertIn("limite", r.get_data(as_text=True))
        self.assertIn("extra", r.get_data(as_text=True))  # texto preservado


# ------------------------------------------------------------ lista de leitura
class TestLeitura(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def novo(self, cliente=None, **kw):
        dados = {"titulo": "Duna", "autor": "Frank Herbert", "status": "quero_ler",
                 "prioridade": "1", "observacao": ""}
        dados.update(kw)
        return (cliente or self.c).post("/leitura/novo", data=dados)

    def test_ciclo_completo(self):
        self.assertEqual(self.novo().status_code, 302)
        self.assertIn("Duna", self.html("/leitura/"))
        r = self.c.post("/leitura/1/editar", data={"titulo": "Duna Messias", "autor": "Frank Herbert",
                                                   "status": "lendo", "prioridade": "2", "observacao": "bom"})
        self.assertEqual(r.status_code, 302)
        i = ItemLeitura.buscar_por_id(1, 1)
        self.assertEqual((i.titulo, i.status, i.prioridade), ("Duna Messias", "lendo", 2))
        self.assertEqual(self.c.get("/leitura/1/excluir").status_code, 405)
        self.assertEqual(self.c.post("/leitura/1/excluir").status_code, 302)
        self.assertIsNone(ItemLeitura.buscar_por_id(1, 1))

    def test_validacao(self):
        r = self.novo(titulo="", status="invalido", prioridade="9", observacao="x" * 501)
        self.assertEqual(r.status_code, 400)
        h = r.get_data(as_text=True)
        for trecho in ("Informe o título", "status válido", "prioridade válida", "500 caracteres"):
            self.assertIn(trecho, h)
        self.assertEqual(ItemLeitura.contar_por_usuario(1), 0)

    def test_isolamento(self):
        self.novo()
        outro = flask_app.test_client()
        self.registrar(outro, "bia", "segredo2")
        self.assertEqual(outro.get("/leitura/1/editar").status_code, 404)
        self.assertEqual(outro.post("/leitura/1/excluir").status_code, 404)
        self.assertNotIn("Duna", self.html("/leitura/", outro))
        self.assertIsNotNone(ItemLeitura.buscar_por_id(1, 1))

    def test_busca_filtro_e_ordem_por_prioridade(self):
        self.novo(titulo="A", autor="Zeca", prioridade="3")
        self.novo(titulo="B", autor="Ana", status="lido", prioridade="1")
        lista = ItemLeitura.listar_por_usuario(1)
        self.assertEqual([i.titulo for i in lista], ["B", "A"])
        self.assertEqual(ItemLeitura.contar_por_usuario(1, busca="zeca"), 1)
        self.assertEqual(ItemLeitura.contar_por_usuario(1, status="lido"), 1)
        h = self.html("/leitura/?status=lido")
        self.assertIn("B", h)
        self.assertEqual(self.c.get("/leitura/?status=hack").status_code, 200)

    def test_relacionamento_com_resenha(self):
        self.criar_resenha()
        r = self.c.post("/resenha/1/indicacao/adicionar", data={"titulo": "Eragon", "autor": "Paolini"})
        self.assertEqual(r.status_code, 302)
        self.assertIn('Indicado a partir da resenha "O Hobbit"', self.html("/leitura/"))
        repetido = self.c.post("/resenha/1/indicacao/adicionar", data={"titulo": "eragon", "autor": "P"},
                               follow_redirects=True)
        self.assertIn("já está na sua lista", repetido.get_data(as_text=True))
        self.assertEqual(ItemLeitura.contar_por_usuario(1), 1)
        outro = flask_app.test_client()
        self.registrar(outro, "bia", "segredo2")
        self.assertEqual(outro.post("/resenha/1/indicacao/adicionar",
                                    data={"titulo": "X", "autor": "Y"}).status_code, 404)


# ------------------------------------------------------------- recomendação
class RespostaFalsa:
    def __init__(self, docs):
        self._docs = docs

    def raise_for_status(self):
        pass

    def json(self):
        return {"docs": self._docs}


class TestRecomendacao(Base):
    def test_indicacao_e_botao_de_adicionar(self):
        self.registrar()
        self.criar_resenha()
        docs = [{"title": f"Livro {i}", "author_name": [f"Autor {i}"]} for i in range(5)]
        with mock.patch.object(recomendacao.requests, "get", return_value=RespostaFalsa(docs)):
            h = self.html("/resenha/1/indicacao")
        self.assertIn("Adicionar à lista de leitura", h)
        self.assertIn('action="/resenha/1/indicacao/adicionar"', h)

    def test_api_fora_do_ar(self):
        self.registrar()
        self.criar_resenha()
        erro = recomendacao.requests.exceptions.ConnectionError("x")
        with mock.patch.object(recomendacao.requests, "get", side_effect=erro):
            with self.assertLogs(flask_app.logger, level="WARNING"):
                h = self.html("/resenha/1/indicacao")
        self.assertIn("Não consegui buscar indicações", h)


if __name__ == "__main__":
    unittest.main()
