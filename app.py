import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, g
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)

from utils.ocr_processor import extract_text_from_image
from utils.parser import parse_receipt_text
from utils.categorizer import categorize_expense

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['SECRET_KEY'] = 'sheen-expense-tracker-secret-key-2026'
app.config['DATABASE'] = 'sheen.db'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ---- Flask-Login ----
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        return User(user['id'], user['email'], user['name'])
    return None


# ---- SQLite helpers ----
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            merchant TEXT,
            amount REAL,
            date TEXT,
            category TEXT DEFAULT 'Uncategorized',
            raw_text TEXT,
            image_path TEXT,
            needs_review INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key)
        );
    ''')
    db.commit()
    db.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ======================= AUTH ROUTES =======================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not name or not email or not password:
        return render_template('register.html', error="All fields are required.")
    if len(password) < 6:
        return render_template('register.html', error="Password must be at least 6 characters.")

    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing:
        return render_template('register.html', error="An account with this email already exists.")

    hashed_pw = generate_password_hash(password)
    db.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
               (name, email, hashed_pw))
    db.commit()

    user_row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    user = User(user_row['id'], user_row['email'], user_row['name'])
    login_user(user)
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    db = get_db()
    user_row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    if not user_row or not check_password_hash(user_row['password'], password):
        return render_template('login.html', error="Invalid email or password.")

    user = User(user_row['id'], user_row['email'], user_row['name'])
    login_user(user)
    return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ======================= MAIN ROUTES =======================

@app.route('/')
@login_required
def index():
    return render_template('index.html', user_name=current_user.name)


@app.route('/upload', methods=['POST'])
@login_required
def upload_receipt():
    if 'receipt_image' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['receipt_image']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Use png/jpg/jpeg"}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    saved_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(filepath)

    raw_text = extract_text_from_image(filepath)
    parsed_data = parse_receipt_text(raw_text)
    category = categorize_expense(parsed_data.get('merchant', ''), raw_text)
    needs_review = 1 if parsed_data.get('amount') is None else 0

    db = get_db()
    cursor = db.execute(
        '''INSERT INTO receipts (user_id, merchant, amount, date, category, raw_text, image_path, needs_review, uploaded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (current_user.id, parsed_data.get('merchant'), parsed_data.get('amount'),
         parsed_data.get('date'), category, raw_text, filepath, needs_review,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    db.commit()

    return jsonify({"success": True, "data": {
        "_id": cursor.lastrowid,
        "merchant": parsed_data.get('merchant'),
        "amount": parsed_data.get('amount'),
        "date": parsed_data.get('date'),
        "category": category,
        "needs_review": bool(needs_review)
    }})


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user_name=current_user.name)


@app.route('/gallery')
@login_required
def gallery():
    return render_template('gallery.html', user_name=current_user.name)


@app.route('/api/receipts', methods=['GET'])
@login_required
def get_receipts():
    db = get_db()
    category_filter = request.args.get('category')

    if category_filter:
        rows = db.execute(
            'SELECT * FROM receipts WHERE user_id = ? AND category = ? ORDER BY uploaded_at DESC',
            (current_user.id, category_filter)
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT * FROM receipts WHERE user_id = ? ORDER BY uploaded_at DESC',
            (current_user.id,)
        ).fetchall()

    receipts = []
    for r in rows:
        rec = dict(r)
        rec['_id'] = rec['id']
        rec['needs_review'] = bool(rec['needs_review'])
        if rec.get('image_path'):
            rec['image_url'] = '/' + rec['image_path'].replace('\\', '/')
        receipts.append(rec)

    return jsonify(receipts)


@app.route('/api/summary', methods=['GET'])
@login_required
def get_summary():
    db = get_db()
    rows = db.execute(
        '''SELECT category, SUM(amount) as total, COUNT(*) as count
           FROM receipts WHERE user_id = ?
           GROUP BY category''',
        (current_user.id,)
    ).fetchall()

    summary = [{"category": r['category'] or 'Uncategorized',
                "total": r['total'] or 0,
                "count": r['count']} for r in rows]
    return jsonify(summary)


@app.route('/api/income', methods=['GET'])
@login_required
def get_income():
    db = get_db()
    row = db.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (current_user.id, 'monthly_income')
    ).fetchone()
    income = float(row['value']) if row else 0
    return jsonify({"monthly_income": income})


@app.route('/api/income', methods=['POST'])
@login_required
def set_income():
    data = request.json
    amount = data.get('amount')
    try:
        amount = float(amount)
        if amount < 0:
            return jsonify({"error": "Amount cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a number"}), 400

    db = get_db()
    db.execute(
        'INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) ON CONFLICT(user_id, key) DO UPDATE SET value = ?',
        (current_user.id, 'monthly_income', str(amount), str(amount))
    )
    db.commit()
    return jsonify({"success": True, "monthly_income": amount})


@app.route('/api/budget', methods=['GET'])
@login_required
def get_budget():
    db = get_db()
    row = db.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (current_user.id, 'monthly_income')
    ).fetchone()
    income = float(row['value']) if row else 0

    now = datetime.now()
    start_of_month = now.strftime('%Y-%m-01')

    result = db.execute(
        'SELECT SUM(amount) as total FROM receipts WHERE user_id = ? AND uploaded_at >= ?',
        (current_user.id, start_of_month)
    ).fetchone()
    total_spent = result['total'] if result['total'] else 0

    remaining = income - total_spent
    percent_used = round((total_spent / income * 100), 1) if income > 0 else 0

    return jsonify({
        "monthly_income": income,
        "total_spent": total_spent,
        "remaining": remaining,
        "percent_used": percent_used
    })


