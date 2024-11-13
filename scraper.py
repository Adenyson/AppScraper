import requests
from bs4 import BeautifulSoup
from utils import get_db_connection, log_price

def fetch_price(product_url):
    """
    Faz o scraping do preço em um link de produto específico.
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(product_url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Ajuste conforme a estrutura HTML da página
    price = soup.find("span", class_="preco_do_produto").text.strip()
    return float(price.replace("R$", "").replace(",", "."))  # Converte para float

def update_all_prices():
    """
    Atualiza os preços para todos os links de todos os produtos no banco de dados.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, product_url FROM product_links')
    links = cursor.fetchall()
    cursor.close()
    conn.close()

    for link_id, product_url in links:
        try:
            price = fetch_price(product_url)
            log_price(link_id, price)
            print(f"Preço atualizado para o link {product_url}: R$ {price}")
        except Exception as e:
            print(f"Erro ao buscar preço de {product_url}: {e}")

if __name__ == "__main__":
    update_all_prices()
