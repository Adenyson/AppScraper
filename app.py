import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from utils import (
    init_db,
    add_product,
    add_product_link,
    get_user_products,
    get_user_by_id,
    create_or_update_user,
    log_price,
    check_link_exists,
    delete_product_link,
    update_product_name,
    verify_user,
    create_user,
    create_or_update_google_user,
    get_db_connection
)
from scraper import fetch_product_info, update_prices
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import datetime
import threading
import time
from authlib.integrations.flask_client import OAuth
from itertools import zip_longest
from flask_caching import Cache
import sqlite3
from contextlib import contextmanager

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'}
)

# Adicione cache se necessário
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

class User(UserMixin):
    def __init__(self, user_id, name, email):
        self.id = user_id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(user_data["id"], user_data["name"], user_data["email"])
    return None

@app.route('/')
@login_required
def index():
    products = get_user_products(current_user.id)
    print("Produtos carregados:", products)  # Debug
    for product in products:
        for link in product['links']:
            print(f"Link encontrado: {link}")  # Debug dos links
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = verify_user(email, password)
        if user:
            login_user(User(str(user['id']), user['name'], user['email']))
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        
        flash('Email ou senha inválidos.', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        user, error = create_user(email, password, name)
        if user:
            login_user(User(str(user['_id']), user['name'], user['email']))
            flash('Conta criada com sucesso!', 'success')
            return redirect(url_for('index'))
        
        flash(f'Erro ao criar conta: {error}', 'error')
        return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorize')
def google_authorize():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()
    
    user = create_or_update_google_user(
        user_info['id'],
        user_info['email'],
        user_info['name']
    )
    
    login_user(User(str(user['_id']), user['name'], user['email']))
    flash('Login com Google realizado com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_product', methods=['POST'])
@login_required
def add_new_product():
    product_name = request.form['product_name']
    product_id = add_product(product_name, current_user.id)
    flash(f'Produto "{product_name}" adicionado com sucesso!')
    return redirect(url_for('index'))

@app.route('/add_link', methods=['POST'])
@login_required
def add_link():
    try:
        # Log de todos os dados do formulário
        print("Dados do formulário:", request.form)
        
        product_id = request.form.get('product_id')
        product_url = request.form.get('product_url')
        
        print("ID do produto recebido:", product_id)
        print("URL recebida:", product_url)
        
        if not product_id:
            print("ERRO: ID do produto não fornecido")
            flash('ID do produto não fornecido', 'error')
            return redirect(url_for('index'))
            
        # Validação: verifica se a URL foi fornecida    
        if not product_url:
            flash('URL do produto não fornecida', 'error')
            return redirect(url_for('index'))

        try:
            # Busca informações do produto na URL fornecida (preço, imagens, etc)
            product_info = fetch_product_info(product_url)
            
            # Log das informações obtidas
            print(f"Informações obtidas do produto: {product_info}")
            
            # Tenta adicionar o link ao produto usando a função do utils.py
            link_id = add_product_link(
                product_id=product_id,  # ID do produto ao qual o link será vinculado
                product_url=product_url,  # URL fornecida pelo usuário
                site_name=urlparse(product_url).netloc,  # Nome do site extraído da URL
                image_url=product_info.get('image_url'),  # Imagem do produto (se encontrada)
                favicon_url=product_info.get('favicon_url'),  # Favicon do site (se encontrado)
                logo_url=product_info.get('logo_url')  # Logo do site (se encontrado)
            )
            
            # Se o link foi adicionado com sucesso e tem preço, registra o preço
            if product_info.get('price'):
                log_price(link_id, product_info['price'])  # Registra o preço inicial
                flash(f'Link adicionado com sucesso! Preço atual: R$ {product_info["price"]:.2f}', 'success')
            else:
                flash('Link adicionado com sucesso, mas não foi possível detectar o preço.', 'warning')
            
            return redirect(url_for('index'))
            
        except ValueError as e:
            # Captura erros de validação (ex: produto não encontrado, link duplicado)
            print(f"Erro de validação: {e}")
            flash(str(e), 'error')
            return redirect(url_for('index'))
            
        except Exception as e:
            # Captura outros erros ao processar o produto
            print(f"Erro ao processar produto: {e}")
            flash('Erro ao adicionar link. Por favor, tente novamente.', 'error')
            return redirect(url_for('index'))
            
    except Exception as e:
        # Captura erros gerais
        print(f"Erro geral: {e}")
        flash('Erro ao adicionar link. Por favor, tente novamente.', 'error')
        return redirect(url_for('index'))

@app.route('/delete_link', methods=['POST'])
@login_required
def delete_link():
    try:
        link_id = request.form.get('link_id')
        if not link_id:
            flash('ID do link não fornecido', 'error')
            return redirect(url_for('index'))
            
        if delete_product_link(link_id):
            flash('Link removido com sucesso!', 'success')
        else:
            flash('Erro ao remover link.', 'error')
            
    except Exception as e:
        flash(f'Erro ao remover link: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.route('/edit_product_name', methods=['POST'])
@login_required
def edit_product_name():
    try:
        product_id = request.form['product_id']
        new_name = request.form['new_name'].strip()
        
        if not new_name:
            flash('O nome do produto não pode ficar vazio.', 'error')
            return redirect(url_for('index'))
        
        if update_product_name(product_id, new_name):
            flash('Nome do produto atualizado com sucesso!', 'success')
        else:
            flash('Erro ao atualizar nome do produto.', 'error')
            
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Erro ao editar nome do produto: {e}")
        flash('Erro ao editar nome do produto.', 'error')
        return redirect(url_for('index'))

@app.route('/delete_product', methods=['POST'])
@login_required
def delete_product():
    try:
        product_id = request.form.get('product_id')
        if not product_id:
            flash('ID do produto não fornecido', 'error')
            return redirect(url_for('index'))
            
        if delete_product_and_links(product_id):
            flash('Produto removido com sucesso!', 'success')
        else:
            flash('Erro ao remover produto.', 'error')
            
    except Exception as e:
        flash(f'Erro ao remover produto: {str(e)}', 'error')
        
    return redirect(url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Erro não tratado: {str(e)}")
    return render_template('500.html'), 500

def background_update():
    """
    Executa a atualização em segundo plano
    """
    with app.app_context():
        while True:
            try:
                print("Iniciando atualização automática...")
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, product_url
                        FROM product_links
                    ''')
                    links = cursor.fetchall()
                    
                    for link in links:
                        try:
                            product_info = fetch_product_info(link['product_url'])
                            if product_info['price']:
                                log_price(link['id'], product_info['price'])
                                print(f"✓ Preço atualizado para {link['product_url']}: R$ {product_info['price']:.2f}")
                        except Exception as e:
                            print(f"✗ Erro ao atualizar {link['product_url']}: {str(e)}")
                            continue
                
                print("Atualização automática concluída!")
                time.sleep(3600)  # 3600 segundos = 1 hora
            except Exception as e:
                print(f"Erro na atualização automática: {e}")
                time.sleep(300)  # 5 minutos em caso de erro

# Use em rotas pesadas
@cache.cached(timeout=300)
def rota_pesada():
    pass

if __name__ == "__main__":
    try:
        print("Inicializando banco de dados...")
        init_db()
        print("Banco de dados inicializado com sucesso!")
        
        # Inicia a atualização em uma thread separada
        print("Iniciando atualização automática dos produtos...")
        update_thread = threading.Thread(target=background_update)
        update_thread.daemon = True
        update_thread.start()
        
    except Exception as e:
        print(f"Erro ao inicializar: {e}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
