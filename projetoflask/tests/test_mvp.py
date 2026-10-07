"""Rodar:  python -m unittest discover -s tests -v   (não usa internet e não toca no seu banco)"""
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

# O banco dos testes é temporário: definimos a variável ANTES de importar o pacote 'clube',
# porque o import já cria as tabelas.
_tmp = tempfile.TemporaryDirectory()
os.environ["RESENHAS_DB"] = str(Path(_tmp.name) / "teste.db")

# Adiciona a raiz do projeto ao path para encontrar o pacote 'clube'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.security import generate_password_hash

from clube import models
from clube import recomendacao
from clube import app as modulo_app

CAMINHO_ORIGINAL = models.CAMINHO


class RespostaFalsa:
    def __init__(self, docs, erro=False):
        self._docs, self._erro = docs, erro

    def raise_for_status(self):
        if self._erro:
            raise recomendacao.requests.HTTPError("500")

    def json(self):
        return {"docs": self._docs}


DOCS = [
    {"title": "Eragon", "author_name": ["Christopher Paolini"], "cover_i": 11,
     "first_publish_year": 2002, "ratings_average": 4.13, "ratings_count": 300},
    {"title": "O Silmarillion", "author_name": ["J. R. R. Tolkien"]},
    {"title": "Sem Autor"},
]


def muitos_docs(prefixo, n, nota=None, autor_unico=False):
    return [
        {"title": f"{prefixo} {i}", "author_name": ["Mesmo Autor" if autor_unico else f"{prefixo} Autor {i}"],
         **({"ratings_average": nota, "ratings_count": 100} if nota else {})}
        for i in range(n)
    ]


class Base(unittest.TestCase):
    def setUp(self):
        models.CAMINHO = CAMINHO_ORIGINAL
        if models.CAMINHO.exists():
            models.CAMINHO.unlink()
        models.criar_tabelas()
        recomendacao.limpar_cache()
        modulo_app.config["TESTING"] = True
        self.c = modulo_app.test_client()

    def registrar(self, nome="ana", senha="segredo1"):
        return self.c.post("/registro", data={"usuario": nome, "senha": senha})

    def criar(self, titulo="O Hobbit", genero="fantasia", texto="Aventura incrível com dragões!", nota="5"):
        dados = {"titulo": titulo, "genero": genero, "resenha": texto}
        if nota is not None:
            dados["nota"] = nota
        return self.c.post("/resenha", data=dados)

    def html(self, url):
        return self.c.get(url).get_data(as_text=True)


# ======================================================================= acesso
class TestAcesso(Base):
    def test_paginas_protegidas_redirecionam(self):
        for url in ("/resenhas", "/resenha", "/resenha/1/editar", "/resenha/1/indicacao"):
            self.assertEqual(self.c.get(url).status_code, 302, url)

    def test_registro_login_logout(self):
        self.assertEqual(self.registrar().status_code, 302)
        self.assertEqual(self.c.get("/resenha").status_code, 200)
        self.c.get("/logout")
        self.assertEqual(self.c.get("/resenha").status_code, 302)
        ruim = self.c.post("/", data={"usuario": "ana", "senha": "errada"})
        self.assertIn("inválidos", ruim.get_data(as_text=True))
        ok = self.c.post("/", data={"usuario": "ANA", "senha": "segredo1"})
        self.assertEqual(ok.status_code, 302)

    def test_senha_fica_com_hash(self):
        self.registrar()
        self.assertNotIn("segredo1", models.Usuario.buscar_por_nome("ana").senha_hash)

    def test_usuario_duplicado_e_validacao(self):
        self.registrar()
        outro = modulo_app.test_client().post("/registro", data={"usuario": "Ana", "senha": "segredo1"})
        self.assertIn("já está em uso", outro.get_data(as_text=True))
        curto = modulo_app.test_client().post("/registro", data={"usuario": "ab", "senha": "123"})
        self.assertEqual(curto.status_code, 200)
        self.assertIsNone(models.Usuario.buscar_por_nome("ab"))


