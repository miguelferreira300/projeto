import random
import time
import unicodedata
import urllib3
import requests

# Desativa alertas de segurança (essencial para o proxy da escola intercetar SSL)
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

PROXY_ESCOLA = {
    "http": "http://proxy.spo.ifsp.edu.br:3128/",
    "https": "http://proxy.spo.ifsp.edu.br:3128/"
}

CACHE_SEGUNDOS = 600
_cache = {}  

def limpar_cache():
    _cache.clear()

def _limpar(texto):
    """Minúsculas e sem acento."""
    if not texto: return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())

def _chave(titulo):
    return _limpar(titulo)[:40]

def _buscar_docs(params, headers):
    """Devolve a lista de livros da API com tratamento de rede."""
    try:
        resposta = requests.get(URL, params=params, headers=headers, timeout=10, proxies={"http": "", "https": ""}, verify=False)
        resposta.raise_for_status()
        dados = resposta.json()
        return dados.get("docs", []) if isinstance(dados, dict) else []
    except (requests.exceptions.RequestException, ValueError):
        try:
            resposta = requests.get(URL, params=params, headers=headers, timeout=10, proxies=PROXY_ESCOLA, verify=False)
            resposta.raise_for_status()
            dados = resposta.json()
            return dados.get("docs", []) if isinstance(dados, dict) else []
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"DEBUG: Falha de rede. Erro: {e}")
            return None

def recomendar_livros(genero, titulos_ja_vistos, quantidade=3):
    limpo = _limpar(genero)
    assunto = TRADUCAO.get(limpo, limpo.replace(" ", "_"))
    vistos = {_chave(t) for t in titulos_ja_vistos}

    docs = None
    em_cache = _cache.get(assunto)
    
    # Só aproveita o cache se houver conteúdo real armazenado
    if em_cache and time.time() - em_cache[0] < CACHE_SEGUNDOS and em_cache[1]:
        docs = em_cache[1]
    else:
        # Mantém as chaves avançadas (ratings, year) que o seu sistema utiliza
        params = {"subject": assunto, "limit": 50,
                  "fields": "title,author_name,cover_i,first_publish_year,ratings_average,ratings_count"}
        headers = {"User-Agent": "ResenhasGeek/1.0"}
        
        docs = _buscar_docs(params, headers)
        
        if not docs:
            return None 
            
        if len(_cache) >= 100:  
            _cache.clear()
        _cache[assunto] = (time.time(), docs)

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
        
        # Dicionário original restaurado por completo
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

    # Ordem aleatória, mas garantindo que os bem avaliados aparecem primeiro
    random.shuffle(opcoes)
    opcoes.sort(key=lambda livro: not livro["bem_avaliado"])

    escolhidos, autores_usados = [], set()
    for livro in opcoes:
        autor = _limpar(livro["autor"])
        if autor not in autores_usados:
            escolhidos.append(livro)
            autores_usados.add(autor)
        if len(escolhidos) == quantidade:
            break
            
    for livro in opcoes:
        if len(escolhidos) >= quantidade:
            break
        if livro not in escolhidos:
            escolhidos.append(livro)
            
    return escolhidos

def recomendar_livro(genero, titulos_ja_vistos):
    livros = recomendar_livros(genero, titulos_ja_vistos, quantidade=1)
    return livros[0] if livros else None