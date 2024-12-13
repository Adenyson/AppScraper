from scraper import fetch_product_info
from utils import get_db_connection, log_price
import time
import schedule
from datetime import datetime

def update_all_prices():
    """
    Atualiza os preços de todos os produtos e gera histórico
    """
    print(f"\nIniciando atualização de preços: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Busca todos os links ativos usando SQLite
        cursor.execute("SELECT * FROM product_links")
        links = cursor.fetchall()
        total_links = len(links)
        print(f"Encontrados {total_links} links para atualizar")
        
        for index, link in enumerate(links, 1):
            try:
                product_url = link['product_url']
                print(f"\nAtualizando link {index}/{total_links}: {product_url}")
                product_info = fetch_product_info(product_url)
                
                if product_info['price']:
                    # Registra o novo preço
                    log_price(link['id'], product_info['price'])
                    print(f"✓ Preço atualizado: R$ {product_info['price']:.2f}")
                    
                    # Atualiza informações do link
                    cursor.execute('''
                        UPDATE product_links
                        SET last_update = ?, image_url = ?, favicon_url = ?, logo_url = ?
                        WHERE id = ?
                    ''', (datetime.utcnow(), product_info['image_url'], product_info['favicon_url'], product_info['logo_url'], link['id']))
                    conn.commit()
                else:
                    print("✗ Não foi possível encontrar o preço")
                    
            except Exception as e:
                print(f"✗ Erro ao atualizar {product_url}: {str(e)}")
                continue

def job():
    print("Iniciando job de atualização programada...")
    update_all_prices()
    print("Job de atualização concluído!")

# Agenda a atualização para rodar a cada 1 hora
schedule.every(1).hour.do(job)

if __name__ == "__main__":
    # Executa uma atualização imediata ao iniciar
    job()
    
    # Continua com as atualizações programadas
    while True:
        schedule.run_pending()
        time.sleep(1) 