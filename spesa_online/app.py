import os
import json
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, flash

# Read options from add-on config
PORT = int(os.getenv('PORT', 80))
opts = {}
try:
    opts = json.loads(os.getenv('ADDON_OPTIONS', '{}'))
except Exception:
    pass
GROCY_URL = opts.get('grocy_url') or os.getenv('GROCY_URL') or 'http://localhost:9254'
GROCY_API_KEY = opts.get('grocy_api_key') or os.getenv('GROCY_API_KEY') or 'ul1YACYf2yJO7UvlwMvV40MkvAQ3IlsrsYtWYa4NavaFQOkWd1'

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', 'change_this_secret')

# Headers for Grocy API
HEADERS = {'Content-Type': 'application/json', 'GROCY-API-KEY': GROCY_API_KEY}

@app.route('/')
def index():
    """Retrieve the current shopping list from Grocy and render the main page."""
    # Fetch Grocy shopping list entries
    products = []
    try:
        url = f"{GROCY_URL}/api/stock/shopping_list"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        items = r.json()
        for item in items:
            # Each item: id, product_id, amount
            item_id = item.get('id')
            qty = item.get('amount', 0)
            # Fetch product details if product_id available
            name = ''
            unit = ''
            pid = item.get('product_id')
            if pid:
                try:
                    pr = requests.get(f"{GROCY_URL}/api/objects/products/{pid}", headers=HEADERS, timeout=10)
                    pr.raise_for_status()
                    prj = pr.json()
                    name = prj.get('name', '')
                    # Get unit name by ID
                    uid = prj.get('qu_id_purchase_unit')
                    if uid:
                        # Fetch unit
                        ur = requests.get(f"{GROCY_URL}/api/objects/quantity_units/{uid}", headers=HEADERS, timeout=10)
                        if ur.ok:
                            uj = ur.json()
                            unit = uj.get('name', '')
                except Exception:
                    # On error, fallback to empty name/unit
                    pass
            products.append({'id': item_id, 'quantity': qty, 'unit': unit, 'name': name})
    except Exception as e:
        flash(f"Error fetching shopping list: {e}", 'error')
    # Default iframe src: soysuper homepage
    iframe_src = 'https://www.soysuper.com'
    return render_template('main.html', products=products, iframe_src=iframe_src)

@app.route('/delete_data', methods=['POST'])
def delete_data():
    """Delete selected shopping list entries in Grocy."""
    selected = request.form.getlist('selected')
    if not selected:
        flash('No items selected for deletion.', 'warning')
        return redirect(url_for('index'))
    errors = []
    for item_id in selected:
        try:
            durl = f"{GROCY_URL}/api/stock/shopping_list/{item_id}"
            d = requests.delete(durl, headers=HEADERS, timeout=10)
            if not d.ok:
                errors.append(f"Failed to delete item {item_id}: {d.status_code}")
        except Exception as e:
            errors.append(f"Error deleting item {item_id}: {e}")
    if errors:
        flash('Errors: ' + '; '.join(errors), 'error')
    else:
        flash('Selected items deleted.', 'success')
    # small delay to allow Grocy to update
    time.sleep(1)
    return redirect(url_for('index'))

@app.route('/search')
def search():
    """Endpoint to set iframe source via query param, redirect to index with iframe src."""
    product = request.args.get('product', '')
    if product:
        # Construct soysuper search URL
        iframe_src = f'https://www.soysuper.com/busca/{product}'
        # Retrieve current shopping list again for rendering
        products = []
        try:
            url = f"{GROCY_URL}/api/stock/shopping_list"
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            items = r.json()
            for item in items:
                item_id = item.get('id')
                qty = item.get('amount', 0)
                name = ''
                unit = ''
                pid = item.get('product_id')
                if pid:
                    try:
                        pr = requests.get(f"{GROCY_URL}/api/objects/products/{pid}", headers=HEADERS, timeout=10)
                        pr.raise_for_status()
                        prj = pr.json()
                        name = prj.get('name', '')
                        uid = prj.get('qu_id_purchase_unit')
                        if uid:
                            ur = requests.get(f"{GROCY_URL}/api/objects/quantity_units/{uid}", headers=HEADERS, timeout=10)
                            if ur.ok:
                                uj = ur.json()
                                unit = uj.get('name', '')
                    except Exception:
                        pass
                products.append({'id': item_id, 'quantity': qty, 'unit': unit, 'name': name})
        except Exception as e:
            flash(f"Error fetching shopping list: {e}", 'error')
        return render_template('home.html', products=products, iframe_src=iframe_src)
    else:
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
