"""Validação dos dados da requisição no servidor. Cada função devolve (dados, erros)."""
from app.models.item_leitura import PRIORIDADES, STATUS


def validar_registro(form):
    dados = {"username": form.get("usuario", "").strip(), "senha": form.get("senha", "")}
    erros = []
    if not 3 <= len(dados["username"]) <= 30:
        erros.append("O usuário deve ter de 3 a 30 caracteres.")
    if len(dados["senha"]) < 6:
        erros.append("A senha deve ter pelo menos 6 caracteres.")
    return dados, erros


def validar_resenha(form):
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


def validar_item_leitura(form):
    dados = {
        "titulo": form.get("titulo", "").strip(),
        "autor": form.get("autor", "").strip(),
        "status": form.get("status", "").strip(),
        "prioridade": None,
        "observacao": form.get("observacao", "").strip(),
    }
    erros = []
    if not 1 <= len(dados["titulo"]) <= 200:
        erros.append("Informe o título (até 200 caracteres).")
    if not 1 <= len(dados["autor"]) <= 120:
        erros.append("Informe o autor (até 120 caracteres).")
    if dados["status"] not in STATUS:
        erros.append("Escolha um status válido.")
    try:
        prioridade = int(form.get("prioridade", ""))
        if prioridade not in PRIORIDADES:
            raise ValueError
        dados["prioridade"] = prioridade
    except ValueError:
        erros.append("Escolha uma prioridade válida (alta, média ou baixa).")
    if len(dados["observacao"]) > 500:
        erros.append("A observação pode ter no máximo 500 caracteres.")
    return dados, erros
