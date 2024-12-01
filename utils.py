import psycopg2
import os

# URL do banco de dados a partir das variáveis de ambiente
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """
    Cria e retorna uma conexão com o banco de dados PostgreSQL.
    Adaptado para o Railway.app
    """
    try:
        # Railway fornece a URL do banco de dados em DATABASE_URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        
        # Railway usa o prefixo postgres://, mas psycopg2 precisa de postgresql://
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        raise e

def init_db():
    """
    Inicializa o banco de dados criando as tabelas 'products', 'product_links' e 'price_history' se não existirem.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE NOT NULL
        )
    ''')

    # Tabela de produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            product_name TEXT NOT NULL,
            user_id TEXT REFERENCES users(id)
        )
    ''')

    # Tabela de links de produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_links (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            product_url TEXT NOT NULL,
            site_name TEXT
        )
    ''')

    # Tabela de histórico de preços
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            link_id INTEGER REFERENCES product_links(id) ON DELETE CASCADE,
            price REAL,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

def add_product(product_name, user_id):
    """
    Adiciona um novo produto ao banco de dados e retorna o ID do produto.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (product_name, user_id) VALUES (%s, %s) RETURNING id', 
                  (product_name, user_id))
    product_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return product_id

def add_product_link(product_id, product_url, site_name):
    """
    Adiciona um novo link de preço para um produto específico e retorna o ID do link.

    Parâmetros:
    - product_id: ID do produto na tabela products.
    - product_url: URL do produto para acompanhamento.
    - site_name: Nome do site (opcional, para identificação).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO product_links (product_id, product_url, site_name) VALUES (%s, %s, %s) RETURNING id',
                   (product_id, product_url, site_name))
    link_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return link_id

def log_price(link_id, price):
    """
    Insere um novo registro de preço no histórico para um link específico.

    Parâmetros:
    - link_id: ID do link na tabela product_links.
    - price: Preço atual do produto.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO price_history (link_id, price) VALUES (%s, %s)', (link_id, price))
    conn.commit()
    cursor.close()
    conn.close()

def get_product_prices(product_id):
    """
    Recupera todos os links e o histórico de preços associados a um produto específico para comparação.

    Parâmetros:
    - product_id: ID do produto na tabela products.

    Retorna:
    - Uma lista de tuplas contendo (product_url, site_name, price, timestamp) para cada registro de histórico de preços.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT pl.product_url, pl.site_name, ph.price, ph.timestamp 
        FROM product_links pl
        JOIN price_history ph ON pl.id = ph.link_id
        WHERE pl.product_id = %s
        ORDER BY ph.timestamp DESC
    ''', (product_id,))
    prices = cursor.fetchall()
    cursor.close()
    conn.close()
    return prices

def get_user_products(user_id):
    """
    Retorna todos os produtos de um usuário com seus dados de preço para os gráficos
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.product_name,
               array_agg(ph.price ORDER BY ph.timestamp) as prices,
               array_agg(ph.timestamp ORDER BY ph.timestamp) as dates
        FROM products p
        LEFT JOIN product_links pl ON p.id = pl.product_id
        LEFT JOIN price_history ph ON pl.id = ph.link_id
        WHERE p.user_id = %s
        GROUP BY p.id, p.product_name
    ''', (user_id,))
    
    products = []
    for row in cursor.fetchall():
        products.append({
            'id': row[0],
            'name': row[1],
            'price_data': {
                'prices': row[2] if row[2][0] is not None else [],
                'dates': [d.strftime('%Y-%m-%d %H:%M') for d in row[3]] if row[3][0] is not None else []
            }
        })
    
    cursor.close()
    conn.close()
    return products
