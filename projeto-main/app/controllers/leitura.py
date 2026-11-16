import math

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   url_for)

from app.models.item_leitura import PRIORIDADES, STATUS, ItemLeitura
from app.utils.auth_middleware import login_required
from app.utils.validacao import validar_item_leitura

leitura_bp = Blueprint("leitura", __name__, url_prefix="/leitura")

POR_PAGINA = 10


@leitura_bp.route("/")
@login_required
def listar():
    busca = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    if status not in STATUS:
        status = ""

    total = ItemLeitura.contar_por_usuario(g.usuario.id, busca, status)
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(max(1, request.args.get("pagina", 1, type=int)), paginas)
    itens = ItemLeitura.listar_por_usuario(g.usuario.id, pagina, POR_PAGINA, busca, status)

    filtros = {k: v for k, v in (("q", busca), ("status", status)) if v}
    return render_template("leitura.html", itens=itens, total=total, pagina=pagina, paginas=paginas,
                           filtros=filtros, busca=busca, status_atual=status)


@leitura_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if request.method == "POST":
        dados, erros = validar_item_leitura(request.form)
        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("leitura_form.html", dados=dados, editando=False,
                                   status=STATUS, prioridades=PRIORIDADES), 400
        item = ItemLeitura(usuario_id=g.usuario.id, **dados)
        item.salvar()
        current_app.logger.info("Item de leitura criado: id=%s usuario_id=%s", item.id, g.usuario.id)
        flash("Livro adicionado à lista de leitura!", "success")
        return redirect(url_for("leitura.listar"))
    return render_template("leitura_form.html", dados={"status": "quero_ler", "prioridade": 2},
                           editando=False, status=STATUS, prioridades=PRIORIDADES)


@leitura_bp.route("/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def editar(item_id):
    item = ItemLeitura.buscar_por_id(item_id, g.usuario.id)
    if item is None:
        abort(404)
    pagina = request.args.get("pagina", 1, type=int)

    if request.method == "POST":
        dados, erros = validar_item_leitura(request.form)
        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("leitura_form.html", dados=dados, editando=True, pagina=pagina,
                                   status=STATUS, prioridades=PRIORIDADES), 400
        item.titulo = dados["titulo"]
        item.autor = dados["autor"]
        item.status = dados["status"]
        item.prioridade = dados["prioridade"]
        item.observacao = dados["observacao"]
        item.atualizar()
        current_app.logger.info("Item de leitura editado: id=%s usuario_id=%s", item.id, g.usuario.id)
        flash("Item atualizado.", "success")
        return redirect(url_for("leitura.listar", pagina=pagina))

    dados = {"titulo": item.titulo, "autor": item.autor, "status": item.status,
             "prioridade": item.prioridade, "observacao": item.observacao}
    return render_template("leitura_form.html", dados=dados, editando=True, pagina=pagina,
                           status=STATUS, prioridades=PRIORIDADES)


@leitura_bp.route("/<int:item_id>/excluir", methods=["POST"])
@login_required
def excluir(item_id):
    item = ItemLeitura.buscar_por_id(item_id, g.usuario.id)
    if item is None:
        abort(404)
    item.excluir()
    current_app.logger.info("Item de leitura excluído: id=%s usuario_id=%s", item_id, g.usuario.id)
    flash("Item removido da lista de leitura.", "success")
    return redirect(url_for("leitura.listar", pagina=request.form.get("pagina", 1, type=int)))
