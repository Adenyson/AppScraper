import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from utils import get_db_connection, log_price
from PIL import Image
from io import BytesIO
import concurrent.futures

def get_image_resolution(img_url):
    """
    Obtém a resolução real da imagem
    """
    try:
        response = requests.get(img_url, timeout=5)
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        return width * height
    except Exception as e:
        print(f"Erro ao verificar resolução da imagem {img_url}: {e}")
        return 0

def is_valid_image_url(url):
    """
    Função melhorada para validar URL da imagem
    """
    if not url:
        return False
    if not url.startswith(('http://', 'https://')):
        return False
    # Extensões de imagem comuns
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    # Remove parâmetros de URL para verificar extensão
    clean_url = url.split('?')[0].lower()
    return any(clean_url.endswith(ext) for ext in valid_extensions)

def get_image_quality_score(url, resolution=None):
    """
    Sistema de pontuação melhorado para qualidade de imagem
    """
    if not url:
        return 0
    
    score = 0
    url_lower = url.lower()

    # Pontuação baseada em palavras-chave no URL
    resolution_indicators = {
        'high': 5,
        'large': 5,
        'full': 7,
        'original': 8,
        'zoom': 6,
        'big': 4,
        'max': 6,
        '1000': 3,
        '1200': 4,
        '1500': 5,
        '2000': 6,
        '2500': 7,
        '3000': 8
    }

    for indicator, points in resolution_indicators.items():
        if indicator in url_lower:
            score += points

    # Penalização para imagens pequenas
    low_res_indicators = ['thumb', 'small', 'mini', '100x', '150x', '200x', 'tiny', 'icon']
    for indicator in low_res_indicators:
        if indicator in url_lower:
            score -= 5

    # Bônus para imagens com dimensões no URL
    dimensions_match = re.search(r'(\d+)x(\d+)', url_lower)
    if dimensions_match:
        width = int(dimensions_match.group(1))
        height = int(dimensions_match.group(2))
        if width >= 800 and height >= 800:
            score += 5
        elif width >= 500 and height >= 500:
            score += 3

    # Pontuação baseada na resolução real (se fornecida)
    if resolution:
        if resolution > 1920*1080:  # Full HD
            score += 10
        elif resolution > 1280*720:  # HD
            score += 7
        elif resolution > 800*600:
            score += 5

    return score

def get_site_logos(soup, domain):
    """
    Busca o favicon e o logotipo do site
    """
    favicon_url = None
    logo_url = None
    
    # Lista de possíveis locais do favicon
    favicon_selectors = [
        'link[rel="icon"]',
        'link[rel="shortcut icon"]',
        'link[rel="apple-touch-icon"]',
        'link[rel="apple-touch-icon-precomposed"]'
    ]
    
    # Lista de possíveis locais do logotipo
    logo_selectors = [
        'img[class*="logo"]',
        'img[alt*="logo"]',
        'img[src*="logo"]',
        '.header img',
        '.navbar-brand img',
        'header img',
        '#logo img'
    ]
    
    # Busca o logotipo
    for selector in logo_selectors:
        logo_elem = soup.select_one(selector)
        if logo_elem and logo_elem.get('src'):
            logo_url = logo_elem['src']
            if not logo_url.startswith(('http://', 'https://')):
                if logo_url.startswith('//'):
                    logo_url = f"https:{logo_url}"
                else:
                    logo_url = f"https://{domain}/{logo_url.lstrip('/')}"
            break
    
    # Busca o favicon
    for selector in favicon_selectors:
        favicon_tag = soup.select_one(selector)
        if favicon_tag and favicon_tag.get('href'):
            favicon_url = favicon_tag['href']
            break
    
    # Se não encontrou favicon, tenta o caminho padrão
    if not favicon_url:
        favicon_url = f"https://{domain}/favicon.ico"
    
    # Se o favicon URL é relativo, converte para absoluto
    if favicon_url and not favicon_url.startswith(('http://', 'https://')):
        if favicon_url.startswith('//'):
            favicon_url = f"https:{favicon_url}"
        else:
            favicon_url = f"https://{domain}/{favicon_url.lstrip('/')}"
    
    # Verifica se o favicon existe
    try:
        response = requests.head(favicon_url, timeout=5)
        if response.status_code != 200:
            favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    except:
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    
    return {
        'favicon_url': favicon_url,
        'logo_url': logo_url
    }

