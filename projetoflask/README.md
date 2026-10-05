# Comunidade de Resenhas MVP

Flask + SQLite (módulo `sqlite3`, **sem ORM** em arquitetura *Active Record* e *Context Manager*) + indicação de livro pela Open Library (com suporte adaptativo a proxy de rede).

## Rodar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                      # abra http://127.0.0.1:5000 e clique em "Criar conta"

```

O banco (`instance/resenhas.db`) é criado sozinho na primeira execução.
Testes (sem internet): `python -m unittest discover -s tests -v`

## Onde está cada coisa

| Arquivo | O que tem |
| --- | --- |
| `run.py` | ponto de entrada raiz para inicializar o servidor da aplicação |
| `clube/__init__.py` | inicialização do pacote Flask, configuração de chaves e carregamento do banco e rotas |
| `clube/models.py` | **camada de dados**: Context Manager (`ConexaoBD`) e classes Active Record (`Usuario`, `Resenha`) com SQL parametrizado |
| `clube/rotas.py` | rotas web, autenticação, sessões e validações de formulário |
| `clube/recomendacao.py` | integração com a Open Library com suporte inteligente a ligações diretas e proxy de rede |
| `clube/templates/` | páginas HTML estruturadas com Jinja2 |
| `tests/test_mvp.py` | suíte de testes automatizados cobrindo acesso, CRUD e resiliência de rede |

## Banco de dados

```
usuarios (id, nome UNIQUE COLLATE NOCASE, senha_hash)
resenhas (id, usuario_id -> usuarios.id ON DELETE CASCADE, titulo, genero, texto, criado_em)

```
