import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from utils import init_db, get_product_prices, add_product, add_product_link, get_user_products

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'uma-chave-secreta-padrao')

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração OAuth para Google
oauth = OAuth(app)

# Verificar se as variáveis de ambiente necessárias estão presentes
if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
    print("AVISO: Credenciais do Google não configuradas!")

google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

class User(UserMixin):
    def __init__(self, user_id, name, email):
        self.id = user_id
        self.name = name
        self.email = email

    @staticmethod
    def get(user_id):
        """
        Busca usuário no banco de dados
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user_data:
            return User(user_data[0], user_data[1], user_data[2])
        return None

def create_or_update_user(user_id, name, email):
    """
    Cria ou atualiza usuário no banco de dados
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (id, name, email) 
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE 
        SET name = EXCLUDED.name, email = EXCLUDED.email
        RETURNING id
    ''', (user_id, name, email))
    user_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return user_id

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
    return google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    try:
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)
        user_id = user_info['sub']
        name = user_info.get('name', user_info.get('email', 'Usuário'))
        email = user_info['email']
        
        # Criar ou atualizar usuário no banco
        create_or_update_user(user_id, name, email)
        
        # Criar objeto User e fazer login
        user = User(user_id, name, email)
        login_user(user)
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro no login: {str(e)}', 'error')
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

# Adicionar tratamento de erro 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Adicionar tratamento de erro 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
