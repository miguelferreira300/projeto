import random
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

def _limpar(texto):
    """Minúsculas e sem acento: 'Ficção Científica' -> 'ficcao cientifica'."""
    if not texto: return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())

def recomendar_livro(genero, titulos_ja_vistos):
    limpo = _limpar(genero)
    assunto = TRADUCAO.get(limpo, limpo.replace(" ", "_"))
    vistos = {_limpar(t) for t in titulos_ja_vistos}

    params = {"subject": assunto, "limit": 30, "fields": "title,author_name,cover_i"}
    headers = {"User-Agent": "ResenhasGeek/1.0"}
    
    docs = []

    # PLANO A: Tenta ligar diretamente à internet (Funciona no seu Windows em casa)
    try:
        # proxies={"http": None, "https": None} força a ignorar qualquer configuração local do Windows
        resposta = requests.get(URL, params=params, headers=headers, timeout=5, proxies={"http": None, "https": None}, verify=False)
        resposta.raise_for_status()
        docs = resposta.json().get("docs", [])
        
    except requests.exceptions.RequestException:
        # PLANO B: Se a ligação cair na firewall, injeta o proxy do IFSP (Funciona no Linux da escola)
        try:
            resposta = requests.get(URL, params=params, headers=headers, timeout=5, proxies=PROXY_ESCOLA, verify=False)
            resposta.raise_for_status()
            docs = resposta.json().get("docs", [])
            
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Falhou a ligação direta e a ligação via proxy. Erro: {e}")
            return None

    # Processa os resultados da API (só chega aqui se um dos planos acima tiver sucesso)
    opcoes = []
    for livro in docs:
        titulo = livro.get("title")
        autores = livro.get("author_name")
        
        if not titulo or not autores or _limpar(titulo) in vistos:
            continue
            
        capa = livro.get("cover_i")
        opcoes.append({
            "titulo": titulo,
            "autor": autores[0],
            "capa_url": f"https://covers.openlibrary.org/b/id/{capa}-M.jpg" if capa else ""
        })

    if opcoes:
        return random.choice(opcoes)

    return None