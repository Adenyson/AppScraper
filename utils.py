import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import bcrypt

def get_db_connection():
    """
    Cria e retorna uma conexão com o MongoDB
    """
    MONGODB_URI = os.getenv("MONGODB_URI")
    client = MongoClient(MONGODB_URI)
    db = client.appscraper
    return db

def init_db():
    """
    Inicializa as coleções necessárias no MongoDB
    """
    db = get_db_connection()
    # Cria índices necessários
    db.users.create_index("email", unique=True)
    db.product_links.create_index("product_url")

def add_product(product_name, user_id):
    """
    Adiciona um novo produto ao MongoDB
    """
    db = get_db_connection()
    result = db.products.insert_one({
        "product_name": product_name,
        "user_id": user_id,
        "created_at": datetime.utcnow()
    })
    return str(result.inserted_id)

def add_product_link(product_id, product_url, site_name, image_url=None, favicon_url=None, logo_url=None):
    """
    Adiciona um novo link de produto
    """
    db = get_db_connection()
    result = db.product_links.insert_one({
        "product_id": product_id,
        "product_url": product_url,
        "site_name": site_name,
        "image_url": image_url,
        "favicon_url": favicon_url,
        "logo_url": logo_url,
        "created_at": datetime.utcnow()
    })
    return str(result.inserted_id)

def log_price(link_id, price):
    """
    Registra um novo preço no histórico
    """
    db = get_db_connection()
    db.price_history.insert_one({
        "link_id": link_id,
        "price": float(price),
        "timestamp": datetime.utcnow()
    })

def get_user_products(user_id):
    """
    Retorna todos os produtos de um usuário com seus links e preços
    """
    db = get_db_connection()
    products = []
    
    for product in db.products.find({"user_id": user_id}):
        product_id = str(product["_id"])
        links = []
        
        # Inicializa as variáveis antes do loop
        lowest_price = float('inf')
        highest_price = 0
        best_price_info = None
        
        for link in db.product_links.find({"product_id": product_id}):
            link_id = str(link["_id"])
            
            # Busca histórico de preços
            price_history = list(db.price_history.find(
                {"link_id": link_id},
                sort=[("timestamp", 1)]
            ))
            
            # Verifica se é um link compartilhado
            original_link = None
            if price_history and "original_link_id" in price_history[0]:
                original_link_id = price_history[0]["original_link_id"]
                original_link = db.product_links.find_one({"_id": ObjectId(original_link_id)})
                if original_link:
                    original_product = db.products.find_one({"_id": original_link["product_id"]})
                    if original_product:
                        original_link["product_name"] = original_product["product_name"]
            
            latest_price = db.price_history.find_one(
                {"link_id": link_id},
                sort=[("timestamp", -1)]
            )
            
            current_price = latest_price["price"] if latest_price else None
            
            if current_price:
                if current_price < lowest_price:
                    lowest_price = current_price
                    best_price_info = {
                        "value": current_price,
                        "link": {
                            "site_name": link["site_name"],
                            "url": link["product_url"]
                        }
                    }
                highest_price = max(highest_price, current_price)
            
            link_data = {
                "id": link_id,
                "url": link["product_url"],
                "site_name": link["site_name"],
                "image_url": link.get("image_url"),
                "favicon_url": link.get("favicon_url"),
                "logo_url": link.get("logo_url"),
                "current_price": current_price,
                "last_update": latest_price["timestamp"] if latest_price else None,
                "price_data": {
                    "prices": [ph["price"] for ph in price_history],
                    "dates": [ph["timestamp"].strftime("%Y-%m-%d %H:%M") for ph in price_history]
                }
            }
            
            # Adiciona informações do link original se existir
            if original_link:
                link_data["shared_from"] = {
                    "product_name": original_link["product_name"],
                    "added_at": original_link["created_at"]
                }
            
            links.append(link_data)
        
        # Calcula a variação de preço
        price_variation = None
        if lowest_price != float('inf') and highest_price > 0:
            price_variation = ((highest_price - lowest_price) / lowest_price) * 100
        
        products.append({
            "id": product_id,
            "name": product["product_name"],
            "links": links,
            "best_price": best_price_info if best_price_info else None,
            "price_variation": price_variation,
            "highest_price": highest_price if highest_price > 0 else None
        })
    
    return products

