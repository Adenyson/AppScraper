from flask import Flask, render_template, request, send_from_directory
from utils import init_db, get_product_prices, add_product, add_product_link
import os

app = Flask(__name__)

# Inicializa o banco de dados
init_db()

@app.route('/')
def index():
    product_id = request.args.get('product_id', default=1, type=int)
    prices = get_product_prices(product_id)
    return send_from_directory(os.getcwd(), 'index.html')

@app.route('/add_product', methods=['POST'])
def add_new_product():
    product_name = request.form['product_name']
    product_id = add_product(product_name)
    return f"Produto '{product_name}' adicionado com ID {product_id}"

@app.route('/add_link', methods=['POST'])
def add_link():
    product_id = int(request.form['product_id'])
    product_url = request.form['product_url']
    site_name = request.form['site_name']
    link_id = add_product_link(product_id, product_url, site_name)
    return f"Link adicionado com ID {link_id} para o produto {product_id}"

if __name__ == "__main__":
    app.run(debug=True)
