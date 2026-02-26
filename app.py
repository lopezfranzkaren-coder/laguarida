"""
La Guarida — Calculadora de Costos
Flask + SQLite | Login por contraseña
"""
import os, sqlite3
from flask import Flask, g, jsonify, request, send_from_directory, session, redirect

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "datos.db")
app          = Flask(__name__, static_folder=BASE_DIR)
app.secret_key  = os.environ.get("SECRET_KEY", "guarida-secret-2024")
APP_PASSWORD    = os.environ.get("APP_PASSWORD", "laiguarida2024")

@app.before_request
def check_auth():
    if request.path in ["/login"] or request.path.startswith("/static"):
        return
    if not session.get("ok"):
        if request.path.startswith("/api"):
            return jsonify({"error": "no autorizado"}), 401
        return redirect("/login")

@app.route("/login", methods=["GET"])
def login_page():
    return send_from_directory(BASE_DIR, "login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    if data.get("password") == APP_PASSWORD:
        session["ok"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Contraseña incorrecta"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def rows_to_list(rows):
    return [dict(r) for r in rows]

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        costo_base REAL,
        activo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS insumos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        costo REAL NOT NULL,
        descripcion TEXT
    );
    CREATE TABLE IF NOT EXISTS recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        insumo_id INTEGER NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'ambos',
        UNIQUE(producto_id, insumo_id),
        FOREIGN KEY(producto_id) REFERENCES productos(id),
        FOREIGN KEY(insumo_id) REFERENCES insumos(id)
    );
    CREATE TABLE IF NOT EXISTS gastos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL UNIQUE,
        monto REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS config (
        clave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT,
        fecha TEXT NOT NULL,
        cliente TEXT NOT NULL,
        telefono TEXT,
        provincia TEXT,
        transporte TEXT,
        tipo_pago TEXT DEFAULT 'transferencia',
        estado TEXT DEFAULT 'pendiente',
        observaciones TEXT,
        total REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS pedido_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        producto TEXT NOT NULL,
        cantidad INTEGER NOT NULL,
        precio_unitario REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
    );
    CREATE TABLE IF NOT EXISTS precios_mayoristas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad TEXT NOT NULL,
        precio REAL,
        UNIQUE(producto_id, cantidad),
        FOREIGN KEY(producto_id) REFERENCES productos(id)
    );
    CREATE TABLE IF NOT EXISTS precios_minoristas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL UNIQUE,
        precio REAL,
        FOREIGN KEY(producto_id) REFERENCES productos(id)
    );
    """)

    if db.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
        prods = [
            ("Taza de ceramica",1500),("Vasos",1460),("Chopp",3700),
            ("Botella",2100),("Hoppy m",4790),("Posavasos",620),
            ("Stickers",180),("Tazones",6900),("Termos 900 ml",6800),
            ("Straw",10200),("Push",None),("XL",None),("Latas",7870),
            ("Glitter",10200),("Hoppy",3500),("Vaso sublimado",3200),
            ("Taza plastica",920),("Jarros termicos",2400),("Llavero",500),
            ("Taza 3D",10060),("Remeras",4500),("Taza magica 3d",2900),
            ("Taza con boca",1500),("Enlozados",3500),("Gorra",2500),
            ("Promos vaso grabado",1330),("Vaso Fluor",10600),("Corcho",5000),
            ("Sensor",7400),("Redondo 2 estampas",10000),("Cangiro",20200),
            ("Tarjeta",927),("XL 1.2",17000),("Torre",None),
        ]
        db.executemany("INSERT OR IGNORE INTO productos (nombre,costo_base) VALUES (?,?)", prods)

    if db.execute("SELECT COUNT(*) FROM insumos").fetchone()[0] == 0:
        ins = [
            ("Argollita",110,"por llavero"),("Hoja",140,"por hoja"),
            ("Tinta",100,"por hoja"),("Imanes",170,"por cada uno"),
            ("Vinilo",500,"hoja A4"),("Grabado",200,"por cada 20 min"),
            ("Madera",800,"plancha A4"),("UV",180,""),
            ("DTF",1750,"por remera / 6 por gorra"),("Embalaje",100,""),
            ("Caja",350,"por unidad"),("Bolsa",128,"por unidad"),
            ("Bolsita remeras",500,"por unidad"),
        ]
        db.executemany("INSERT OR IGNORE INTO insumos (nombre,costo,descripcion) VALUES (?,?,?)", ins)

    if db.execute("SELECT COUNT(*) FROM gastos_fijos").fetchone()[0] == 0:
        db.executemany("INSERT OR IGNORE INTO gastos_fijos (item,monto) VALUES (?,?)", [
            ("Alquiler",720000),("Sueldos",3000000),("Luz",70000),
            ("Expensas",90000),("Agua",35000),("Internet",30000),
            ("Alarma",39000),("ABL",12000),("Publicidad",350000),
        ])

    defaults = [
        ("pct_variables","0.44"),("desc_transferencia","0.05"),
        ("desc_efectivo","0.10"),("comision_qr_debito","0.0135"),
        ("comision_qr_credito","0.0629"),("comision_3cuotas","0.086"),
        ("inflacion_q1_2025","0.08"),("inflacion_q2_2025","0.11"),
        ("inflacion_q3_2025","0.09"),("inflacion_q4_2025","0.07"),
        ("inflacion_q1_2026","0.00"),("inflacion_q2_2026","0.00"),
        ("last_update",""),("logo_data",""),
    ]
    for clave, valor in defaults:
        db.execute("INSERT OR IGNORE INTO config (clave,valor) VALUES (?,?)", (clave, valor))

    db.commit()
    db.close()

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

# CONFIG
@app.route("/api/config", methods=["GET"])
def get_config():
    rows = get_db().execute("SELECT clave,valor FROM config").fetchall()
    return jsonify({r["clave"]: r["valor"] for r in rows})

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.json or {}
    db = get_db()
    for clave, valor in data.items():
        db.execute("INSERT OR REPLACE INTO config (clave,valor) VALUES (?,?)", (clave, str(valor)))
    db.commit()
    return jsonify({"ok": True})

# PRODUCTOS
@app.route("/api/productos", methods=["GET"])
def get_productos():
    rows = get_db().execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/productos", methods=["POST"])
def add_producto():
    d = request.json
    try:
        get_db().execute("INSERT INTO productos (nombre,costo_base) VALUES (?,?)", (d["nombre"], d.get("costo_base")))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Ya existe"}), 400

@app.route("/api/productos/<int:pid>", methods=["PUT"])
def upd_producto(pid):
    d = request.json
    db = get_db()
    db.execute("UPDATE productos SET nombre=?,costo_base=? WHERE id=?", (d["nombre"], d.get("costo_base"), pid))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/productos/<int:pid>", methods=["DELETE"])
def del_producto(pid):
    db = get_db()
    db.execute("UPDATE productos SET activo=0 WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})

# INSUMOS
@app.route("/api/insumos", methods=["GET"])
def get_insumos():
    rows = get_db().execute("SELECT * FROM insumos ORDER BY nombre").fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/insumos", methods=["POST"])
def add_insumo():
    d = request.json
    try:
        get_db().execute("INSERT INTO insumos (nombre,costo,descripcion) VALUES (?,?,?)", (d["nombre"], d["costo"], d.get("descripcion","")))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Ya existe"}), 400

@app.route("/api/insumos/<int:iid>", methods=["PUT"])
def upd_insumo(iid):
    d = request.json
    db = get_db()
    db.execute("UPDATE insumos SET nombre=?,costo=?,descripcion=? WHERE id=?", (d["nombre"], d["costo"], d.get("descripcion",""), iid))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/insumos/<int:iid>", methods=["DELETE"])
def del_insumo(iid):
    db = get_db()
    db.execute("DELETE FROM insumos WHERE id=?", (iid,))
    db.commit()
    return jsonify({"ok": True})

# RECETAS
@app.route("/api/recetas/<int:pid>", methods=["GET"])
def get_receta(pid):
    rows = get_db().execute(
        "SELECT r.*, i.nombre as insumo_nombre, i.costo as insumo_costo "
        "FROM recetas r JOIN insumos i ON r.insumo_id=i.id WHERE r.producto_id=?", (pid,)
    ).fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/recetas/<int:pid>", methods=["POST"])
def save_receta(pid):
    items = request.json or []
    db = get_db()
    db.execute("DELETE FROM recetas WHERE producto_id=?", (pid,))
    for item in items:
        db.execute("INSERT OR IGNORE INTO recetas (producto_id,insumo_id,tipo) VALUES (?,?,?)",
                   (pid, item["insumo_id"], item.get("tipo","ambos")))
    db.commit()
    return jsonify({"ok": True})

# PRECIOS MINORISTAS
@app.route("/api/precios_minoristas", methods=["GET"])
def get_precios_min():
    rows = get_db().execute("SELECT * FROM precios_minoristas").fetchall()
    return jsonify({r["producto_id"]: r["precio"] for r in rows})

@app.route("/api/precios_minoristas/<int:pid>", methods=["POST"])
def set_precio_min(pid):
    d = request.json
    db = get_db()
    db.execute("INSERT OR REPLACE INTO precios_minoristas (producto_id,precio) VALUES (?,?)", (pid, d.get("precio")))
    db.commit()
    return jsonify({"ok": True})

# PRECIOS MAYORISTAS
@app.route("/api/precios_mayoristas", methods=["GET"])
def get_precios_mayor():
    rows = get_db().execute("SELECT * FROM precios_mayoristas").fetchall()
    result = {}
    for r in rows:
        pid = r["producto_id"]
        if pid not in result: result[pid] = {}
        result[pid][r["cantidad"]] = r["precio"]
    return jsonify(result)

@app.route("/api/precios_mayoristas/<int:pid>", methods=["POST"])
def set_precio_mayor(pid):
    data = request.json or {}
    db = get_db()
    for cantidad, precio in data.items():
        db.execute("INSERT OR REPLACE INTO precios_mayoristas (producto_id,cantidad,precio) VALUES (?,?,?)", (pid, cantidad, precio))
    db.commit()
    return jsonify({"ok": True})

# GASTOS
@app.route("/api/gastos", methods=["GET"])
def get_gastos():
    rows = get_db().execute("SELECT * FROM gastos_fijos ORDER BY item").fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/gastos", methods=["POST"])
def add_gasto():
    d = request.json
    try:
        get_db().execute("INSERT INTO gastos_fijos (item,monto) VALUES (?,?)", (d["item"], d["monto"]))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Ya existe"}), 400

@app.route("/api/gastos/<int:gid>", methods=["PUT"])
def upd_gasto(gid):
    d = request.json
    db = get_db()
    db.execute("UPDATE gastos_fijos SET item=?,monto=? WHERE id=?", (d["item"], d["monto"], gid))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/gastos/<int:gid>", methods=["DELETE"])
def del_gasto(gid):
    db = get_db()
    db.execute("DELETE FROM gastos_fijos WHERE id=?", (gid,))
    db.commit()
    return jsonify({"ok": True})

# PEDIDOS
@app.route("/api/pedidos", methods=["GET"])
def get_pedidos():
    db = get_db()
    rows = db.execute("SELECT * FROM pedidos ORDER BY fecha DESC, id DESC").fetchall()
    result = []
    for r in rows:
        p = dict(r)
        items = db.execute("SELECT * FROM pedido_items WHERE pedido_id=?", (p["id"],)).fetchall()
        p["items"] = rows_to_list(items)
        result.append(p)
    return jsonify(result)

@app.route("/api/pedidos", methods=["POST"])
def add_pedido():
    d = request.json
    items = d.pop("items", [])
    total = sum(i["subtotal"] for i in items)
    db = get_db()
    cur = db.execute(
        "INSERT INTO pedidos (numero,fecha,cliente,telefono,provincia,transporte,tipo_pago,estado,observaciones,total) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d.get("numero",""), d["fecha"], d["cliente"], d.get("telefono",""),
         d.get("provincia",""), d.get("transporte",""), d.get("tipo_pago","transferencia"),
         d.get("estado","pendiente"), d.get("observaciones",""), total)
    )
    pid = cur.lastrowid
    for i in items:
        db.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",
                   (pid, i["producto"], i["cantidad"], i["precio_unitario"], i["subtotal"]))
    db.commit()
    return jsonify({"ok": True, "id": pid})

@app.route("/api/pedidos/<int:pid>", methods=["PUT"])
def upd_pedido(pid):
    d = request.json
    items = d.pop("items", [])
    total = sum(i["subtotal"] for i in items)
    db = get_db()
    db.execute(
        "UPDATE pedidos SET numero=?,fecha=?,cliente=?,telefono=?,provincia=?,transporte=?,tipo_pago=?,estado=?,observaciones=?,total=? WHERE id=?",
        (d.get("numero",""), d["fecha"], d["cliente"], d.get("telefono",""),
         d.get("provincia",""), d.get("transporte",""), d.get("tipo_pago","transferencia"),
         d.get("estado","pendiente"), d.get("observaciones",""), total, pid)
    )
    db.execute("DELETE FROM pedido_items WHERE pedido_id=?", (pid,))
    for i in items:
        db.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",
                   (pid, i["producto"], i["cantidad"], i["precio_unitario"], i["subtotal"]))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/pedidos/<int:pid>", methods=["DELETE"])
def del_pedido(pid):
    db = get_db()
    db.execute("DELETE FROM pedido_items WHERE pedido_id=?", (pid,))
    db.execute("DELETE FROM pedidos WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/clientes", methods=["GET"])
def get_clientes():
    rows = get_db().execute("""
        SELECT cliente, telefono, provincia,
               COUNT(DISTINCT id) as num_pedidos,
               MAX(fecha) as ultimo_pedido,
               SUM(CASE WHEN fecha LIKE '2025%' THEN total ELSE 0 END) as total_2025,
               SUM(CASE WHEN fecha LIKE '2026%' THEN total ELSE 0 END) as total_2026,
               SUM(total) as total_acumulado
        FROM pedidos GROUP BY cliente ORDER BY total_acumulado DESC
    """).fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/clientes/<path:nombre>/pedidos", methods=["GET"])
def get_cliente_pedidos(nombre):
    db = get_db()
    rows = db.execute("SELECT * FROM pedidos WHERE cliente=? ORDER BY fecha DESC", (nombre,)).fetchall()
    result = []
    for r in rows:
        p = dict(r)
        items = db.execute("SELECT * FROM pedido_items WHERE pedido_id=?", (p["id"],)).fetchall()
        p["items"] = rows_to_list(items)
        result.append(p)
    return jsonify(result)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

init_db()
