import os
import json
import time
import requests
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps

# Read options from add-on config
PORT = int(os.getenv('PORT', 80))
opts = {}
try:
    opts = json.loads(os.getenv('ADDON_OPTIONS', "{}"))
except Exception:
    pass
GROCY_URL = opts.get('grocy_url') or 'http://grocy:9283'
GROCY_API_KEY = opts.get('grocy_api_key') or ''

# Login credentials: set via ADDON_OPTIONS: 'login_username' and 'login_password'
# Fallback to environment vars or defaults (change defaults in production)
LOGIN_USERNAME = opts.get('login_username') or os.getenv('LOGIN_USERNAME') or 'admin'
LOGIN_PASSWORD = opts.get('login_password') or os.getenv('LOGIN_PASSWORD') or 'admin'

app = Flask(__name__, template_folder="templates")
# Secret key for session
app.secret_key = os.getenv('SECRET_KEY', 'change_this_to_a_strong_secret')

# Configure session cookies to work in iframe contexts
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# Apply ProxyFix if behind HA ingress proxy
debug_proxy = os.getenv('ENABLE_PROXY_FIX', 'true').lower() in ('true', '1', 'yes')
if debug_proxy:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Remove restrictive frame options so the app can be embedded in HA iframe
@app.after_request
def remove_frame_options(response):
    response.headers.pop('X-Frame-Options', None)
    return response

HEADERS = {'Content-Type': 'application/json', 'GROCY-API-KEY': GROCY_API_KEY}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            next_path = request.path
            return redirect(url_for('login', next=next_path))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            session.clear()
            session['logged_in'] = True
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            # Prevent open redirect: ensure next_page is a safe path
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('main.html', products=[])

@app.route('/import')
@login_required
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

    template_name = 'home.html' if os.path.exists(os.path.join(app.template_folder or '', 'home.html')) else 'main.html'
    return render_template(template_name, products=products)

@app.route('/delete_data')
@login_required
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