@app.route('/api/category-limits', methods=['GET'])
@login_required
def get_category_limits():
    import json
    db = get_db()
    row = db.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (current_user.id, 'category_limits')
    ).fetchone()
    limits = json.loads(row['value']) if row else {}
    return jsonify(limits)


@app.route('/api/category-limits', methods=['POST'])
@login_required
def set_category_limit():
    import json
    data = request.json
    category = data.get('category')
    limit = data.get('limit')

    try:
        limit = float(limit)
    except (ValueError, TypeError):
        return jsonify({"error": "Limit must be a number"}), 400

    db = get_db()
    row = db.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (current_user.id, 'category_limits')
    ).fetchone()
    limits = json.loads(row['value']) if row else {}
    limits[category] = limit

    db.execute(
        'INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) ON CONFLICT(user_id, key) DO UPDATE SET value = ?',
        (current_user.id, 'category_limits', json.dumps(limits), json.dumps(limits))
    )
    db.commit()
    return jsonify({"success": True})


@app.route('/api/category-status', methods=['GET'])
@login_required
def get_category_status():
    import json
    db = get_db()
    row = db.execute(
        'SELECT value FROM settings WHERE user_id = ? AND key = ?',
        (current_user.id, 'category_limits')
    ).fetchone()
    limits = json.loads(row['value']) if row else {}

    now = datetime.now()
    start_of_month = now.strftime('%Y-%m-01')

    rows = db.execute(
        '''SELECT category, SUM(amount) as spent FROM receipts
           WHERE user_id = ? AND uploaded_at >= ?
           GROUP BY category''',
        (current_user.id, start_of_month)
    ).fetchall()

    spend_by_category = {r['category'] or 'Uncategorized': (r['spent'] or 0) for r in rows}
    all_categories = set(limits.keys()) | set(spend_by_category.keys())
    status_list = []

    for cat in all_categories:
        spent = spend_by_category.get(cat, 0)
        limit = limits.get(cat)
        if limit and limit > 0:
            percent = round((spent / limit) * 100, 1)
            status = "over" if percent >= 100 else ("warn" if percent >= 80 else "ok")
        else:
            percent = None
            status = "no_limit"

        status_list.append({"category": cat, "spent": spent, "limit": limit,
                            "percent": percent, "status": status})

    order = {"over": 0, "warn": 1, "ok": 2, "no_limit": 3}
    status_list.sort(key=lambda x: order[x["status"]])
    return jsonify(status_list)


@app.route('/api/monthly-comparison', methods=['GET'])
@login_required
def get_monthly_comparison():
    db = get_db()
    now = datetime.now()

    current_month = now.strftime('%Y-%m')
    if now.month == 1:
        prev_month = f"{now.year - 1}-12"
    else:
        prev_month = f"{now.year}-{now.month - 1:02d}"

    rows = db.execute(
        '''SELECT category, strftime('%Y-%m', uploaded_at) as month, SUM(amount) as total
           FROM receipts WHERE user_id = ?
           AND strftime('%Y-%m', uploaded_at) IN (?, ?)
           GROUP BY category, month''',
        (current_user.id, current_month, prev_month)
    ).fetchall()

    current_spend = {}
    previous_spend = {}
    for r in rows:
        cat = r['category'] or 'Uncategorized'
        if r['month'] == current_month:
            current_spend[cat] = r['total'] or 0
        else:
            previous_spend[cat] = r['total'] or 0

    all_categories = set(current_spend.keys()) | set(previous_spend.keys())
    comparison = []
    for cat in all_categories:
        curr = current_spend.get(cat, 0)
        prev = previous_spend.get(cat, 0)
        percent_change = round(((curr - prev) / prev) * 100, 1) if prev > 0 else (100.0 if curr > 0 else 0.0)
        comparison.append({
            "category": cat, "current_month": curr, "previous_month": prev,
            "percent_change": percent_change,
            "direction": "up" if percent_change > 0 else ("down" if percent_change < 0 else "flat")
        })

    comparison.sort(key=lambda x: abs(x["percent_change"]), reverse=True)
    from calendar import month_name
    return jsonify({
        "current_month_label": now.strftime("%B %Y"),
        "previous_month_label": f"{month_name[int(prev_month.split('-')[1])]} {prev_month.split('-')[0]}",
        "categories": comparison
    })


@app.route('/api/receipt/<int:receipt_id>', methods=['PUT'])
@login_required
def update_receipt(receipt_id):
    updates = request.json
    allowed_fields = {'merchant', 'amount', 'date', 'category'}
    db = get_db()
    for field in allowed_fields:
        if field in updates:
            db.execute(
                f'UPDATE receipts SET {field} = ? WHERE id = ? AND user_id = ?',
                (updates[field], receipt_id, current_user.id)
            )
    db.execute('UPDATE receipts SET needs_review = 0 WHERE id = ? AND user_id = ?',
               (receipt_id, current_user.id))
    db.commit()
    return jsonify({"success": True})


@app.route('/api/receipt/<int:receipt_id>', methods=['DELETE'])
@login_required
def delete_receipt(receipt_id):
    db = get_db()
    db.execute('DELETE FROM receipts WHERE id = ? AND user_id = ?',
               (receipt_id, current_user.id))
    db.commit()
    return jsonify({"success": True})


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)
