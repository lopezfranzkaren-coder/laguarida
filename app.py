"""
Calculadora de Costos — La Guarida
App web con Flask + SQLite, con login por contraseña
"""
import os, sqlite3, json
from flask import Flask, g, jsonify, request, send_from_directory, session, redirect

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "datos.db")
app          = Flask(__name__, static_folder=BASE_DIR)
app.secret_key  = os.environ.get("SECRET_KEY", "guarida-secret-2024")
APP_PASSWORD    = os.environ.get("APP_PASSWORD", "laiguarida2024")

# ─── Auth ─────────────────────────────────────────────────────────────────────
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

# ─── DB helpers ───────────────────────────────────────────────────────────────
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

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        costo REAL NOT NULL,
        activo INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS gastos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL UNIQUE,
        monto REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ventas_mensuales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto TEXT NOT NULL,
        mes TEXT NOT NULL,
        anio INTEGER NOT NULL,
        cantidad INTEGER NOT NULL DEFAULT 0,
        UNIQUE(producto, mes, anio)
    );
    CREATE TABLE IF NOT EXISTS cotizaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        cliente TEXT,
        descripcion TEXT NOT NULL,
        detalle_json TEXT NOT NULL,
        subtotal REAL NOT NULL,
        costo_final REAL NOT NULL,
        precio_venta REAL NOT NULL,
        margen_pct REAL NOT NULL,
        estado TEXT DEFAULT 'borrador'
    );
    """)
    if db.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
        db.executemany("INSERT OR IGNORE INTO productos (nombre, costo) VALUES (?,?)", [
            ("Taza de ceramica", 3050), ("Vasos", 3180), ("Chopp", 7000),
            ("Botella", 4000), ("Hoppy m", 7430), ("Posavasos", 900),
            ("Stickers", 180), ("Tazones", 10270), ("Termos 900 ml", 10320),
            ("Straw", 15270), ("Push", 12020), ("XL", 12620), ("Latas", 12350),
            ("Glitter", 15420), ("Hoppy", 6200), ("Vaso sublimado", 4970),
            ("Taza plastica", 1800), ("Jarros termicos", 3850), ("Llavero", 500),
            ("Taza 3D", 10060), ("Remeras", 8480), ("Taza magica 3d", 4890),
            ("Taza con boca", 3554), ("Enlozados", 7300), ("Gorra", 4010),
            ("Promo vaso grabado", 2270), ("Vaso Fluor", 12800), ("Corcho", 9000),
            ("Sensor", 9300), ("Redondo 2 estampas", 17000), ("Cangiro", 21800),
            ("Tarjeta", 927), ("XL 1.2", 21400), ("Torre", 13650),
        ])
    if db.execute("SELECT COUNT(*) FROM gastos_fijos").fetchone()[0] == 0:
        db.executemany("INSERT OR IGNORE INTO gastos_fijos (item, monto) VALUES (?,?)", [
            ("Alquiler", 720000), ("Sueldos", 3000000), ("Luz", 70000),
            ("Expensas", 90000), ("Agua", 35000), ("Internet", 30000),
            ("Alarma", 39000), ("ABL", 12000), ("Publicidad", 350000),
        ])
    db.commit()
    db.close()

# ─── Static ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

# ─── PRODUCTOS ────────────────────────────────────────────────────────────────
@app.route("/api/productos", methods=["GET"])
def get_productos():
    rows = get_db().execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/productos", methods=["POST"])
def add_producto():
    data = request.json
    try:
        get_db().execute("INSERT INTO productos (nombre, costo) VALUES (?,?)", (data["nombre"], data["costo"]))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Ya existe un producto con ese nombre"}), 400

@app.route("/api/productos/<int:pid>", methods=["PUT"])
def update_producto(pid):
    data = request.json
    db = get_db()
    db.execute("UPDATE productos SET nombre=?, costo=? WHERE id=?", (data["nombre"], data["costo"], pid))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/productos/<int:pid>", methods=["DELETE"])
def delete_producto(pid):
    db = get_db()
    db.execute("UPDATE productos SET activo=0 WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})

# ─── GASTOS FIJOS ─────────────────────────────────────────────────────────────
@app.route("/api/gastos", methods=["GET"])
def get_gastos():
    rows = get_db().execute("SELECT * FROM gastos_fijos ORDER BY item").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/gastos", methods=["POST"])
def add_gasto():
    data = request.json
    try:
        get_db().execute("INSERT INTO gastos_fijos (item, monto) VALUES (?,?)", (data["item"], data["monto"]))
        get_db().commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Ya existe ese gasto"}), 400

@app.route("/api/gastos/<int:gid>", methods=["PUT"])
def update_gasto(gid):
    data = request.json
    db = get_db()
    db.execute("UPDATE gastos_fijos SET item=?, monto=? WHERE id=?", (data["item"], data["monto"], gid))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/gastos/<int:gid>", methods=["DELETE"])
def delete_gasto(gid):
    db = get_db()
    db.execute("DELETE FROM gastos_fijos WHERE id=?", (gid,))
    db.commit()
    return jsonify({"ok": True})

# ─── VENTAS ───────────────────────────────────────────────────────────────────
@app.route("/api/ventas", methods=["GET"])
def get_ventas():
    anio = request.args.get("anio", 2025)
    rows = get_db().execute(
        "SELECT * FROM ventas_mensuales WHERE anio=? ORDER BY producto, mes", (anio,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/ventas", methods=["POST"])
def upsert_venta():
    data = request.json
    db = get_db()
    db.execute("""
        INSERT INTO ventas_mensuales (producto, mes, anio, cantidad)
        VALUES (?,?,?,?)
        ON CONFLICT(producto, mes, anio) DO UPDATE SET cantidad=excluded.cantidad
    """, (data["producto"], data["mes"], data["anio"], data["cantidad"]))
    db.commit()
    return jsonify({"ok": True})

# ─── COTIZACIONES ─────────────────────────────────────────────────────────────
@app.route("/api/cotizaciones", methods=["GET"])
def get_cotizaciones():
    rows = get_db().execute("SELECT * FROM cotizaciones ORDER BY fecha DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["detalle_json"] = json.loads(d["detalle_json"])
        result.append(d)
    return jsonify(result)

@app.route("/api/cotizaciones", methods=["POST"])
def add_cotizacion():
    data = request.json
    db = get_db()
    db.execute("""
        INSERT INTO cotizaciones
        (fecha, cliente, descripcion, detalle_json, subtotal, costo_final, precio_venta, margen_pct, estado)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        data["fecha"], data.get("cliente",""), data["descripcion"],
        json.dumps(data["detalle_json"]),
        data["subtotal"], data["costo_final"], data["precio_venta"],
        data["margen_pct"], data.get("estado","borrador")
    ))
    db.commit()
    return jsonify({"ok": True, "id": db.execute("SELECT last_insert_rowid()").fetchone()[0]})