# ========================================================================= CRUD
class TestCrud(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_ciclo_completo(self):
        r = self.criar()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)
        self.assertIn("O Hobbit", self.html("/resenhas"))

        r = self.c.post("/resenha/1/editar", data={"titulo": "O Hobbit (2ª ed.)", "genero": "aventura",
                                                   "nota": "3", "resenha": "Releitura ainda melhor que a primeira."})
        self.assertEqual(r.status_code, 302)
        editada = models.Resenha.buscar(1, 1)
        self.assertEqual((editada.titulo, editada.genero, editada.nota), ("O Hobbit (2ª ed.)", "aventura", 3))

        self.assertEqual(self.c.post("/resenha/1/excluir").status_code, 302)
        self.assertIsNone(models.Resenha.buscar(1, 1))

    def test_validacao_no_servidor(self):
        r = self.criar(titulo="  ", genero="x", texto="curto")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 0)
        self.assertIn("Informe o título", r.get_data(as_text=True))

    def test_excluir_so_por_post(self):
        self.criar()
        self.assertEqual(self.c.get("/resenha/1/excluir").status_code, 405)
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)

    def test_outro_usuario_nao_acessa(self):
        self.criar()
        outro = modulo_app.test_client()
        outro.post("/registro", data={"usuario": "bia", "senha": "segredo2"})
        self.assertEqual(outro.get("/resenha/1/editar").status_code, 404)
        self.assertEqual(outro.get("/resenha/1/indicacao").status_code, 404)
        self.assertEqual(outro.post("/resenha/1/excluir").status_code, 404)
        self.assertEqual(outro.post("/resenha/1/editar", data={"titulo": "hack", "genero": "xx", "nota": "1",
                                                              "resenha": "1234567890"}).status_code, 404)
        self.assertEqual(models.Resenha.buscar(1, 1).titulo, "O Hobbit")
        self.assertNotIn("O Hobbit", outro.get("/resenhas").get_data(as_text=True))

    def test_sql_injection_e_xss(self):
        self.criar(titulo="'); DROP TABLE resenhas; --", texto="<script>alert(1)</script> texto longo")
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)
        html = self.html("/resenhas")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_apagar_usuario_apaga_resenhas_fk(self):
        self.criar()
        with models.ConexaoBD() as bd:
            bd.execute("DELETE FROM usuarios WHERE id = 1")
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 0)

    def test_fk_impede_resenha_sem_dono(self):
        with self.assertRaises(sqlite3.IntegrityError):
            models.Resenha(usuario_id=999, titulo="x", genero="yy", nota=3, texto="texto qualquer aqui").guardar()


