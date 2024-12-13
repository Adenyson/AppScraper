import os
import sqlite3
from datetime import datetime
import bcrypt
from contextlib import contextmanager
import uuid

@contextmanager
def get_db_connection():
    """
    Cria e retorna uma conexão com o SQLite
    """
    conn = sqlite3.connect('appscraper.db')
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """
    Inicializa as tabelas necessárias no SQLite
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Criação das tabelas
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password BLOB,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                auth_type TEXT DEFAULT 'email',
                google_id TEXT
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS product_links (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                product_url TEXT NOT NULL,
                site_name TEXT,
                image_url TEXT,
                favicon_url TEXT,
                logo_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_link_id TEXT,
                FOREIGN KEY (link_id) REFERENCES product_links(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_product_links_url ON product_links(product_url);
        ''')
        conn.commit()

def add_product(product_name, user_id):
    """
    Adiciona um novo produto ao SQLite
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        product_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO products (id, product_name, user_id)
            VALUES (?, ?, ?)
        ''', (product_id, product_name, user_id))
        conn.commit()
        return product_id

def add_product_link(product_id, product_url, site_name, image_url=None, favicon_url=None, logo_url=None):
    """
    Adiciona um novo link de produto
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verifica se o produto existe
        cursor.execute('SELECT id FROM products WHERE id = ?', (product_id,))
        if not cursor.fetchone():
            raise ValueError("Produto não encontrado")
        
        # Verifica se o link já existe para este produto
        cursor.execute('''
            SELECT id 
            FROM product_links 
            WHERE product_id = ? AND product_url = ?
        ''', (product_id, product_url))
        
        if cursor.fetchone():
            raise ValueError("Este link já existe para este produto")
            
        # Adiciona o link
        link_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO product_links 
            (id, product_id, product_url, site_name, image_url, favicon_url, logo_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            link_id,
            product_id,
            product_url,
            site_name,
            image_url,
            favicon_url,
            logo_url,
            datetime.utcnow()
        ))
        conn.commit()
        return link_id

def log_price(link_id, price):
    """
    Registra um novo preço no histórico
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO price_history (link_id, price)
            VALUES (?, ?)
        ''', (link_id, float(price)))
        conn.commit()

def get_user_products(user_id):
    """
    Retorna todos os produtos do usuário com seus links e histórico de preços
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Busca produtos
        cursor.execute('''
            SELECT id, product_name as name, created_at
            FROM products
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        products = [dict(row) for row in cursor.fetchall()]
        
        # Para cada produto, busca seus links e histórico de preços
        for product in products:
            cursor.execute('''
                SELECT pl.*, 
                       GROUP_CONCAT(ph.price) as prices,
                       GROUP_CONCAT(ph.timestamp) as dates
                FROM product_links pl
                LEFT JOIN price_history ph ON pl.id = ph.link_id
                WHERE pl.product_id = ?
                GROUP BY pl.id
            ''', (product['id'],))
            
            links = []
            for link in cursor.fetchall():
                link_dict = dict(link)
                
                # Processa os preços e datas
                prices = link_dict.get('prices')
                dates = link_dict.get('dates')
                
                if prices and dates:
                    prices = [float(p) for p in prices.split(',') if p]
                    dates = [d for d in dates.split(',') if d]
                    link_dict['price_data'] = {
                        'prices': prices,
                        'dates': dates
                    }
                else:
                    link_dict['price_data'] = {'prices': [], 'dates': []}
                
                links.append(link_dict)
            
            product['links'] = links
            
        return products

def get_user_by_id(user_id):
    """
    Busca um usuário pelo ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM users
            WHERE id = ?
        ''', (user_id,))
        return cursor.fetchone()

def create_or_update_user(user_id, name, email):
    """
    Cria ou atualiza um usuário no SQLite
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET name = ?, email = ?, updated_at = ?
            WHERE id = ?
        ''', (name, email, datetime.utcnow(), user_id))
        conn.commit()
        return user_id

