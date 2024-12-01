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
    db = get_db_connection()
    
    try:
        # Busca todos os links ativos
        links = list(db.product_links.find())
        total_links = len(links)
        print(f"Encontrados {total_links} links para atualizar")
        
        for index, link in enumerate(links, 1):
            try:
                print(f"\nAtualizando link {index}/{total_links}: {link['product_url']}")
                product_info = fetch_product_info(link['product_url'])
                
                if product_info['price']:
                    # Registra o novo preço
                    log_price(str(link['_id']), product_info['price'])
                    print(f"✓ Preço atualizado: R$ {product_info['price']:.2f}")
                    
                    # Atualiza informações do link
                    db.product_links.update_one(
                        {"_id": link['_id']},
                        {"$set": {
                            "last_update": datetime.utcnow(),
                            "image_url": product_info['image_url'],
                            "favicon_url": product_info['favicon_url'],
                            "logo_url": product_info['logo_url']
                        }}
                    )
                else:
                    print("✗ Não foi possível encontrar o preço")
                    
            except Exception as e:
                print(f"✗ Erro ao atualizar {link['product_url']}: {str(e)}")
                continue
        
        print("\nAtualização concluída!")
        
    except Exception as e:
        print(f"Erro durante a atualização: {str(e)}")

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