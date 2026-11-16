from urllib.parse import urlparse

from flask import Blueprint, make_response, redirect, request, url_for

main_bp = Blueprint("main", __name__)

TEMAS = ("escuro", "claro")
UM_ANO = 365 * 24 * 60 * 60


@main_bp.route("/tema", methods=["POST"])
def alternar_tema():
    """Cookie de preferência: guarda o tema (claro/escuro) por 1 ano."""
    atual = request.cookies.get("tema", "escuro")
    novo = request.form.get("tema") or ("claro" if atual == "escuro" else "escuro")
    if novo not in TEMAS:
        novo = "escuro"

    destino = url_for("auth.login")
    origem = urlparse(request.referrer or "")
    if origem.netloc == request.host and origem.path:  # só volta para páginas do próprio site
        destino = origem.path + (f"?{origem.query}" if origem.query else "")

    resposta = make_response(redirect(destino))
    resposta.set_cookie("tema", novo, max_age=UM_ANO, samesite="Lax")
    return resposta
