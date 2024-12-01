from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from utils import init_db, get_product_prices, add_product, add_product_link, get_user_products
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração OAuth para Apple
oauth = OAuth(app)
apple = oauth.register(
    name='apple',
    client_id=os.getenv('APPLE_CLIENT_ID'),
    client_secret=os.getenv('APPLE_CLIENT_SECRET'),
    authorize_url='https://appleid.apple.com/auth/authorize',
    authorize_params=None,
    access_token_url='https://appleid.apple.com/auth/token',
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri=os.getenv('APPLE_REDIRECT_URI'),
    client_kwargs={'scope': 'name email'}
)

class User(UserMixin):
    def __init__(self, user_id, name, email):
        self.id = user_id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    # Implementar busca do usuário no banco
    return User.get(user_id)

@app.route('/')
def index():
    if current_user.is_authenticated:
        products = get_user_products(current_user.id)
        return render_template('index.html', products=products)
    return render_template('index.html')

@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return apple.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = apple.authorize_access_token()
    user_info = apple.parse_id_token(token)
    # Criar ou atualizar usuário no banco
    user = User(user_info['sub'], user_info.get('name', ''), user_info['email'])
    login_user(user)
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
def add_link():
    product_id = int(request.form['product_id'])
    product_url = request.form['product_url']
    site_name = request.form['site_name']
    link_id = add_product_link(product_id, product_url, site_name)
    return f"Link adicionado com ID {link_id} para o produto {product_id}"

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