def check_link_exists(product_url):
    """
    Verifica se um link já existe e retorna suas informações
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pl.*, p.product_name, p.user_id
            FROM product_links pl
            JOIN products p ON pl.product_id = p.id
            WHERE pl.product_url = ?
            ORDER BY pl.created_at DESC
            LIMIT 1
        ''', (product_url,))
        link = cursor.fetchone()
        
        if link:
            # Busca histórico de preços
            cursor.execute('''
                SELECT price, timestamp
                FROM price_history
                WHERE link_id = ?
                ORDER BY timestamp ASC
            ''', (link['id'],))
            price_history = cursor.fetchall()
            
            return {
                "exists": True,
                "product_name": link['product_name'],
                "product_id": link['product_id'],
                "link_id": link['id'],
                "added_at": link['created_at'],
                "site_name": link['site_name'],
                "image_url": link['image_url'],
                "favicon_url": link['favicon_url'],
                "logo_url": link['logo_url'],
                "price_history": price_history,
                "user_id": link['user_id']
            }
    return {"exists": False}

def delete_product_link(link_id):
    """
    Remove um link de produto
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Primeiro remove o histórico de preços
        cursor.execute('''
            DELETE FROM price_history
            WHERE link_id = ?
        ''', (link_id,))
        
        # Depois remove o link
        cursor.execute('''
            DELETE FROM product_links
            WHERE id = ?
        ''', (link_id,))
        
        conn.commit()
        return cursor.rowcount > 0

def get_best_price_link(product_id):
    """
    Retorna o link com o melhor preço atual para um produto
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, product_url, site_name, price, timestamp
            FROM product_links
            JOIN price_history ON product_links.id = price_history.link_id
            WHERE product_id = ?
            ORDER BY price ASC
            LIMIT 1
        ''', (product_id,))
        link = cursor.fetchone()
        if link:
            return {
                "url": link['product_url'],
                "site_name": link['site_name'],
                "price": link['price'],
                "last_update": link['timestamp']
            }
        return None

def update_product_name(product_id, new_name):
    """
    Atualiza o nome de um produto
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET product_name = ?
            WHERE id = ?
        ''', (new_name, product_id))
        conn.commit()
        return cursor.rowcount > 0

def create_user(email, password, name):
    """
    Cria um novo usuário com email e senha
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verifica se o email já existe
        cursor.execute('''
            SELECT *
            FROM users
            WHERE email = ?
        ''', (email,))
        if cursor.fetchone():
            return None, "Email já cadastrado"
        
        # Hash da senha
        cursor.execute('''
            INSERT INTO users (id, email, password, name, created_at, auth_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (str(uuid.uuid4()), email, bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()), name, datetime.utcnow(), 'email'))
        conn.commit()
        return cursor.lastrowid, None

def verify_user(email, password):
    """
    Verifica credenciais do usuário
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM users
            WHERE email = ? AND auth_type = ?
        ''', (email, 'email'))
        user = cursor.fetchone()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return user
        return None

def create_or_update_google_user(google_id, email, name):
    """
    Cria ou atualiza usuário do Google
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET google_id = ?, name = ?, auth_type = ?, updated_at = ?
            WHERE email = ?
        ''', (google_id, name, 'google', datetime.utcnow(), email))
        conn.commit()
        cursor.execute('''
            SELECT *
            FROM users
            WHERE email = ?
        ''', (email,))
        return cursor.fetchone()

def delete_product_and_links(product_id):
    """
    Remove um produto e todos seus links
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Primeiro busca todos os links do produto
        cursor.execute('SELECT id FROM product_links WHERE product_id = ?', (product_id,))
        links = cursor.fetchall()
        
        # Remove o histórico de preços de cada link
        for link in links:
            cursor.execute('DELETE FROM price_history WHERE link_id = ?', (link['id'],))
            
        # Remove todos os links do produto
        cursor.execute('DELETE FROM product_links WHERE product_id = ?', (product_id,))
        
        # Por fim, remove o produto
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        
        conn.commit()
        return cursor.rowcount > 0