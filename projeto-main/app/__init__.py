"""Instância do Flask, secret_key, logger, tratamento de erros e registro dos Blueprints."""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request

from app.db import BASE_DIR

app = Flask(__name__, template_folder="views")
# Em produção defina SECRET_KEY no ambiente; o valor abaixo serve apenas para desenvolvimento.
app.secret_key = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento-troque-em-producao")


# ------------------------------------------------------------------- logs
def _configurar_logs():
    app.logger.setLevel(logging.INFO)
    if os.environ.get("BANCO_DB"):  # execução de testes: sem arquivo de log
        return
    pasta = os.path.join(BASE_DIR, "logs")
    os.makedirs(pasta, exist_ok=True)
    arquivo = RotatingFileHandler(os.path.join(pasta, "app.log"), maxBytes=200_000, backupCount=2,
                                  encoding="utf-8")
    arquivo.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    app.logger.addHandler(arquivo)


_configurar_logs()

# ----------------------------------------------------- filtros e contexto
from app.utils.filtros import data_br  # noqa: E402
from app.models.resenha import LIMITE_RESENHAS_POR_HORA  # noqa: E402

app.add_template_filter(data_br, "data_br")


@app.context_processor
def variaveis_dos_templates():
    tema = request.cookies.get("tema", "escuro")  # cookie de preferência de tema
    return {"tema": tema if tema in ("claro", "escuro") else "escuro",
            "limite_por_hora": LIMITE_RESENHAS_POR_HORA}


# ------------------------------------------------------- tratamento de erros
@app.errorhandler(404)
def pagina_nao_encontrada(erro):
    app.logger.warning("404: %s %s", request.method, request.path)
    return render_template("404.html"), 404


@app.errorhandler(403)
def acesso_negado(erro):
    app.logger.warning("403: %s %s", request.method, request.path)
    return render_template("erro.html", codigo=403, titulo="Acesso negado",
                           mensagem="Você não tem permissão para acessar esta página."), 403


@app.errorhandler(500)
def erro_interno(erro):
    app.logger.error("500: %s %s", request.method, request.path)
    return render_template("erro.html", codigo=500, titulo="Algo deu errado",
                           mensagem="Ocorreu um erro inesperado. Tente novamente em instantes."), 500


# ------------------------------------------------------------- blueprints
from app.controllers.auth import auth_bp  # noqa: E402
from app.controllers.main import main_bp  # noqa: E402
from app.controllers.resenhas import resenhas_bp  # noqa: E402
from app.controllers.leitura import leitura_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(resenhas_bp)
app.register_blueprint(leitura_bp)
