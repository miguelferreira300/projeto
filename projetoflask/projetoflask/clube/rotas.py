import sqlite3
from datetime import datetime
from functools import wraps

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Importa a instância do Flask e as classes Active Record do próprio pacote
from clube import app, models
from clube.recomendacao import recomendar_livro


# ---------------------------------------------------------------- utilidades
def login_obrigatorio(rota):
    @wraps(rota)
    def envelope(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return rota(*args, **kwargs)
    return envelope


def validar_resenha(form):
    """Devolve (dados, erros). Validar no servidor é obrigatório."""
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
        
        # Busca o objeto Usuario na base de dados
        usuario = models.Usuario.buscar_por_nome(nome)
        if usuario and check_password_hash(usuario.senha_hash, senha):
            session.clear()
            session["usuario_id"] = usuario.id
            session["usuario"] = usuario.nome
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
                # Instancia e guarda o novo utilizador usando Active Record
                novo_usuario = models.Usuario(nome=nome, senha_hash=generate_password_hash(senha))
                novo_id = novo_usuario.guardar()
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
    # Obtém uma lista de objetos Resenha em vez de dicionários
    lista_resenhas = models.Resenha.listar_do_usuario(session["usuario_id"])
    return render_template("resenhas.html", resenhas=lista_resenhas)


@app.route("/resenha", methods=["GET", "POST"])
@login_obrigatorio
def nova_resenha():
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=False), 400
        
        # Cria e guarda a resenha como um objeto
        nova_resenha_obj = models.Resenha(
            usuario_id=session["usuario_id"], 
            titulo=dados["titulo"], 
            genero=dados["genero"], 
            texto=dados["texto"]
        )
        novo_id = nova_resenha_obj.guardar()
        
        return redirect(url_for("indicacao", resenha_id=novo_id))
    return render_template("resenha_form.html", dados={}, editando=False)


@app.route("/resenha/<int:resenha_id>/indicacao")
@login_obrigatorio
def indicacao(resenha_id):
    resenha = models.Resenha.buscar(resenha_id, session["usuario_id"])
    if resenha is None:
        abort(404)
        
    vistos = session.get("vistos", [])
    ja_conhecidos = vistos + models.Resenha.titulos_do_usuario(session["usuario_id"])
    
    livro = recomendar_livro(resenha.genero, ja_conhecidos)
    if livro:
        session["vistos"] = (vistos + [livro["titulo"]])[-50:]  # guarda só os 50 últimos
        
    return render_template("resultado.html", resenha=resenha, recomendacao=livro)


@app.route("/resenha/<int:resenha_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_resenha(resenha_id):
    resenha = models.Resenha.buscar(resenha_id, session["usuario_id"])
    if resenha is None:
        abort(404)
        
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=True), 400
            
        # Modifica os atributos do objeto e atualiza na base de dados
        resenha.titulo = dados["titulo"]
        resenha.genero = dados["genero"]
        resenha.texto = dados["texto"]
        resenha.guardar()
        
        flash("Resenha atualizada.")
        return redirect(url_for("resenhas"))
        
    dados = {"titulo": resenha.titulo, "genero": resenha.genero, "texto": resenha.texto}
    return render_template("resenha_form.html", dados=dados, editando=True)


@app.route("/resenha/<int:resenha_id>/excluir", methods=["POST"])
@login_obrigatorio
def excluir_resenha(resenha_id):
    if not models.Resenha.apagar(resenha_id, session["usuario_id"]):
        abort(404)
    flash("Resenha excluída.")
    return redirect(url_for("resenhas"))