# ====================================================================== estrelas
class TestNota(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_nota_obrigatoria_e_entre_1_e_5(self):
        for ruim in (None, "", "0", "6", "-1", "abc", "3.5"):
            r = self.criar(nota=ruim)
            self.assertEqual(r.status_code, 400, f"nota={ruim!r}")
            self.assertIn("nota de 1 a 5", r.get_data(as_text=True))
        self.assertEqual(models.Resenha.contar_do_usuario(1), 0)

    def test_banco_tambem_recusa_nota_invalida(self):
        with self.assertRaises(sqlite3.IntegrityError):
            models.Resenha(usuario_id=1, titulo="x", genero="yy", nota=9, texto="texto qualquer aqui").guardar()

    def test_estrelas_aparecem_na_lista(self):
        self.criar(nota="4")
        html = self.html("/resenhas")
        self.assertEqual(html.count('class="on"'), 4)
        self.assertEqual(html.count('class="off"'), 1)
        self.assertIn('aria-label="Nota 4 de 5"', html)

    def test_formulario_tem_cinco_radios_e_mantem_nota_ao_errar(self):
        html = self.html("/resenha")
        self.assertEqual(html.count('name="nota" value='), 5)
        r = self.criar(nota="2", texto="curto")                      # erro de texto, nota deve ser mantida
        self.assertEqual(r.status_code, 400)
        html = r.get_data(as_text=True)
        self.assertRegex(html, r'value="2"\s+checked')

    def test_editar_preseleciona_a_nota_atual(self):
        self.criar(nota="4")
        self.assertRegex(self.html("/resenha/1/editar"), r'value="4"\s+checked')

    def test_resenha_de_banco_antigo_aparece_como_sem_nota(self):
        antigo = Path(_tmp.name) / "antigo.db"
        con = sqlite3.connect(antigo)
        con.executescript(
            """
            CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE COLLATE NOCASE, senha_hash TEXT NOT NULL);
            CREATE TABLE resenhas (id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                titulo TEXT NOT NULL, genero TEXT NOT NULL, texto TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """
        )
        con.execute("INSERT INTO usuarios (nome, senha_hash) VALUES (?, ?)", ("velho", generate_password_hash("segredo1")))
        con.execute("INSERT INTO resenhas (usuario_id, titulo, genero, texto) VALUES (1, 'Livro Antigo', 'terror', 'Resenha feita antes das estrelas.')")
        con.commit(); con.close()

        models.CAMINHO = antigo
        self.addCleanup(setattr, models, "CAMINHO", CAMINHO_ORIGINAL)
        models.criar_tabelas()                                      # roda a migração
        models.criar_tabelas()                                      # e é idempotente
        r = models.Resenha.buscar(1, 1)
        self.assertEqual((r.titulo, r.nota), ("Livro Antigo", None))

        cliente = modulo_app.test_client()
        cliente.post("/", data={"usuario": "velho", "senha": "segredo1"})
        html = cliente.get("/resenhas").get_data(as_text=True)
        self.assertIn("Livro Antigo", html)
        self.assertIn("sem nota", html)
        # e dá para editar, passando a ter nota
        cliente.post("/resenha/1/editar", data={"titulo": "Livro Antigo", "genero": "terror", "nota": "5",
                                                "resenha": "Agora com cinco estrelas!"})
        self.assertEqual(models.Resenha.buscar(1, 1).nota, 5)


# ============================================================ limite por hora
class TestLimite(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_decima_primeira_resenha_e_barrada(self):
        for i in range(10):
            self.assertEqual(self.criar(titulo=f"Livro {i}").status_code, 302, i)
        r = self.criar(titulo="Livro 11", texto="Texto que não pode se perder.")
        self.assertEqual(r.status_code, 429)
        html = r.get_data(as_text=True)
        self.assertIn("limite de 10 resenhas por hora", html)
        self.assertIn("60 minutos", html)
        self.assertIn("Texto que não pode se perder.", html)        # o que a pessoa digitou volta no formulário
        self.assertEqual(models.Resenha.contar_do_usuario(1), 10)

    def test_apagar_resenhas_nao_burla_o_limite(self):
        for i in range(10):
            self.criar(titulo=f"Livro {i}")
        self.c.post("/resenha/1/excluir")
        self.c.post("/resenha/2/excluir")
        self.assertEqual(self.criar(titulo="Outro").status_code, 429)

    def test_limite_libera_depois_de_uma_hora(self):
        for i in range(10):
            self.criar(titulo=f"Livro {i}")
        with models.ConexaoBD() as bd:
            bd.execute("UPDATE registro_criacoes SET criado_em = datetime('now', '-61 minutes')")
        self.assertEqual(self.criar(titulo="Depois de 1h").status_code, 302)

    def test_mensagem_diz_quanto_falta(self):
        for i in range(10):
            self.criar(titulo=f"Livro {i}")
        with models.ConexaoBD() as bd:  # a mais antiga está quase fazendo 1 hora
            bd.execute("UPDATE registro_criacoes SET criado_em = datetime('now', '-59 minutes') "
                       "WHERE id = (SELECT MIN(id) FROM registro_criacoes)")
        html = self.criar(titulo="X").get_data(as_text=True)
        self.assertIn("em 1 minuto.", html)

    def test_limite_e_por_usuario(self):
        for i in range(10):
            self.criar(titulo=f"Livro {i}")
        outro = modulo_app.test_client()
        outro.post("/registro", data={"usuario": "bia", "senha": "segredo2"})
        r = outro.post("/resenha", data={"titulo": "Do outro", "genero": "terror", "nota": "3",
                                         "resenha": "Resenha de outra pessoa."})
        self.assertEqual(r.status_code, 302)

    def test_editar_nao_conta_para_o_limite(self):
        self.criar()
        for _ in range(15):
            self.c.post("/resenha/1/editar", data={"titulo": "O Hobbit", "genero": "fantasia", "nota": "4",
                                                   "resenha": "Editando várias vezes seguidas."})
        with models.ConexaoBD() as bd:
            self.assertEqual(bd.execute("SELECT COUNT(*) FROM registro_criacoes").fetchone()[0], 1)

    def test_concorrencia_nao_fura_o_limite(self):
        resultados = []

        def tentar(i):
            try:
                models.Resenha.criar_com_limite(1, f"Livro {i}", "terror", 3, "Resenha simultânea.")
                resultados.append("ok")
            except models.LimiteDeResenhas:
                resultados.append("limite")
            except Exception as e:  # ex.: database is locked
                resultados.append(f"erro: {e}")

        threads = [threading.Thread(target=tentar, args=(i,)) for i in range(16)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(resultados.count("ok"), 10, resultados)
        self.assertEqual(resultados.count("limite"), 6, resultados)
        self.assertEqual(models.Resenha.contar_do_usuario(1), 10)


# ============================================================== paginação
class TestPaginacao(Base):
    def setUp(self):
        super().setUp()
        self.registrar()
        for i in range(1, 26):   # 25 resenhas (guardar() não passa pelo limite por hora)
            models.Resenha(usuario_id=1, titulo=f"Livro {i:02d}", genero="terror", nota=3,
                           texto="Resenha de teste da paginação.").guardar()

    def test_dez_por_pagina(self):
        p1, p2, p3 = (self.html(f"/resenhas?pagina={n}") for n in (1, 2, 3))
        self.assertEqual(p1.count('class="resenha"'), 10)
        self.assertEqual(p2.count('class="resenha"'), 10)
        self.assertEqual(p3.count('class="resenha"'), 5)
        self.assertIn("Livro 25", p1)           # mais recentes primeiro
        self.assertNotIn("Livro 15", p1)
        self.assertIn("Livro 15", p2)
        self.assertIn("Livro 01", p3)
        self.assertIn("Página 2 de 3", p2)
        self.assertIn("25 resenhas", p1)

    def test_sem_repeticao_entre_paginas(self):
        todos = []
        for n in (1, 2, 3):
            html = self.html(f"/resenhas?pagina={n}")
            todos += [f"Livro {i:02d}" for i in range(1, 26) if f"<h3>Livro {i:02d}</h3>" in html]
        self.assertEqual(sorted(todos), [f"Livro {i:02d}" for i in range(1, 26)])

    def test_pagina_invalida_nao_quebra(self):
        self.assertIn("Página 3 de 3", self.html("/resenhas?pagina=999"))
        self.assertIn("Página 1 de 3", self.html("/resenhas?pagina=0"))
        self.assertIn("Página 1 de 3", self.html("/resenhas?pagina=-4"))
        self.assertIn("Página 1 de 3", self.html("/resenhas?pagina=abc"))

    def test_navegacao_anterior_proxima(self):
        p1, p2, p3 = (self.html(f"/resenhas?pagina={n}") for n in (1, 2, 3))
        self.assertNotIn('href="/resenhas?pagina=0"', p1)
        self.assertIn("pagina=2", p1)
        self.assertIn("pagina=1", p2)
        self.assertIn("pagina=3", p2)
        self.assertNotIn("pagina=4", p3)

    def test_sem_navegacao_com_uma_pagina_so(self):
        self.setUp_poucas()
        self.assertNotIn("Página 1 de", self.html("/resenhas"))

    def setUp_poucas(self):
        with models.ConexaoBD() as bd:
            bd.execute("DELETE FROM resenhas WHERE id > 3")

    def test_excluir_e_editar_voltam_para_a_mesma_pagina(self):
        r = self.c.post("/resenha/1/excluir", data={"pagina": "2"})
        self.assertTrue(r.headers["Location"].endswith("/resenhas?pagina=2"))
        r = self.c.post("/resenha/2/editar?pagina=2", data={"titulo": "Livro 02", "genero": "terror", "nota": "4",
                                                           "resenha": "Editada na segunda página."})
        self.assertTrue(r.headers["Location"].endswith("/resenhas?pagina=2"))

    def test_excluir_ultima_da_ultima_pagina_nao_quebra(self):
        for i in range(21, 26):
            self.c.post(f"/resenha/{i}/excluir", data={"pagina": "3"})
        self.assertIn("Página 2 de 2", self.c.get("/resenhas?pagina=3").get_data(as_text=True))


# ========================================================= recomendações
class TestRecomendacao(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_indicacao_traduz_genero_e_nao_repete_o_que_ja_leu(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)) as get:
            self.criar(titulo="Eragon", genero="Fantasia")
            html = self.html("/resenha/1/indicacao")
        self.assertEqual(get.call_args.kwargs["params"]["subject"], "fantasy")
        self.assertIn("O Silmarillion", html)           # Eragon já foi resenhado; sobra este
        self.assertNotIn("Sem Autor", html)
        self.assertIn("Sem capa", html)

    def test_genero_com_acento_e_espaco(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)) as get:
            recomendacao.recomendar_livro("Ficção Científica", [])
        self.assertEqual(get.call_args.kwargs["params"]["subject"], "science_fiction")

    def test_tres_indicacoes_com_detalhes(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("Livro", 8, nota=4.26))):
            livros = recomendacao.recomendar_livros("fantasia", [])
        self.assertEqual(len(livros), 3)
        self.assertEqual(len({l["titulo"] for l in livros}), 3)
        self.assertEqual(livros[0]["nota_media"], 4.3)
        self.assertEqual(livros[0]["n_notas"], 100)

    def test_pagina_mostra_tres_cartoes_e_botao_novas_indicacoes(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("Livro", 8))):
            self.criar(titulo="Outro", genero="fantasia")
            html = self.html("/resenha/1/indicacao")
        self.assertEqual(html.count('class="recomendacao-box"'), 3)
        self.assertIn("Novas indicações", html)

    def test_nota_da_comunidade_com_separador_de_milhar(self):
        docs = [{"title": "Popular", "author_name": ["Alguém"], "ratings_average": 4.47, "ratings_count": 15400,
                 "first_publish_year": 2007}]
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(docs)):
            self.criar(titulo="Outro", genero="fantasia")
            html = self.html("/resenha/1/indicacao")
        self.assertIn("★ 4.5 na Open Library (15.400 avaliações)", html)

    def test_novas_indicacoes_nunca_repetem(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("Livro", 9))):
            self.criar(titulo="Outro", genero="fantasia")
            vistos = []
            for _ in range(3):
                html = self.html("/resenha/1/indicacao")
                vistos += [f"Livro {i}" for i in range(9) if f"<strong>Livro {i}</strong>" in html]
            self.assertEqual(len(vistos), 9)
            self.assertEqual(len(set(vistos)), 9)                    # 3 cliques x 3 livros, todos diferentes
            html = self.html("/resenha/1/indicacao")                # acabaram
            self.assertIn("já viu todas as indicações", html)
            self.assertNotIn("Novas indicações", html)

    def test_prefere_bem_avaliados_e_autores_diferentes(self):
        docs = muitos_docs("Bom", 6, nota=4.5) + muitos_docs("Sem", 6)
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(docs)):
            for _ in range(20):
                titulos = [l["titulo"] for l in recomendacao.recomendar_livros("fantasia", [])]
                self.assertTrue(all(t.startswith("Bom") for t in titulos), titulos)
        recomendacao.limpar_cache()
        mesmo = muitos_docs("Tolkien", 5, nota=4.8, autor_unico=True) + muitos_docs("Outro", 2, nota=4.0)
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(mesmo)):
            for _ in range(20):
                autores = {l["autor"] for l in recomendacao.recomendar_livros("fantasia", [])}
                self.assertGreaterEqual(len(autores), 3, autores)    # 1 "Mesmo Autor" + 2 diferentes

    def test_completa_com_repetidos_se_faltarem_autores(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("L", 5, autor_unico=True))):
            self.assertEqual(len(recomendacao.recomendar_livros("fantasia", [])), 3)

    def test_cache_evita_nova_ida_a_internet(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("Livro", 9))) as get:
            recomendacao.recomendar_livros("fantasia", [])
            recomendacao.recomendar_livros("Fantasia", [])
            recomendacao.recomendar_livros("fantasia", [])
            self.assertEqual(get.call_count, 1)
            recomendacao.recomendar_livros("terror", [])             # outro gênero busca de novo
            self.assertEqual(get.call_count, 2)

    def test_falha_nao_vai_para_o_cache(self):
        import requests
        with mock.patch("clube.recomendacao.requests.get", side_effect=requests.ConnectionError()):
            self.assertIsNone(recomendacao.recomendar_livros("fantasia", []))
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(muitos_docs("Livro", 5))):
            self.assertEqual(len(recomendacao.recomendar_livros("fantasia", [])), 3)

    # ---- a exceção do proxy da escola (Plano A -> Plano B) deve continuar valendo
    def test_plano_a_funciona_direto_sem_proxy(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)) as get:
            recomendacao.recomendar_livros("fantasia", [])
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["proxies"], {"http": None, "https": None})
        self.assertIs(get.call_args.kwargs["verify"], False)

    def test_plano_b_usa_o_proxy_do_ifsp_quando_a_ligacao_direta_cai(self):
        import requests
        with mock.patch("clube.recomendacao.requests.get",
                        side_effect=[requests.ConnectionError("firewall"), RespostaFalsa(DOCS)]) as get:
            livros = recomendacao.recomendar_livros("fantasia", [])
        self.assertTrue(livros)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].kwargs["proxies"], recomendacao.PROXY_ESCOLA)
        self.assertEqual(recomendacao.PROXY_ESCOLA["https"], "http://proxy.spo.ifsp.edu.br:3128/")
        self.assertIs(get.call_args_list[1].kwargs["verify"], False)

    def test_plano_b_tambem_cobre_resposta_que_nao_e_json(self):
        ruim = mock.Mock()
        ruim.raise_for_status.return_value = None
        ruim.json.side_effect = ValueError("página de login do proxy, não é JSON")
        with mock.patch("clube.recomendacao.requests.get", side_effect=[ruim, RespostaFalsa(DOCS)]) as get:
            self.assertTrue(recomendacao.recomendar_livros("fantasia", []))
        self.assertEqual(get.call_count, 2)

    def test_api_fora_do_ar_nao_quebra(self):
        import requests
        with mock.patch("clube.recomendacao.requests.get", side_effect=requests.ConnectionError()) as get:
            r = self.criar()
            self.assertEqual(r.status_code, 302)
            html = self.html("/resenha/1/indicacao")
        self.assertEqual(get.call_count, 2)                          # tentou o Plano A e o Plano B
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)  # a resenha foi salva mesmo assim
        self.assertIn("Não consegui buscar indicações", html)
        self.assertIn("Tentar de novo", html)

    def test_erro_http_e_json_invalido(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa([], erro=True)):
            self.assertIsNone(recomendacao.recomendar_livro("fantasia", []))
        recomendacao.limpar_cache()
        ruim = mock.Mock()
        ruim.raise_for_status.return_value = None
        ruim.json.side_effect = ValueError("não é json")
        with mock.patch("clube.recomendacao.requests.get", return_value=ruim):
            self.assertIsNone(recomendacao.recomendar_livro("fantasia", []))

    def test_sessao_guarda_chaves_curtas_e_no_maximo_40(self):
        titulos_longos = [{"title": f"Um título extremamente longo número {i} " + "x" * 80, "author_name": [f"Autor {i}"]}
                          for i in range(200)]
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(titulos_longos)):
            self.criar(titulo="Outro", genero="fantasia")
            for _ in range(25):
                self.c.get("/resenha/1/indicacao")
        with self.c.session_transaction() as s:
            self.assertEqual(len(s["vistos"]), 40)
            self.assertTrue(all(len(v) <= 40 for v in s["vistos"]))
        self.assertEqual(self.c.get("/resenhas").status_code, 200)   # continua logado (cookie não estourou)


if __name__ == "__main__":
    unittest.main()
