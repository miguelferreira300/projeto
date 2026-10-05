# Comunidade de Resenhas Geek — MVP

Flask + SQLite (módulo `sqlite3`, **sem ORM**) + indicação de livro pela Open Library.

## Rodar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # abra http://127.0.0.1:5000 e clique em "Criar conta"
```

O banco (`instance/resenhas.db`) é criado sozinho na primeira execução.
Testes (sem internet): `python -m unittest discover -s tests -v`

## Onde está cada coisa

| Arquivo | O que tem |
|---|---|
| `banco.py` | **todo o SQL**: `CREATE TABLE` e o CRUD (`INSERT`, `SELECT`, `UPDATE`, `DELETE`) |
| `app.py` | rotas, login/registro e validação dos formulários |
| `recomendacao.py` | busca na Open Library e escolha do livro indicado |
| `templates/` | páginas HTML |

## Banco de dados

```
usuarios (id, nome UNIQUE, senha_hash)
resenhas (id, usuario_id -> usuarios.id, titulo, genero, texto, criado_em)
```





