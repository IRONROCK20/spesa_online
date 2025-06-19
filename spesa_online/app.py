import os
import json
import time
import requests
from flask import Flask, render_template, redirect, url_for, request
from werkzeug.middleware.proxy_fix import ProxyFix

# Read options from add-on config
PORT = int(os.getenv('PORT', 80))
opts = {}
try:
    opts = json.loads(os.getenv('ADDON_OPTIONS', "{}"))
except Exception:
    pass
GROCY_URL = opts.get('grocy_url') or 'http://grocy:9283'
GROCY_API_KEY = opts.get('grocy_api_key') or ''

app = Flask(__name__, template_folder="templates")
# Secret key for session (if you implement login or other session features)
app.secret_key = os.getenv('SECRET_KEY', 'change_this_to_a_strong_secret')

# Configure session cookies to work in iframe contexts (SameSite=None, Secure)
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# If behind HA ingress proxy, use ProxyFix so url_for
debug_proxy = os.getenv('ENABLE_PROXY_FIX', 'true').lower() in ('true', '1', 'yes')
if debug_proxy:
    # x_proto=1, x_host=1 allow Flask to see X-Forwarded-Proto and Host
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Remove restrictive frame options so the app can be embedded in HA iframe
def remove_frame_options(response):
    response.headers.pop('X-Frame-Options', None)
    # If you have Content-Security-Policy with frame-ancestors, adjust or remove as needed
    # response.headers.pop('Content-Security-Policy', None)
    return response
app.after_request(remove_frame_options)

HEADERS = {'Content-Type': 'application/json', 'GROCY-API-KEY': GROCY_API_KEY}

@app.route('/')
def index():
    return render_template('main.html', products=[])

@app.route('/import')
def import_data():
    # Fetch Grocy shopping list entries
    try:
        url = f"{GROCY_URL}/api/stock/shopping_list"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        items = r.json()
    except Exception as e:
        app.logger.error(f"Error fetching shopping list: {e}")
        items = []

    products = []
    for item in items:
        qty = item.get('amount', 0)
        try:
            prod = requests.get(f"{GROCY_URL}/api/objects/products/{item['product_id']}", headers=HEADERS, timeout=10)
            prod.raise_for_status()
            prod_json = prod.json()
            products.append([qty, prod_json.get('qu_id_purchase_unit', ''), prod_json.get('name', '')])
        except Exception as e:
            app.logger.warning(f"Error fetching product {item.get('product_id')}: {e}")

    # Render appropriate template. If you only have main.html, render it;
    # if you have a separate home.html, ensure the template exists in templates/.
    template_name = 'home.html' if os.path.exists(os.path.join(app.template_folder or '', 'home.html')) else 'main.html'
    return render_template(template_name, products=products)

@app.route('/delete_data')
def delete_data():
    # Delete all shopping list entries
    try:
        url = f"{GROCY_URL}/api/stock/shopping_list"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        items = r.json()
    except Exception as e:
        app.logger.error(f"Error fetching shopping list for delete: {e}")
        items = []
    for item in items:
        try:
            del_url = f"{GROCY_URL}/api/stock/shopping_list/{item['id']}"
            d = requests.delete(del_url, headers=HEADERS, timeout=10)
            d.raise_for_status()
            time.sleep(1)
        except Exception as e:
            app.logger.warning(f"Error deleting shopping list item {item.get('id')}: {e}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Bind to the correct port from environment
    app.run(host='0.0.0.0', port=PORT, debug=False)
