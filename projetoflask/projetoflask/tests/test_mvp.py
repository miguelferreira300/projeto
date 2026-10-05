"""Rodar:  python -m unittest discover -s tests -v   (não usa internet)"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Adiciona a raiz do projeto ao path para encontrar o pacote 'clube'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isola o banco de dados antes de inicializar as rotas
_tmp = tempfile.TemporaryDirectory()
from clube import models
models.CAMINHO = Path(_tmp.name) / "teste.db"

from clube import recomendacao
from clube import app as modulo_app


class RespostaFalsa:
    def __init__(self, docs, erro=False):
        self._docs, self._erro = docs, erro

    def raise_for_status(self):
        if self._erro:
            raise recomendacao.requests.HTTPError("500")

    def json(self):
        return {"docs": self._docs}


DOCS = [
    {"title": "Eragon", "author_name": ["Christopher Paolini"], "cover_i": 11},
    {"title": "O Silmarillion", "author_name": ["J. R. R. Tolkien"]},          
    {"title": "Sem Autor"},                                                     
]


class Base(unittest.TestCase):
    def setUp(self):
        if models.CAMINHO.exists():
            models.CAMINHO.unlink()
        models.criar_tabelas()
        modulo_app.config["TESTING"] = True
        self.c = modulo_app.test_client()

    def registrar(self, nome="ana", senha="segredo1"):
        return self.c.post("/registro", data={"usuario": nome, "senha": senha})

    def criar(self, titulo="O Hobbit", genero="fantasia", texto="Aventura incrível com dragões!"):
        return self.c.post("/resenha", data={"titulo": titulo, "genero": genero, "resenha": texto})


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
        h = models.Usuario.buscar_por_nome("ana").senha_hash
        self.assertNotIn("segredo1", h)

    def test_usuario_duplicado_e_validacao(self):
        self.registrar()
        outro = self.app_limpo().post("/registro", data={"usuario": "Ana", "senha": "segredo1"})
        self.assertIn("já está em uso", outro.get_data(as_text=True))
        curto = self.app_limpo().post("/registro", data={"usuario": "ab", "senha": "123"})
        self.assertEqual(curto.status_code, 200)
        self.assertIsNone(models.Usuario.buscar_por_nome("ab"))

    def app_limpo(self):
        return modulo_app.test_client()


class TestCrud(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_ciclo_completo(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)):
            r = self.criar()
        self.assertEqual(r.status_code, 302)                                 
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)
        self.assertIn("O Hobbit", self.c.get("/resenhas").get_data(as_text=True))

        r = self.c.post("/resenha/1/editar", data={"titulo": "O Hobbit (2ª ed.)", "genero": "aventura",
                                                   "resenha": "Releitura ainda melhor que a primeira."})
        self.assertEqual(r.status_code, 302)
        
        editada = models.Resenha.buscar(1, 1)
        # O teste agora acede às propriedades do objeto Active Record
        self.assertEqual((editada.titulo, editada.genero), ("O Hobbit (2ª ed.)", "aventura"))

        self.assertEqual(self.c.post("/resenha/1/excluir").status_code, 302)
        self.assertIsNone(models.Resenha.buscar(1, 1))

    def test_validacao_no_servidor(self):
        r = self.criar(titulo="  ", genero="x", texto="curto")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 0)
        html = r.get_data(as_text=True)
        self.assertIn("Informe o título", html)

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
        self.assertEqual(outro.post("/resenha/1/editar", data={"titulo": "hack", "genero": "xx",
                                                              "resenha": "1234567890"}).status_code, 404)
        
        self.assertEqual(models.Resenha.buscar(1, 1).titulo, "O Hobbit")
        self.assertNotIn("O Hobbit", outro.get("/resenhas").get_data(as_text=True))

    def test_sql_injection_e_xss(self):
        self.criar(titulo="'); DROP TABLE resenhas; --", texto="<script>alert(1)</script> texto longo")
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)                   
        html = self.c.get("/resenhas").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_apagar_usuario_apaga_resenhas_fk(self):
        self.criar()
        # Validação usando o novo Context Manager da conexão
        with models.ConexaoBD() as bd:
            bd.execute("DELETE FROM usuarios WHERE id = 1")
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 0)                   

    def test_fk_impede_resenha_sem_dono(self):
        with self.assertRaises(sqlite3.IntegrityError):
            nova_resenha = models.Resenha(usuario_id=999, titulo="x", genero="yy", texto="texto qualquer aqui")
            nova_resenha.guardar()


class TestRecomendacao(Base):
    def setUp(self):
        super().setUp()
        self.registrar()

    def test_indicacao_traduz_genero_e_nao_repete_o_que_ja_leu(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)) as get:
            self.criar(titulo="Eragon", genero="Fantasia")
            html = self.c.get("/resenha/1/indicacao").get_data(as_text=True)
        
        self.assertEqual(get.call_args.kwargs["params"]["subject"], "fantasy")
        self.assertIn("O Silmarillion", html)            
        self.assertNotIn("Sem Autor", html)
        self.assertIn("Sem+Capa", html)

    def test_genero_com_acento_e_espaco(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa(DOCS)) as get:
            recomendacao.recomendar_livro("Ficção Científica", [])
        self.assertEqual(get.call_args.kwargs["params"]["subject"], "science_fiction")

    def test_api_fora_do_ar_nao_quebra(self):
        import requests
        with mock.patch("clube.recomendacao.requests.get", side_effect=requests.ConnectionError()):
            r = self.criar()
            self.assertEqual(r.status_code, 302)
            
        self.assertEqual(len(models.Resenha.listar_do_usuario(1)), 1)

    def test_erro_http_e_json_invalido(self):
        with mock.patch("clube.recomendacao.requests.get", return_value=RespostaFalsa([], erro=True)):
            self.assertIsNone(recomendacao.recomendar_livro("fantasia", []))
            
        ruim = mock.Mock()
        ruim.raise_for_status.return_value = None
        ruim.json.side_effect = ValueError("não é json")
        with mock.patch("clube.recomendacao.requests.get", return_value=ruim):
            self.assertIsNone(recomendacao.recomendar_livro("fantasia", []))

if __name__ == "__main__":
    unittest.main()