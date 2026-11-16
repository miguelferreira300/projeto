"""Ponto de entrada: inicia o servidor Flask."""
import os

from app import app
from app.db import DB_PATH

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Banco de dados não encontrado. Rode primeiro:  python iniciar_bd.py")
    else:
        app.run(debug=True)
