import os
import json
from flask import Flask, send_from_directory, request, jsonify

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/menu.json')
def menu():
    return send_from_directory('.', 'menu.json')

@app.route('/health')
def health():
    return 'OK'

@app.route('/api/order', methods=['POST'])
def create_order():
    data = request.json
    order = {
        'id': len(get_orders()) + 1,
        'user_id': data.get('user_id', 'anon'),
        'items': data.get('items', []),
        'total': data.get('total', 0),
        'timestamp': data.get('timestamp', '')
    }
    orders = get_orders()
    orders.append(order)
    save_orders(orders)
    return jsonify({'order_id': order['id'], 'status': 'received'})

def get_orders():
    try:
        with open('orders.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_orders(orders):
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
