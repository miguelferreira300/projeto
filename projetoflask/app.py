"""Comunidade de Resenhas Geek — MVP.

Rodar:  pip install -r requirements.txt   e depois   python app.py
"""
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import banco
from recomendacao import recomendar_livro

app = Flask(__name__)
# Em produção defina a variável de ambiente SECRET_KEY com um valor longo e aleatório.
app.secret_key = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento-troque-em-producao")

banco.criar_tabelas()


# ---------------------------------------------------------------- utilidades
def login_obrigatorio(rota):
    @wraps(rota)
    def envelope(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return rota(*args, **kwargs)

    return envelope


def validar_resenha(form):
    """Devolve (dados, erros). Validar no servidor é obrigatório: o HTML sozinho não protege."""
    dados = {
        "titulo": form.get("titulo", "").strip(),
        "genero": form.get("genero", "").strip(),
        "texto": form.get("resenha", "").strip(),
    }
    erros = []
    if not 1 <= len(dados["titulo"]) <= 200:
        erros.append("Informe o título (até 200 caracteres).")
    if not 2 <= len(dados["genero"]) <= 60:
        erros.append("Informe o gênero (de 2 a 60 caracteres).")
    if not 10 <= len(dados["texto"]) <= 3000:
        erros.append("A resenha deve ter entre 10 e 3000 caracteres.")
    return dados, erros


@app.template_filter("data_br")
def data_br(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor or ""


# --------------------------------------------------------------------- acesso
@app.route("/", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("resenhas"))
    if request.method == "POST":
        nome = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        usuario = banco.buscar_usuario_por_nome(nome)
        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["usuario"] = usuario["nome"]
            session["vistos"] = []
            return redirect(url_for("nova_resenha"))
        flash("Usuário ou senha inválidos.")
    return render_template("login.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if "usuario_id" in session:
        return redirect(url_for("resenhas"))
    if request.method == "POST":
        nome = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        erros = []
        if not 3 <= len(nome) <= 30:
            erros.append("O usuário deve ter de 3 a 30 caracteres.")
        if len(senha) < 6:
            erros.append("A senha deve ter pelo menos 6 caracteres.")
        if not erros:
            try:
                novo_id = banco.criar_usuario(nome, generate_password_hash(senha))
            except sqlite3.IntegrityError:
                erros.append("Esse nome de usuário já está em uso.")
            else:
                session.clear()
                session["usuario_id"] = novo_id
                session["usuario"] = nome
                session["vistos"] = []
                return redirect(url_for("nova_resenha"))
        for erro in erros:
            flash(erro)
    return render_template("registro.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------- resenhas
@app.route("/resenhas")
@login_obrigatorio
def resenhas():
    return render_template("resenhas.html", resenhas=banco.listar_resenhas(session["usuario_id"]))


@app.route("/resenha", methods=["GET", "POST"])
@login_obrigatorio
def nova_resenha():
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=False), 400
        novo_id = banco.criar_resenha(session["usuario_id"], dados["titulo"], dados["genero"], dados["texto"])
        # Redireciona (em vez de renderizar direto) para que F5 não salve a resenha duas vezes.
        return redirect(url_for("indicacao", resenha_id=novo_id))
    return render_template("resenha_form.html", dados={}, editando=False)


@app.route("/resenha/<int:resenha_id>/indicacao")
@login_obrigatorio
def indicacao(resenha_id):
    resenha = banco.buscar_resenha(resenha_id, session["usuario_id"])
    if resenha is None:
        abort(404)
    vistos = session.get("vistos", [])
    ja_conhecidos = vistos + banco.titulos_do_usuario(session["usuario_id"])
    livro = recomendar_livro(resenha["genero"], ja_conhecidos)
    if livro:
        session["vistos"] = (vistos + [livro["titulo"]])[-50:]  # guarda só os 50 últimos
    return render_template("resultado.html", resenha=resenha, recomendacao=livro)


@app.route("/resenha/<int:resenha_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_resenha(resenha_id):
    resenha = banco.buscar_resenha(resenha_id, session["usuario_id"])
    if resenha is None:
        abort(404)
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=True), 400
        banco.atualizar_resenha(resenha_id, session["usuario_id"], dados["titulo"], dados["genero"], dados["texto"])
        flash("Resenha atualizada.")
        return redirect(url_for("resenhas"))
    dados = {"titulo": resenha["titulo"], "genero": resenha["genero"], "texto": resenha["texto"]}
    return render_template("resenha_form.html", dados=dados, editando=True)


@app.route("/resenha/<int:resenha_id>/excluir", methods=["POST"])
@login_obrigatorio
def excluir_resenha(resenha_id):
    if not banco.excluir_resenha(resenha_id, session["usuario_id"]):
        abort(404)
    flash("Resenha excluída.")
    return redirect(url_for("resenhas"))


if __name__ == "__main__":
    app.run(debug=True)
