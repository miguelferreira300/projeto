import os
from flask import Flask

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento-troque-em-producao")

# Inicializa as tabelas usando o novo nome do ficheiro
from clube import models
models.criar_tabelas()

from clube import rotas