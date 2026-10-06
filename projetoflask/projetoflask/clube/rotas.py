import math
import sqlite3
from datetime import datetime
from functools import wraps

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Importa a instância do Flask e as classes Active Record do próprio pacote
from clube import app, models
from clube.recomendacao import recomendar_livros

POR_PAGINA = 10  # resenhas por página na listagem


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
        "nota": None,
    }
    erros = []
    if not 1 <= len(dados["titulo"]) <= 200:
        erros.append("Informe o título (até 200 caracteres).")
    if not 2 <= len(dados["genero"]) <= 60:
        erros.append("Informe o gênero (de 2 a 60 caracteres).")
    try:
        nota = int(form.get("nota", ""))
        if not 1 <= nota <= 5:
            raise ValueError
        dados["nota"] = nota
    except ValueError:
        erros.append("Escolha uma nota de 1 a 5 estrelas.")
    if not 10 <= len(dados["texto"]) <= 3000:
        erros.append("A resenha deve ter entre 10 e 3000 caracteres.")
    return dados, erros


@app.context_processor
def constantes_dos_templates():
    return {"limite_por_hora": models.LIMITE_RESENHAS_POR_HORA}


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
    usuario_id = session["usuario_id"]
    total = models.Resenha.contar_do_usuario(usuario_id)
    paginas = max(1, math.ceil(total / POR_PAGINA))
    # ?pagina=abc ou fora do intervalo não quebra: cai na primeira/última página
    pagina = min(max(1, request.args.get("pagina", 1, type=int)), paginas)
    lista_resenhas = models.Resenha.listar_do_usuario(usuario_id, pagina, POR_PAGINA)
    return render_template("resenhas.html", resenhas=lista_resenhas, total=total, pagina=pagina, paginas=paginas)


@app.route("/resenha", methods=["GET", "POST"])
@login_obrigatorio
def nova_resenha():
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=False), 400

        try:
            # Cria a resenha e confere o limite de 10 por hora numa operação só
            novo_id = models.Resenha.criar_com_limite(
                usuario_id=session["usuario_id"],
                titulo=dados["titulo"],
                genero=dados["genero"],
                nota=dados["nota"],
                texto=dados["texto"],
            )
        except models.LimiteDeResenhas as e:
            unidade = "minuto" if e.minutos == 1 else "minutos"
            flash(f"Você atingiu o limite de {models.LIMITE_RESENHAS_POR_HORA} resenhas por hora. "
                  f"Tente novamente em {e.minutos} {unidade}. Seu texto foi mantido abaixo.")
            return render_template("resenha_form.html", dados=dados, editando=False), 429

        flash("Resenha salva com sucesso!")
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

    # None = API fora do ar | [] = nada novo para esse gênero | lista = indicações
    livros = recomendar_livros(resenha.genero, ja_conhecidos)
    if livros:
        # Guarda só uma chave curta de cada título (cabe no cookie) e só as 40 últimas
        session["vistos"] = (vistos + [livro["chave"] for livro in livros])[-40:]

    return render_template("resultado.html", resenha=resenha, recomendacoes=livros)


@app.route("/resenha/<int:resenha_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_resenha(resenha_id):
    resenha = models.Resenha.buscar(resenha_id, session["usuario_id"])
    if resenha is None:
        abort(404)
    pagina = request.args.get("pagina", 1, type=int)  # para voltar à mesma página da lista

    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro)
            return render_template("resenha_form.html", dados=dados, editando=True, pagina=pagina), 400

        # Modifica os atributos do objeto e atualiza na base de dados
        resenha.titulo = dados["titulo"]
        resenha.genero = dados["genero"]
        resenha.nota = dados["nota"]
        resenha.texto = dados["texto"]
        resenha.guardar()

        flash("Resenha atualizada.")
        return redirect(url_for("resenhas", pagina=pagina))

    dados = {"titulo": resenha.titulo, "genero": resenha.genero, "nota": resenha.nota, "texto": resenha.texto}
    return render_template("resenha_form.html", dados=dados, editando=True, pagina=pagina)


@app.route("/resenha/<int:resenha_id>/excluir", methods=["POST"])
@login_obrigatorio
def excluir_resenha(resenha_id):
    if not models.Resenha.apagar(resenha_id, session["usuario_id"]):
        abort(404)
    flash("Resenha excluída.")
    # Volta à mesma página; se ela deixou de existir, /resenhas corrige sozinha
    return redirect(url_for("resenhas", pagina=request.form.get("pagina", 1, type=int)))
