import math

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   session, url_for)

from app.models.item_leitura import ItemLeitura
from app.models.resenha import LIMITE_RESENHAS_POR_HORA, LimiteDeResenhas, Resenha
from app.utils.auth_middleware import login_required
from app.utils.recomendacao import recomendar_livros
from app.utils.validacao import validar_resenha

resenhas_bp = Blueprint("resenhas", __name__)

POR_PAGINA = 10


@resenhas_bp.route("/resenhas")
@login_required
def listar():
    # filtros vindos da query string: ?q=...&genero=...&nota=...&pagina=...
    busca = request.args.get("q", "").strip()
    genero = request.args.get("genero", "").strip()
    nota = request.args.get("nota", type=int)
    if nota is not None and not 1 <= nota <= 5:
        nota = None

    total = Resenha.contar_por_usuario(g.usuario.id, busca, genero, nota)
    paginas = max(1, math.ceil(total / POR_PAGINA))
    pagina = min(max(1, request.args.get("pagina", 1, type=int)), paginas)  # ?pagina=abc não quebra
    lista = Resenha.listar_por_usuario(g.usuario.id, pagina, POR_PAGINA, busca, genero, nota)

    filtros = {k: v for k, v in (("q", busca), ("genero", genero), ("nota", nota)) if v not in ("", None)}
    return render_template(
        "resenhas.html", resenhas=lista, total=total, pagina=pagina, paginas=paginas,
        filtros=filtros, busca=busca, genero_atual=genero, nota_atual=nota,
        generos=Resenha.generos_do_usuario(g.usuario.id),
    )


@resenhas_bp.route("/resenha", methods=["GET", "POST"])
@login_required
def nova():
    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("resenha_form.html", dados=dados, editando=False), 400

        try:
            novo_id = Resenha.criar_com_limite(
                usuario_id=g.usuario.id, titulo=dados["titulo"], genero=dados["genero"],
                nota=dados["nota"], texto=dados["texto"],
            )
        except LimiteDeResenhas as e:
            unidade = "minuto" if e.minutos == 1 else "minutos"
            current_app.logger.warning("Limite de resenhas por hora atingido: usuario_id=%s", g.usuario.id)
            flash(f"Você atingiu o limite de {LIMITE_RESENHAS_POR_HORA} resenhas por hora. "
                  f"Tente novamente em {e.minutos} {unidade}. Seu texto foi mantido abaixo.", "warning")
            return render_template("resenha_form.html", dados=dados, editando=False), 429

        current_app.logger.info("Resenha criada: id=%s usuario_id=%s", novo_id, g.usuario.id)
        flash("Resenha salva com sucesso!", "success")
        return redirect(url_for("resenhas.indicacao", resenha_id=novo_id))
    return render_template("resenha_form.html", dados={}, editando=False)


@resenhas_bp.route("/resenha/<int:resenha_id>/indicacao")
@login_required
def indicacao(resenha_id):
    resenha = Resenha.buscar_por_id(resenha_id, g.usuario.id)
    if resenha is None:
        abort(404)

    vistos = session.get("vistos", [])
    ja_conhecidos = vistos + Resenha.titulos_do_usuario(g.usuario.id)

    # None = API fora do ar | [] = nada novo para esse gênero | lista = indicações
    livros = recomendar_livros(resenha.genero, ja_conhecidos)
    if livros:
        session["vistos"] = (vistos + [livro["chave"] for livro in livros])[-40:]
    return render_template("resultado.html", resenha=resenha, recomendacoes=livros)


@resenhas_bp.route("/resenha/<int:resenha_id>/editar", methods=["GET", "POST"])
@login_required
def editar(resenha_id):
    resenha = Resenha.buscar_por_id(resenha_id, g.usuario.id)
    if resenha is None:
        abort(404)
    pagina = request.args.get("pagina", 1, type=int)

    if request.method == "POST":
        dados, erros = validar_resenha(request.form)
        if erros:
            for erro in erros:
                flash(erro, "danger")
            return render_template("resenha_form.html", dados=dados, editando=True, pagina=pagina), 400

        resenha.titulo = dados["titulo"]
        resenha.genero = dados["genero"]
        resenha.nota = dados["nota"]
        resenha.texto = dados["texto"]
        resenha.atualizar()
        current_app.logger.info("Resenha editada: id=%s usuario_id=%s", resenha.id, g.usuario.id)
        flash("Resenha atualizada.", "success")
        return redirect(url_for("resenhas.listar", pagina=pagina))

    dados = {"titulo": resenha.titulo, "genero": resenha.genero, "nota": resenha.nota, "texto": resenha.texto}
    return render_template("resenha_form.html", dados=dados, editando=True, pagina=pagina)


@resenhas_bp.route("/resenha/<int:resenha_id>/excluir", methods=["POST"])
@login_required
def excluir(resenha_id):
    resenha = Resenha.buscar_por_id(resenha_id, g.usuario.id)  # só encontra se for do usuário logado
    if resenha is None:
        abort(404)
    resenha.excluir()
    current_app.logger.info("Resenha excluída: id=%s usuario_id=%s", resenha_id, g.usuario.id)
    flash("Resenha excluída.", "success")
    return redirect(url_for("resenhas.listar", pagina=request.form.get("pagina", 1, type=int)))


@resenhas_bp.route("/resenha/<int:resenha_id>/indicacao/adicionar", methods=["POST"])
@login_required
def adicionar_indicacao(resenha_id):
    """Salva um livro indicado na Lista de Leitura (relaciona o item à resenha de origem)."""
    resenha = Resenha.buscar_por_id(resenha_id, g.usuario.id)
    if resenha is None:
        abort(404)
    titulo = request.form.get("titulo", "").strip()[:200]
    autor = request.form.get("autor", "").strip()[:120]
    if not titulo or not autor:
        flash("Não foi possível adicionar esse livro à lista.", "danger")
    elif ItemLeitura.existe_titulo(g.usuario.id, titulo):
        flash(f"\"{titulo}\" já está na sua lista de leitura.", "info")
    else:
        item = ItemLeitura(usuario_id=g.usuario.id, titulo=titulo, autor=autor, resenha_id=resenha.id)
        item.salvar()
        current_app.logger.info("Item de leitura criado a partir de indicação: id=%s usuario_id=%s",
                                item.id, g.usuario.id)
        flash(f"\"{titulo}\" foi adicionado à sua lista de leitura.", "success")
    return redirect(url_for("resenhas.indicacao", resenha_id=resenha.id))
