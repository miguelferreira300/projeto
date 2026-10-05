"""Indicação de livro pela API da Open Library, a partir do gênero da resenha."""
import random
import unicodedata

import requests

URL = "https://openlibrary.org/search.json"

# A Open Library indexa os assuntos em inglês: traduzimos o que a pessoa digita.
TRADUCAO = {
    "fantasia": "fantasy",
    "ficcao": "fiction",
    "ficcao cientifica": "science_fiction",
    "terror": "horror",
    "suspense": "thriller",
    "misterio": "mystery",
    "policial": "mystery",
    "romance": "romance",
    "aventura": "adventure",
    "quadrinhos": "comics",
    "hq": "comics",
    "hqs": "comics",
    "manga": "manga",
    "distopia": "dystopia",
    "historia": "history",
    "biografia": "biography",
    "poesia": "poetry",
    "infantil": "children",
    "classicos": "classics",
    "autoajuda": "self-help",
    "filosofia": "philosophy",
    "humor": "humor",
    "super-heroi": "superheroes",
    "super-herois": "superheroes",
}


def _limpar(texto):
    """minúsculas e sem acento: 'Ficção Científica' -> 'ficcao cientifica'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def recomendar_livro(genero, titulos_ja_vistos):
    """Devolve {'titulo', 'autor', 'capa_url'} ou None se não achar / API fora do ar."""
    limpo = _limpar(genero)
    assunto = TRADUCAO.get(limpo, limpo.replace(" ", "_"))
    vistos = {_limpar(t) for t in titulos_ja_vistos}

    try:
        resposta = requests.get(
            URL,
            params={"subject": assunto, "limit": 30, "fields": "title,author_name,cover_i"},
            headers={"User-Agent": "ResenhasGeek/1.0 (projeto escolar)"},
            timeout=5,
        )
        resposta.raise_for_status()
        docs = resposta.json().get("docs", [])
    except (requests.RequestException, ValueError):
        return None

    opcoes = []
    for livro in docs:
        titulo = livro.get("title")
        autores = livro.get("author_name")
        if not titulo or not autores or _limpar(titulo) in vistos:
            continue
        capa = livro.get("cover_i")
        opcoes.append(
            {
                "titulo": titulo,
                "autor": autores[0],
                "capa_url": f"https://covers.openlibrary.org/b/id/{capa}-M.jpg" if capa else "",
            }
        )
    return random.choice(opcoes) if opcoes else None
