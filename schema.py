import sqlite3

def init_db():
    """
    Inicializa o banco de dados SQLite com as tabelas necessárias
    """
    conn = sqlite3.connect('appscraper.db')
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
    conn.close()

if __name__ == '__main__':
    init_db() 