@app.route("/api/cotizaciones/<int:cid>", methods=["PUT"])
def update_cotizacion(cid):
    data = request.json
    db = get_db()
    db.execute("""
        UPDATE cotizaciones SET
        fecha=?, cliente=?, descripcion=?, detalle_json=?,
        subtotal=?, costo_final=?, precio_venta=?, margen_pct=?, estado=?
        WHERE id=?
    """, (
        data["fecha"], data.get("cliente",""), data["descripcion"],
        json.dumps(data["detalle_json"]),
        data["subtotal"], data["costo_final"], data["precio_venta"],
        data["margen_pct"], data.get("estado","borrador"), cid
    ))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/cotizaciones/<int:cid>", methods=["DELETE"])
def delete_cotizacion(cid):
    db = get_db()
    db.execute("DELETE FROM cotizaciones WHERE id=?", (cid,))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/cotizaciones/<int:cid>/estado", methods=["PUT"])
def update_estado(cid):
    db = get_db()
    db.execute("UPDATE cotizaciones SET estado=? WHERE id=?", (request.json["estado"], cid))
    db.commit()
    return jsonify({"ok": True})

# ─── Stats ────────────────────────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def get_stats():
    db = get_db()
    return jsonify({
        "n_productos":    db.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0],
        "total_fijos":    db.execute("SELECT COALESCE(SUM(monto),0) FROM gastos_fijos").fetchone()[0],
        "n_cotizaciones": db.execute("SELECT COUNT(*) FROM cotizaciones").fetchone()[0],
        "aprobadas":      db.execute("SELECT COUNT(*) FROM cotizaciones WHERE estado='aprobada'").fetchone()[0],
        "vol_aprobado":   db.execute("SELECT COALESCE(SUM(precio_venta),0) FROM cotizaciones WHERE estado='aprobada'").fetchone()[0],
    })

# ─── Boot ─────────────────────────────────────────────────────────────────────
init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=False)
