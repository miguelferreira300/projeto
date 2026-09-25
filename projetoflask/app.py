from flask import Flask, render_template, request, redirect, url_for, session
from models import validar_login, recomendar_livro_inedito

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_usar_sessoes'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        
        if validar_login(usuario, senha):
            session['logado'] = True
            session['usuario'] = usuario
            session['vistos'] = [] 
            return redirect(url_for('nova_resenha'))
            
        return "Credenciais inválidas. Tente admin / 1234."
        
    return render_template('login.html')

@app.route('/resenha', methods=['GET', 'POST'])
def nova_resenha():
    if not session.get('logado'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        titulo_lido = request.form['titulo']
        genero_lido = request.form['genero']
        texto_resenha = request.form['resenha']
        
        livros_vistos = session.get('vistos', [])
        livro_indicado = recomendar_livro_inedito(genero_lido, livros_vistos)
        
        if livro_indicado['titulo'] not in livros_vistos:
            livros_vistos.append(livro_indicado['titulo'])
            session['vistos'] = livros_vistos
            session.modified = True
        
        return render_template('resultado.html', 
                               titulo=titulo_lido, 
                               resenha=texto_resenha, 
                               recomendacao=livro_indicado)
                               
    return render_template('resenha.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)