def fetch_product_info(product_url):
    """
    Faz o scraping das informações do produto
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(product_url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    domain = urlparse(product_url).netloc
    site_name = domain.replace('www.', '').split('.')[0].capitalize()
    
    # Busca favicon e logo
    site_logos = get_site_logos(soup, domain)
    
    # Lista expandida de seletores prioritários
    image_selectors = [
        '#view-container img',
        '.product-image-container img',
        '.product-gallery img',
        '#main-image',
        '.main-product-image',
        'img[itemprop="image"]',
        '#landingImage',
        '.showcase-product__picture',
        '.product-image',
        '.zoom-image',
        '.product__image',
        '.product-featured-image',
        'img[data-zoom-image]',
        '.highres-image',
        '.product-photo',
        '.full-price'
    ]
    
    image_candidates = []
    
    # Coleta todas as imagens candidatas
    for selector in image_selectors:
        images = soup.select(selector)
        for img in images:
            for attr in ['data-zoom-image', 'data-src', 'data-original', 'data-lazy', 'data-high-res', 'src']:
                img_url = img.get(attr)
                if is_valid_image_url(img_url):
                    image_candidates.append(img_url)

    # Se não encontrou imagens suficientes, procura em todas as imagens
    if len(image_candidates) < 3:
        all_images = soup.find_all('img')
        for img in all_images:
            for attr in ['data-zoom-image', 'data-src', 'data-original', 'data-lazy', 'data-high-res', 'src']:
                img_url = img.get(attr)
                if is_valid_image_url(img_url):
                    image_candidates.append(img_url)

    # Remove duplicatas mantendo a ordem
    image_candidates = list(dict.fromkeys(image_candidates))

    # Verifica resolução das imagens em paralelo
    scored_images = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(get_image_resolution, url): url for url in image_candidates[:5]}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                resolution = future.result()
                score = get_image_quality_score(url, resolution)
                scored_images.append({
                    'url': url,
                    'score': score,
                    'resolution': resolution
                })
            except Exception as e:
                print(f"Erro ao processar imagem {url}: {e}")

    # Ordena por pontuação
    scored_images.sort(key=lambda x: (x['score'], x['resolution']), reverse=True)
    
    # Seleciona a melhor imagem
    image_url = scored_images[0]['url'] if scored_images else None
    if image_url and not image_url.startswith(('http://', 'https://')):
        image_url = f"https:{image_url}"

    # Busca o preço
    price = None
    
    # Verifica se é um site da Apple
    if 'apple.com' in domain:
        try:
            # Busca exatamente o elemento da Apple com classe e data-autom específicos
            price_elem = soup.find('span', {
                'class': 'rc-prices-fullprice',
                'data-autom': 'full-price'
            })
            
            if price_elem:
                price_text = price_elem.get_text().strip()
                print(f"Texto do preço encontrado na Apple: {price_text}")
                
                # Remove R$ e outros caracteres
                price_text = re.sub(r'[^\d,.]', '', price_text)
                
                # Trata casos com vírgula e ponto
                if ',' in price_text and '.' in price_text:
                    price_text = price_text.replace('.', '').replace(',', '.')
                else:
                    price_text = price_text.replace(',', '.')
                
                price = float(price_text)
                print(f"✓ Preço encontrado no site da Apple: R$ {price:.2f}")
            else:
                print("✗ Elemento de preço não encontrado no site da Apple")
        except Exception as e:
            print(f"✗ Erro ao processar preço da Apple: {e}")
    else:
        # Lógica original para outros sites
        price_elem = soup.find('h2', class_='price')
        if price_elem:
            # Remove o span interno se existir
            span = price_elem.find('span')
            if span:
                span.decompose()
            
            # Pega o texto limpo
            price_text = price_elem.get_text().strip()
            try:
                price_text = re.sub(r'[^\d,.]', '', price_text)
                if ',' in price_text and '.' in price_text:
                    price_text = price_text.replace('.', '').replace(',', '.')
                else:
                    price_text = price_text.replace(',', '.')
                price = float(price_text)
            except (ValueError, AttributeError):
                price = None
        
        # Se não encontrou preço, tenta outros seletores
        if not price:
            # Seletores específicos conhecidos
            price_selectors = [
                'h2.price',                    # Seu caso específico
                'span.price-tag-fraction',     # Mercado Livre
                'span.a-price-whole',          # Amazon
                'p.price-template__text',      # Magalu
                'div.priceSales',              # Americanas
                'span.price',                  # Genérico
                'div.product-price',           # Genérico
                'p.price',                     # Genérico
                'span.regular-price'           # Genérico
            ]
            
            price = try_get_price(soup, price_selectors)
            
            # Se ainda não encontrou, tenta busca genérica por classe price
            if not price:
                elements_with_price = soup.find_all(class_=lambda x: x and 'price' in x.lower())
                for elem in elements_with_price:
                    try:
                        for child in elem.find_all(['span', 'small', 'sup', 'sub']):
                            child.decompose()
                        
                        price_text = elem.get_text().strip()
                        price_text = re.sub(r'[^\d,.]', '', price_text)
                        
                        if not any(c.isdigit() for c in price_text):
                            continue
                        
                        if ',' in price_text and '.' in price_text:
                            price_text = price_text.replace('.', '').replace(',', '.')
                        else:
                            price_text = price_text.replace(',', '.')
                        
                        price = float(price_text)
                        if price > 0:
                            print(f"Preço encontrado em elemento com classe: {elem.get('class')}")
                            break
                    except (ValueError, AttributeError) as e:
                        continue

    return {
        'price': price,
        'image_url': image_url,
        'site_name': site_name,
        'favicon_url': site_logos['favicon_url'],
        'logo_url': site_logos['logo_url']
    }

def try_get_price(soup, selectors):
    """
    Tenta obter o preço usando uma lista de seletores
    """
    for selector in selectors:
        try:
            price_elem = soup.select_one(selector)
            if price_elem:
                # Remove elementos internos que possam interferir
                for child in price_elem.find_all(['span', 'small', 'sup', 'sub']):
                    child.decompose()
                
                price_text = price_elem.get_text().strip()
                price_text = re.sub(r'[^\d,.]', '', price_text)
                
                if ',' in price_text and '.' in price_text:
                    price_text = price_text.replace('.', '').replace(',', '.')
                else:
                    price_text = price_text.replace(',', '.')
                
                price = float(price_text)
                if price > 0:  # Preço válido encontrado
                    print(f"Preço encontrado usando seletor: {selector}")
                    return price
        except (ValueError, AttributeError) as e:
            print(f"Erro ao processar seletor {selector}: {e}")
            continue
    return None

def update_prices():
    """
    Atualiza os preços de todos os produtos
    """
    conn, placeholder = get_db_connection()
    cursor = conn.cursor()
    
    # Busca todos os links
    cursor.execute('SELECT id, product_url FROM product_links')
    links = cursor.fetchall()
    
    for link_id, url in links:
        try:
            info = fetch_product_info(url)
            if info['price']:
                log_price(link_id, info['price'])
                print(f"Preço atualizado para {url}: R$ {info['price']:.2f}")
        except Exception as e:
            print(f"Erro ao atualizar preço de {url}: {e}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    update_prices()