def get_user_by_id(user_id):
    """
    Busca um usuário pelo ID
    """
    db = get_db_connection()
    return db.users.find_one({"_id": user_id})

def create_or_update_user(user_id, name, email):
    """
    Cria ou atualiza um usuário no MongoDB
    """
    db = get_db_connection()
    db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "name": name,
                "email": email,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    return user_id

def check_link_exists(product_url):
    """
    Verifica se um link já existe e retorna suas informações
    """
    db = get_db_connection()
    link = db.product_links.find_one({"product_url": product_url})
    if link:
        # Busca informações do produto original
        product = db.products.find_one({"_id": link["product_id"]})
        
        # Busca histórico de preços
        price_history = list(db.price_history.find(
            {"link_id": str(link["_id"])},
            sort=[("timestamp", 1)]
        ))
        
        # Busca o preço mais recente
        latest_price = db.price_history.find_one(
            {"link_id": str(link["_id"])},
            sort=[("timestamp", -1)]
        )
        
        return {
            "exists": True,
            "product_name": product["product_name"],
            "product_id": str(product["_id"]),
            "link_id": str(link["_id"]),
            "added_at": link["created_at"],
            "site_name": link.get("site_name"),
            "image_url": link.get("image_url"),
            "favicon_url": link.get("favicon_url"),
            "logo_url": link.get("logo_url"),
            "current_price": latest_price["price"] if latest_price else None,
            "price_history": price_history,
            "user_id": product["user_id"]  # ID do usuário original
        }
    return {"exists": False}

def delete_product_link(link_id):
    """
    Remove um link e seu histórico de preços
    """
    db = get_db_connection()
    try:
        # Remove o histórico de preços primeiro
        db.price_history.delete_many({"link_id": link_id})
        # Remove o link
        db.product_links.delete_one({"_id": ObjectId(link_id)})
        return True
    except Exception as e:
        print(f"Erro ao deletar link: {e}")
        return False

def get_best_price_link(product_id):
    """
    Retorna o link com o melhor preço atual para um produto
    """
    db = get_db_connection()
    links = db.product_links.find({"product_id": product_id})
    best_price = float('inf')
    best_link = None

    for link in links:
        latest_price = db.price_history.find_one(
            {"link_id": str(link["_id"])},
            sort=[("timestamp", -1)]
        )
        if latest_price and latest_price["price"] < best_price:
            best_price = latest_price["price"]
            best_link = {
                "url": link["product_url"],
                "site_name": link["site_name"],
                "price": latest_price["price"],
                "last_update": latest_price["timestamp"]
            }
    
    return best_link

def update_product_name(product_id, new_name):
    """
    Atualiza o nome de um produto
    """
    db = get_db_connection()
    try:
        result = db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"name": new_name}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Erro ao atualizar nome do produto: {e}")
        return False

def create_user(email, password, name):
    """
    Cria um novo usuário com email e senha
    """
    db = get_db_connection()
    
    # Verifica se o email já existe
    if db.users.find_one({"email": email}):
        return None, "Email já cadastrado"
    
    # Hash da senha
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    user = {
        "_id": str(ObjectId()),
        "email": email,
        "password": hashed,
        "name": name,
        "created_at": datetime.utcnow(),
        "auth_type": "email"
    }
    
    try:
        db.users.insert_one(user)
        return user, None
    except Exception as e:
        return None, str(e)

def verify_user(email, password):
    """
    Verifica credenciais do usuário
    """
    db = get_db_connection()
    user = db.users.find_one({"email": email, "auth_type": "email"})
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return user
    return None

def create_or_update_google_user(google_id, email, name):
    """
    Cria ou atualiza usuário do Google
    """
    db = get_db_connection()
    user = db.users.find_one_and_update(
        {"email": email},
        {
            "$set": {
                "google_id": google_id,
                "name": name,
                "auth_type": "google",
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True,
        return_document=True
    )
    return user