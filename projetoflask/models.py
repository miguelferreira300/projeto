import requests
import random

USUARIOS_CADASTRADOS = {"admin": "1234"}

def validar_login(usuario, senha):
    return USUARIOS_CADASTRADOS.get(usuario) == senha

def recomendar_livro_inedito(genero, livros_ja_vistos):
    termo_busca = genero.lower().replace(" ", "_")
    url = f"https://openlibrary.org/search.json?subject={termo_busca}&limit=30"
    
    try:
        resposta = requests.get(url, timeout=5)
        dados = resposta.json()
        resultados = dados.get('docs', [])
        
        livros_validos = []
        for livro in resultados:
            titulo = livro.get('title')
            autor = livro.get('author_name')
            # A API retorna o ID da capa no campo 'cover_i'
            cover_id = livro.get('cover_i') 
            
            if titulo and autor and (titulo not in livros_ja_vistos):
                
                # Monta a URL da capa (o 'M' no final indica tamanho médio)
                if cover_id:
                    capa_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                else:
                    # Imagem cinza genérica caso o livro não tenha capa no sistema deles
                    capa_url = "https://via.placeholder.com/150x220?text=Sem+Capa"
                    
                livros_validos.append({
                    "titulo": titulo,
                    "autor": autor[0],
                    "capa_url": capa_url # Adicionamos a URL ao dicionário
                })
        
        if livros_validos:
            return random.choice(livros_validos)
            
    except requests.exceptions.RequestException:
        pass

    # Fallback com imagem de erro
    return {
        "titulo": "Indicação Surpresa (API Indisponível)", 
        "autor": "Autor Desconhecido",
        "capa_url": "https://via.placeholder.com/150x220?text=Erro+de+Conexao"
    }