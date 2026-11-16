"""Middleware de autenticação (Aula 12)."""
from functools import wraps

from flask import flash, g, redirect, session, url_for

from app.models.usuario import Usuario


def login_required(rota):
    """Protege a rota: confere no BANCO se session['user_id'] existe e expõe o usuário em g.usuario."""
    @wraps(rota)
    def envelope(*args, **kwargs):
        user_id = session.get("user_id")
        usuario = Usuario.buscar_por_id(user_id) if user_id else None
        if usuario is None:
            session.clear()  # sessão antiga/forjada ou usuário removido
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        g.usuario = usuario
        return rota(*args, **kwargs)
    return envelope
