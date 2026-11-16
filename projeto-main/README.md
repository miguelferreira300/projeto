# Comunidade de Resenhas Geek

Aplicação web **MPA** em **Flask + Jinja2 + SQLite3** (SQL puro, sem ORM) para o Projeto Final de
**SPOLBP1 – Laboratório de Programação 1** (Técnico em Desenvolvimento de Sistemas – IFSP).

Cada usuário cadastra resenhas de livros e HQs, recebe indicações de leitura (API Open Library) e
organiza uma **Lista de Leitura** pessoal.

## Funcionalidades

- **Usuários:** cadastro, login e logout; senhas com `generate_password_hash` / `check_password_hash`.
- **Entidade 1 – Resenhas:** cadastro, listagem (paginada), edição, exclusão, nota em estrelas (1–5),
  busca por texto e filtros por gênero e nota, limite de 10 resenhas por hora e indicações de livros.
- **Entidade 2 – Lista de Leitura:** cadastro, listagem (paginada), edição, exclusão, status
  (quero ler / lendo / lido), prioridade, busca e filtro por status.
- **Relacionamento:** um item da lista pode ter sido criado a partir de uma resenha
  (`itens_leitura.resenha_id → resenhas.id`, botão "Adicionar à lista de leitura" nas indicações).
- **Isolamento por usuário:** toda consulta/edição/exclusão filtra por `usuario_id` do usuário logado.
- **Recursos do semestre:** sessão (`session.clear()`, `user_id`, `username`), middleware
  `@login_required` validando no banco e preenchendo `g.usuario`, cookies (último usuário no login e
  tema claro/escuro), flash messages categorizadas, validação no servidor, `@app.errorhandler`
  (404, 403, 500) e `app.logger` (console + `logs/app.log`).

## Estrutura (MVC)

```
projeto-main/
├── iniciar_bd.py        # CREATE TABLE IF NOT EXISTS + usuário de teste (via Usuario.salvar())
├── banco_dados.db       # gerado por iniciar_bd.py
├── run.py               # inicia o servidor Flask
├── requirements.txt
├── README.md
├── tests/               # testes automatizados (unittest)
└── app/
    ├── __init__.py      # Flask, secret_key, logger, errorhandlers e registro dos Blueprints
    ├── db.py            # DatabaseConnection (__enter__ / __exit__)
    ├── models/          # usuario.py, resenha.py, item_leitura.py (POO + todo o SQL)
    ├── controllers/     # auth_bp, main_bp, resenhas_bp, leitura_bp (sem SQL)
    ├── utils/           # auth_middleware.py, validacao.py, filtros.py, recomendacao.py
    ├── views/           # templates Jinja2 (herança de base.html)
    └── static/          # css/estilo.css e js/app.js
```

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python iniciar_bd.py             # cria banco_dados.db e o usuário de teste
python run.py                    # http://127.0.0.1:5000
```

Opcional: defina `SECRET_KEY` no ambiente para trocar a chave de sessão de desenvolvimento.

## Usuário de teste

| Usuário | Senha      |
|---------|------------|
| `teste` | `teste123` |

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes usam um banco temporário (variável `BANCO_DB`) e não acessam a internet.
