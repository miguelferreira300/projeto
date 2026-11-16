from flask import (Blueprint, current_app, flash, make_response, redirect, render_template,
                   request, session, url_for)

from app.models.usuario import Usuario, UsuarioJaExiste
from app.utils.validacao import validar_registro

auth_bp = Blueprint("auth", __name__)

COOKIE_ULTIMO_USUARIO = "ultimo_usuario"
UM_MES = 30 * 24 * 60 * 60


def _iniciar_sessao(usuario):
    session.clear()  # descarta qualquer sessão anterior
    session["user_id"] = usuario.id
    session["username"] = usuario.username
    session["vistos"] = []


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("resenhas.listar"))

    ultimo_usuario = request.cookies.get(COOKIE_ULTIMO_USUARIO, "")  # cookie: lembra o último usuário
    if request.method == "POST":
        username = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        usuario = Usuario.buscar_por_username(username)
        if usuario and usuario.verificar_senha(senha):
            _iniciar_sessao(usuario)
            current_app.logger.info("Login realizado: usuario_id=%s (%s)", usuario.id, usuario.username)
            flash(f"Bem-vindo(a), {usuario.username}!", "success")
            resposta = make_response(redirect(url_for("resenhas.nova")))
            resposta.set_cookie(COOKIE_ULTIMO_USUARIO, usuario.username, max_age=UM_MES, samesite="Lax")
            return resposta
        current_app.logger.warning("Falha de autenticação para o usuário '%s' (IP %s)", username, request.remote_addr)
        flash("Usuário ou senha inválidos.", "danger")
        ultimo_usuario = username
    return render_template("login.html", ultimo_usuario=ultimo_usuario)


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if "user_id" in session:
        return redirect(url_for("resenhas.listar"))
    if request.method == "POST":
        dados, erros = validar_registro(request.form)
        if not erros:
            usuario = Usuario(username=dados["username"])
            usuario.definir_senha(dados["senha"])  # guarda só o hash
            try:
                usuario.salvar()
            except UsuarioJaExiste:
                erros.append("Esse nome de usuário já está em uso.")
            else:
                _iniciar_sessao(usuario)
                current_app.logger.info("Novo usuário cadastrado: usuario_id=%s (%s)", usuario.id, usuario.username)
                flash("Conta criada com sucesso!", "success")
                resposta = make_response(redirect(url_for("resenhas.nova")))
                resposta.set_cookie(COOKIE_ULTIMO_USUARIO, usuario.username, max_age=UM_MES, samesite="Lax")
                return resposta
        for erro in erros:
            flash(erro, "danger")
        return render_template("registro.html", username=dados["username"]), 400
    return render_template("registro.html", username="")


@auth_bp.route("/logout")
def logout():
    username = session.get("username")
    session.clear()
    current_app.logger.info("Logout: %s", username)
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("auth.login"))
