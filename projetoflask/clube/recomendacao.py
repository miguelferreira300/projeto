import random
import time
import unicodedata
import urllib3
import requests

# Desativa alertas de segurança (essencial, pois o proxy da escola interceta certificados SSL)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://openlibrary.org/search.json"

TRADUCAO = {
    "fantasia": "fantasy", "ficcao": "fiction", "ficcao cientifica": "science_fiction",
    "terror": "horror", "suspense": "thriller", "misterio": "mystery",
    "policial": "mystery", "romance": "romance", "aventura": "adventure",
    "quadrinhos": "comics", "hq": "comics", "hqs": "comics",
    "manga": "manga", "distopia": "dystopia", "historia": "history",
    "biografia": "biography", "poesia": "poetry", "infantil": "children",
    "classicos": "classics", "autoajuda": "self-help", "filosofia": "philosophy",
    "humor": "humor", "super-heroi": "superheroes", "super-herois": "superheroes",
}

# As credenciais exatas que extraiu do terminal do Linux
PROXY_ESCOLA = {
    "http": "http://proxy.spo.ifsp.edu.br:3128/",
    "https": "http://proxy.spo.ifsp.edu.br:3128/"
}

# Cache em memória: "Novas indicações" não precisa ir à internet de novo (e, na escola,
# esperar o Plano A estourar o tempo limite) a cada clique.
CACHE_SEGUNDOS = 600
_cache = {}  # assunto -> (momento_da_busca, docs)


def limpar_cache():
    _cache.clear()


def _limpar(texto):
    """Minúsculas e sem acento: 'Ficção Científica' -> 'ficcao cientifica'."""
    if not texto: return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _chave(titulo):
    """Identifica um título de forma curta (cabe folgado no cookie de sessão)."""
    return _limpar(titulo)[:40]


def _buscar_docs(params, headers):
    """Devolve a lista de livros da API, ou None se não conseguiu por nenhum dos dois caminhos."""
    # PLANO A: Tenta ligar diretamente à internet (Funciona no seu Windows em casa)
    try:
        # proxies={"http": None, "https": None} força a ignorar qualquer configuração local do Windows
        resposta = requests.get(URL, params=params, headers=headers, timeout=5, proxies={"http": None, "https": None}, verify=False)
        resposta.raise_for_status()
        dados = resposta.json()
        return dados.get("docs", []) if isinstance(dados, dict) else []

    except (requests.exceptions.RequestException, ValueError):
        # PLANO B: Se a ligação cair na firewall, injeta o proxy do IFSP (Funciona no Linux da escola)
        try:
            resposta = requests.get(URL, params=params, headers=headers, timeout=5, proxies=PROXY_ESCOLA, verify=False)
            resposta.raise_for_status()
            dados = resposta.json()
            return dados.get("docs", []) if isinstance(dados, dict) else []

        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"DEBUG: Falhou a ligação direta e a ligação via proxy. Erro: {e}")
            return None


def recomendar_livros(genero, titulos_ja_vistos, quantidade=3):
    """Sorteia até `quantidade` livros do gênero.

    Retorna None se a API não respondeu; lista vazia se não sobrou nenhum livro novo.
    Cada livro: titulo, autor, capa_url, ano, nota_media, n_notas, chave.
    """
    limpo = _limpar(genero)
    assunto = TRADUCAO.get(limpo, limpo.replace(" ", "_"))
    vistos = {_chave(t) for t in titulos_ja_vistos}

    docs = None
    em_cache = _cache.get(assunto)
    if em_cache and time.time() - em_cache[0] < CACHE_SEGUNDOS:
        docs = em_cache[1]
    else:
        params = {"subject": assunto, "limit": 50,
                  "fields": "title,author_name,cover_i,first_publish_year,ratings_average,ratings_count"}
        headers = {"User-Agent": "ResenhasGeek/1.0"}
        docs = _buscar_docs(params, headers)
        if docs is None:
            return None  # falha não vai para o cache: o próximo clique tenta de novo
        if len(_cache) >= 100:  # limite simples para o cache não crescer sem fim
            _cache.clear()
        _cache[assunto] = (time.time(), docs)

    # Processa os resultados da API: só livros com título e autor, ainda não vistos
    opcoes = []
    chaves_na_busca = set()
    for livro in docs:
        titulo = livro.get("title")
        autores = livro.get("author_name")
        if not titulo or not autores:
            continue
        chave = _chave(titulo)
        if chave in vistos or chave in chaves_na_busca:
            continue
        chaves_na_busca.add(chave)

        capa = livro.get("cover_i")
        media = livro.get("ratings_average")
        qtd = livro.get("ratings_count")
        media = round(media, 1) if isinstance(media, (int, float)) else None
        qtd = qtd if isinstance(qtd, int) else 0
        ano = livro.get("first_publish_year")
        opcoes.append({
            "titulo": titulo,
            "autor": autores[0],
            "capa_url": f"https://covers.openlibrary.org/b/id/{capa}-M.jpg" if capa else "",
            "ano": ano if isinstance(ano, int) else None,
            "nota_media": media,
            "n_notas": qtd,
            "chave": chave,
            "bem_avaliado": bool(media and media >= 3.5 and qtd >= 5),
        })

    # Ordem aleatória, mas com os bem avaliados na frente (o sort do Python é estável)
    random.shuffle(opcoes)
    opcoes.sort(key=lambda livro: not livro["bem_avaliado"])

    # Prefere autores diferentes, para as indicações não serem todas do mesmo escritor
    escolhidos, autores_usados = [], set()
    for livro in opcoes:
        autor = _limpar(livro["autor"])
        if autor not in autores_usados:
            escolhidos.append(livro)
            autores_usados.add(autor)
        if len(escolhidos) == quantidade:
            break
    # Se faltaram autores diferentes, completa com o que sobrou
    for livro in opcoes:
        if len(escolhidos) >= quantidade:
            break
        if livro not in escolhidos:
            escolhidos.append(livro)
    return escolhidos


def recomendar_livro(genero, titulos_ja_vistos):
    """Versão de uma indicação só (mantida por compatibilidade). None se não houver."""
    livros = recomendar_livros(genero, titulos_ja_vistos, quantidade=1)
    return livros[0] if livros else None
