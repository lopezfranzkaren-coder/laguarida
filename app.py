"""
La Guarida — Flask + PostgreSQL (Supabase) | Login por contraseña
"""
import os
from flask import Flask, g, jsonify, request, send_from_directory, session, redirect

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
app          = Flask(__name__, static_folder=BASE_DIR)
app.secret_key  = os.environ.get("SECRET_KEY", "guarida-secret-2024")
APP_PASSWORD    = os.environ.get("APP_PASSWORD", "laiguarida2024")
DATABASE_URL    = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2, psycopg2.extras
else:
    import sqlite3
    DB_PATH = os.path.join(BASE_DIR, "datos.db")

def get_db():
    if "db" not in g:
        if USE_PG:
            g.db = psycopg2.connect(DATABASE_URL)
        else:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        try: db.close()
        except: pass

def q(sql, params=()):
    db = get_db()
    if USE_PG:
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    else:
        return [dict(r) for r in db.execute(sql, params).fetchall()]

def ex(sql, params=(), commit=True):
    db = get_db()
    if USE_PG:
        cur = db.cursor()
        cur.execute(sql, params)
        lid = None
        try:
            row = cur.fetchone()
            lid = row[0] if row else None
        except: pass
        if commit: db.commit()
        return lid
    else:
        cur = db.execute(sql, params)
        if commit: db.commit()
        return cur.lastrowid

def P(n=1):
    """Return n placeholders: %s for PG, ? for SQLite"""
    if USE_PG: return ",".join(["%s"]*n)
    return ",".join(["?"]*n)

def ph():
    return "%s" if USE_PG else "?"

# ─── Auth ──────────────────────────────────────────────────────────────────────
@app.before_request
def check_auth():
    if request.path in ["/login"] or request.path.startswith("/static"): return
    if not session.get("ok"):
        if request.path.startswith("/api"): return jsonify({"error":"no autorizado"}),401
        return redirect("/login")

@app.route("/login", methods=["GET"])
def login_page(): return send_from_directory(BASE_DIR, "login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    if data.get("password") == APP_PASSWORD:
        session["ok"] = True; return jsonify({"ok":True})
    return jsonify({"ok":False,"error":"Contraseña incorrecta"}),401

@app.route("/logout")
def logout(): session.clear(); return redirect("/login")

# ─── Init DB ───────────────────────────────────────────────────────────────────
def init_db():
    db = get_db()
    p = ph()
    if USE_PG:
        cur = db.cursor()
        stmts = [
            "CREATE TABLE IF NOT EXISTS productos (id SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, costo_base REAL, activo INTEGER DEFAULT 1, visible INTEGER DEFAULT 1)",
            "CREATE TABLE IF NOT EXISTS insumos (id SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, costo REAL NOT NULL, descripcion TEXT)",
            "CREATE TABLE IF NOT EXISTS recetas (id SERIAL PRIMARY KEY, producto_id INTEGER NOT NULL, insumo_id INTEGER NOT NULL, tipo TEXT NOT NULL DEFAULT 'ambos', UNIQUE(producto_id,insumo_id))",
            "CREATE TABLE IF NOT EXISTS gastos_fijos (id SERIAL PRIMARY KEY, item TEXT NOT NULL UNIQUE, monto REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS pedidos (id SERIAL PRIMARY KEY, numero TEXT, fecha TEXT NOT NULL, cliente TEXT NOT NULL, telefono TEXT, provincia TEXT, transporte TEXT, tipo_pago TEXT DEFAULT 'transferencia', estado TEXT DEFAULT 'pendiente', observaciones TEXT, total REAL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS pedido_items (id SERIAL PRIMARY KEY, pedido_id INTEGER NOT NULL, producto TEXT NOT NULL, cantidad INTEGER NOT NULL, precio_unitario REAL NOT NULL, subtotal REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS precios_mayoristas (id SERIAL PRIMARY KEY, producto_id INTEGER NOT NULL, cantidad TEXT NOT NULL, precio REAL, markup REAL, UNIQUE(producto_id,cantidad))",
            "CREATE TABLE IF NOT EXISTS precios_minoristas (id SERIAL PRIMARY KEY, producto_id INTEGER NOT NULL UNIQUE, precio REAL)",
            "ALTER TABLE productos ADD COLUMN IF NOT EXISTS visible INTEGER DEFAULT 1",
            "ALTER TABLE precios_mayoristas ADD COLUMN IF NOT EXISTS markup REAL",
            "ALTER TABLE precios_minoristas ADD COLUMN IF NOT EXISTS markup REAL",
        ]
        for s in stmts:
            try: cur.execute(s)
            except: pass
        db.commit()
    else:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, costo_base REAL, activo INTEGER DEFAULT 1, visible INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE, costo REAL NOT NULL, descripcion TEXT);
        CREATE TABLE IF NOT EXISTS recetas (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL, insumo_id INTEGER NOT NULL, tipo TEXT NOT NULL DEFAULT 'ambos', UNIQUE(producto_id,insumo_id));
        CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT NOT NULL UNIQUE, monto REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT, fecha TEXT NOT NULL, cliente TEXT NOT NULL, telefono TEXT, provincia TEXT, transporte TEXT, tipo_pago TEXT DEFAULT 'transferencia', estado TEXT DEFAULT 'pendiente', observaciones TEXT, total REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS pedido_items (id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id INTEGER NOT NULL, producto TEXT NOT NULL, cantidad INTEGER NOT NULL, precio_unitario REAL NOT NULL, subtotal REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS precios_mayoristas (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL, cantidad TEXT NOT NULL, precio REAL, markup REAL, UNIQUE(producto_id,cantidad));
        CREATE TABLE IF NOT EXISTS precios_minoristas (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL UNIQUE, precio REAL);
        """)
        try: db.execute("ALTER TABLE productos ADD COLUMN visible INTEGER DEFAULT 1"); db.commit()
        except: pass
        try: db.execute("ALTER TABLE precios_mayoristas ADD COLUMN markup REAL"); db.commit()
        except: pass
        try: db.execute("ALTER TABLE precios_minoristas ADD COLUMN markup REAL"); db.commit()
        except: pass
    # Seed if empty
    cnt = q("SELECT COUNT(*) as n FROM productos")[0]["n"]
    if int(cnt) == 0:
        prods = [
            ("Taza de ceramica",1500),("Vasos",1460),("Chopp",3700),("Botella",2100),
            ("Hoppy m",4790),("Posavasos",620),("Stickers",180),("Tazones",6900),
            ("Termos 900 ml",6800),("Straw",10200),("Push",None),("XL",None),
            ("Latas",7870),("Glitter",10200),("Hoppy",3500),("Vaso sublimado",3200),
            ("Taza plastica",920),("Jarros termicos",2400),("Llavero",500),
            ("Taza 3D",10060),("Remeras",4500),("Taza magica 3d",2900),
            ("Taza con boca",1500),("Enlozados",3500),("Gorra",2500),
            ("Promos vaso grabado",1330),("Vaso Fluor",10600),("Corcho",5000),
            ("Sensor",7400),("Redondo 2 estampas",10000),("Cangiro",20200),
            ("Tarjeta",927),("XL 1.2",17000),("Torre",None),
        ]
        if USE_PG:
            cur = db.cursor()
            for n,c in prods: cur.execute("INSERT INTO productos (nombre,costo_base) VALUES (%s,%s) ON CONFLICT DO NOTHING",(n,c))
            db.commit()
        else:
            db.executemany("INSERT OR IGNORE INTO productos (nombre,costo_base) VALUES (?,?)", prods); db.commit()

    cnt = q("SELECT COUNT(*) as n FROM insumos")[0]["n"]
    if int(cnt) == 0:
        ins = [("Argollita",110,"por llavero"),("Hoja",140,"por hoja"),("Tinta",100,"por hoja"),
               ("Imanes",170,"por cada uno"),("Vinilo",500,"hoja A4"),("Grabado",200,"por cada 20 min"),
               ("Madera",800,"plancha A4"),("UV",180,""),("DTF",1750,"por remera / 6 por gorra"),
               ("Embalaje",100,""),("Caja",350,"por unidad"),("Bolsa",128,"por unidad"),("Bolsita remeras",500,"por unidad")]
        if USE_PG:
            cur = db.cursor()
            for n,c,d in ins: cur.execute("INSERT INTO insumos (nombre,costo,descripcion) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",(n,c,d))
            db.commit()
        else:
            db.executemany("INSERT OR IGNORE INTO insumos (nombre,costo,descripcion) VALUES (?,?,?)",ins); db.commit()

    cnt = q("SELECT COUNT(*) as n FROM gastos_fijos")[0]["n"]
    if int(cnt) == 0:
        gastos=[("Alquiler",720000),("Sueldos",3000000),("Luz",70000),("Expensas",90000),
                ("Agua",35000),("Internet",30000),("Alarma",39000),("ABL",12000),("Publicidad",350000)]
        if USE_PG:
            cur = db.cursor()
            for i,m in gastos: cur.execute("INSERT INTO gastos_fijos (item,monto) VALUES (%s,%s) ON CONFLICT DO NOTHING",(i,m))
            db.commit()
        else:
            db.executemany("INSERT OR IGNORE INTO gastos_fijos (item,monto) VALUES (?,?)",gastos); db.commit()

    defaults=[("pct_variables","0.44"),("desc_transferencia","0.05"),("desc_efectivo","0.10"),
              ("comision_qr_debito","0.0135"),("comision_qr_credito","0.0629"),("comision_3cuotas","0.086"),
              ("inflacion_q1_2025","0.08"),("inflacion_q2_2025","0.11"),("inflacion_q3_2025","0.09"),
              ("inflacion_q4_2025","0.07"),("inflacion_q1_2026","0.00"),("inflacion_q2_2026","0.00"),
              ("last_update",""),("logo_data",""),
              ("markup_12","0.60"),("markup_36","0.50"),("markup_72","0.30")]
    if USE_PG:
        cur = db.cursor()
        for k,v in defaults: cur.execute("INSERT INTO config (clave,valor) VALUES (%s,%s) ON CONFLICT DO NOTHING",(k,v))
        db.commit()
    else:
        for k,v in defaults: db.execute("INSERT OR IGNORE INTO config (clave,valor) VALUES (?,?)",(k,v))
        db.commit()

# ─── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index(): return send_from_directory(BASE_DIR, "index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({r["clave"]:r["valor"] for r in q("SELECT clave,valor FROM config")})

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.json or {}
    db = get_db(); p = ph()
    if USE_PG:
        cur = db.cursor()
        for k,v in data.items(): cur.execute("INSERT INTO config (clave,valor) VALUES (%s,%s) ON CONFLICT (clave) DO UPDATE SET valor=EXCLUDED.valor",(k,str(v)))
        db.commit()
    else:
        for k,v in data.items(): db.execute("INSERT OR REPLACE INTO config (clave,valor) VALUES (?,?)",(k,str(v)))
        db.commit()
    return jsonify({"ok":True})

@app.route("/api/productos", methods=["GET"])
def get_productos():
    return jsonify(q("SELECT * FROM productos WHERE activo=1 ORDER BY nombre"))

@app.route("/api/productos", methods=["POST"])
def add_producto():
    d = request.json
    try:
        if USE_PG:
            cur = get_db().cursor()
            cur.execute("INSERT INTO productos (nombre,costo_base) VALUES (%s,%s)",(d["nombre"],d.get("costo_base")))
            get_db().commit()
        else:
            get_db().execute("INSERT INTO productos (nombre,costo_base) VALUES (?,?)",(d["nombre"],d.get("costo_base"))); get_db().commit()
        return jsonify({"ok":True})
    except: return jsonify({"ok":False,"error":"Ya existe"}),400

@app.route("/api/productos/<int:pid>", methods=["PUT"])
def upd_producto(pid):
    d = request.json
    if USE_PG:
        cur = get_db().cursor(); cur.execute("UPDATE productos SET nombre=%s,costo_base=%s WHERE id=%s",(d["nombre"],d.get("costo_base"),pid)); get_db().commit()
    else:
        get_db().execute("UPDATE productos SET nombre=?,costo_base=? WHERE id=?",(d["nombre"],d.get("costo_base"),pid)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/productos/<int:pid>/visible", methods=["POST"])
def set_visible(pid):
    visible = 1 if request.json.get("visible") else 0
    if USE_PG:
        cur = get_db().cursor(); cur.execute("UPDATE productos SET visible=%s WHERE id=%s",(visible,pid)); get_db().commit()
    else:
        get_db().execute("UPDATE productos SET visible=? WHERE id=?",(visible,pid)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/productos/<int:pid>", methods=["DELETE"])
def del_producto(pid):
    if USE_PG:
        cur = get_db().cursor(); cur.execute("UPDATE productos SET activo=0 WHERE id=%s",(pid,)); get_db().commit()
    else:
        get_db().execute("UPDATE productos SET activo=0 WHERE id=?",(pid,)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/insumos", methods=["GET"])
def get_insumos(): return jsonify(q("SELECT * FROM insumos ORDER BY nombre"))

@app.route("/api/insumos", methods=["POST"])
def add_insumo():
    d = request.json
    try:
        if USE_PG:
            cur = get_db().cursor(); cur.execute("INSERT INTO insumos (nombre,costo,descripcion) VALUES (%s,%s,%s)",(d["nombre"],d["costo"],d.get("descripcion",""))); get_db().commit()
        else:
            get_db().execute("INSERT INTO insumos (nombre,costo,descripcion) VALUES (?,?,?)",(d["nombre"],d["costo"],d.get("descripcion",""))); get_db().commit()
        return jsonify({"ok":True})
    except: return jsonify({"ok":False,"error":"Ya existe"}),400

@app.route("/api/insumos/<int:iid>", methods=["PUT"])
def upd_insumo(iid):
    d = request.json
    if USE_PG:
        cur = get_db().cursor(); cur.execute("UPDATE insumos SET nombre=%s,costo=%s,descripcion=%s WHERE id=%s",(d["nombre"],d["costo"],d.get("descripcion",""),iid)); get_db().commit()
    else:
        get_db().execute("UPDATE insumos SET nombre=?,costo=?,descripcion=? WHERE id=?",(d["nombre"],d["costo"],d.get("descripcion",""),iid)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/insumos/<int:iid>", methods=["DELETE"])
def del_insumo(iid):
    if USE_PG:
        cur = get_db().cursor(); cur.execute("DELETE FROM insumos WHERE id=%s",(iid,)); get_db().commit()
    else:
        get_db().execute("DELETE FROM insumos WHERE id=?",(iid,)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/recetas/<int:pid>", methods=["GET"])
def get_receta(pid):
    sql = "SELECT r.*,i.nombre as insumo_nombre,i.costo as insumo_costo FROM recetas r JOIN insumos i ON r.insumo_id=i.id WHERE r.producto_id={0}".format("%s" if USE_PG else "?")
    return jsonify(q(sql,(pid,)))

@app.route("/api/recetas/<int:pid>", methods=["POST"])
def save_receta(pid):
    items = request.json or []
    db = get_db()
    if USE_PG:
        cur = db.cursor(); cur.execute("DELETE FROM recetas WHERE producto_id=%s",(pid,))
        for item in items: cur.execute("INSERT INTO recetas (producto_id,insumo_id,tipo) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",(pid,item["insumo_id"],item.get("tipo","ambos")))
        db.commit()
    else:
        db.execute("DELETE FROM recetas WHERE producto_id=?",(pid,))
        for item in items: db.execute("INSERT OR IGNORE INTO recetas (producto_id,insumo_id,tipo) VALUES (?,?,?)",(pid,item["insumo_id"],item.get("tipo","ambos")))
        db.commit()
    return jsonify({"ok":True})

@app.route("/api/precios_minoristas", methods=["GET"])
def get_precios_min():
    return jsonify({r["producto_id"]:{"precio":r["precio"],"markup":r["markup"]} for r in q("SELECT * FROM precios_minoristas")})

@app.route("/api/precios_minoristas/<int:pid>", methods=["POST"])
def set_precio_min(pid):
    precio = request.json.get("precio")
    markup = request.json.get("markup")
    if USE_PG:
        cur = get_db().cursor(); cur.execute("INSERT INTO precios_minoristas (producto_id,precio,markup) VALUES (%s,%s,%s) ON CONFLICT (producto_id) DO UPDATE SET precio=EXCLUDED.precio,markup=EXCLUDED.markup",(pid,precio,markup)); get_db().commit()
    else:
        get_db().execute("INSERT OR REPLACE INTO precios_minoristas (producto_id,precio,markup) VALUES (?,?,?)",(pid,precio,markup)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/precios_mayoristas", methods=["GET"])
def get_precios_mayor():
    result={}
    for r in q("SELECT * FROM precios_mayoristas"):
        pid=r["producto_id"]
        if pid not in result: result[pid]={}
        result[pid][r["cantidad"]]={"precio":r["precio"],"markup":r["markup"]}
    return jsonify(result)

@app.route("/api/precios_mayoristas/<int:pid>", methods=["POST"])
def set_precio_mayor(pid):
    data = request.json or {}
    db = get_db()
    for cantidad,vals in data.items():
        precio = vals.get("precio") if isinstance(vals,dict) else vals
        markup = vals.get("markup") if isinstance(vals,dict) else None
        if USE_PG:
            cur = db.cursor(); cur.execute("INSERT INTO precios_mayoristas (producto_id,cantidad,precio,markup) VALUES (%s,%s,%s,%s) ON CONFLICT (producto_id,cantidad) DO UPDATE SET precio=EXCLUDED.precio,markup=EXCLUDED.markup",(pid,cantidad,precio,markup))
        else:
            db.execute("INSERT OR REPLACE INTO precios_mayoristas (producto_id,cantidad,precio,markup) VALUES (?,?,?,?)",(pid,cantidad,precio,markup))
    db.commit()
    return jsonify({"ok":True})

@app.route("/api/gastos", methods=["GET"])
def get_gastos(): return jsonify(q("SELECT * FROM gastos_fijos ORDER BY item"))

@app.route("/api/gastos", methods=["POST"])
def add_gasto():
    d = request.json
    try:
        if USE_PG:
            cur = get_db().cursor(); cur.execute("INSERT INTO gastos_fijos (item,monto) VALUES (%s,%s)",(d["item"],d["monto"])); get_db().commit()
        else:
            get_db().execute("INSERT INTO gastos_fijos (item,monto) VALUES (?,?)",(d["item"],d["monto"])); get_db().commit()
        return jsonify({"ok":True})
    except: return jsonify({"ok":False,"error":"Ya existe"}),400

@app.route("/api/gastos/<int:gid>", methods=["PUT"])
def upd_gasto(gid):
    d = request.json
    if USE_PG:
        cur = get_db().cursor(); cur.execute("UPDATE gastos_fijos SET item=%s,monto=%s WHERE id=%s",(d["item"],d["monto"],gid)); get_db().commit()
    else:
        get_db().execute("UPDATE gastos_fijos SET item=?,monto=? WHERE id=?",(d["item"],d["monto"],gid)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/gastos/<int:gid>", methods=["DELETE"])
def del_gasto(gid):
    if USE_PG:
        cur = get_db().cursor(); cur.execute("DELETE FROM gastos_fijos WHERE id=%s",(gid,)); get_db().commit()
    else:
        get_db().execute("DELETE FROM gastos_fijos WHERE id=?",(gid,)); get_db().commit()
    return jsonify({"ok":True})

@app.route("/api/pedidos", methods=["GET"])
def get_pedidos():
    rows = q("SELECT * FROM pedidos ORDER BY fecha DESC, id DESC")
    result=[]
    for r in rows:
        p=dict(r)
        sql="SELECT * FROM pedido_items WHERE pedido_id={0}".format("%s" if USE_PG else "?")
        p["items"]=q(sql,(p["id"],))
        result.append(p)
    return jsonify(result)

@app.route("/api/pedidos", methods=["POST"])
def add_pedido():
    d=request.json; items=d.pop("items",[]); total=sum(i["subtotal"] for i in items)
    db=get_db()
    if USE_PG:
        cur=db.cursor()
        cur.execute("INSERT INTO pedidos (numero,fecha,cliente,telefono,provincia,transporte,tipo_pago,estado,observaciones,total) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (d.get("numero",""),d["fecha"],d["cliente"],d.get("telefono",""),d.get("provincia",""),d.get("transporte",""),d.get("tipo_pago","transferencia"),d.get("estado","pendiente"),d.get("observaciones",""),total))
        pid=cur.fetchone()[0]
        for i in items: cur.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (%s,%s,%s,%s,%s)",(pid,i["producto"],i["cantidad"],i["precio_unitario"],i["subtotal"]))
        db.commit()
    else:
        cur=db.execute("INSERT INTO pedidos (numero,fecha,cliente,telefono,provincia,transporte,tipo_pago,estado,observaciones,total) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (d.get("numero",""),d["fecha"],d["cliente"],d.get("telefono",""),d.get("provincia",""),d.get("transporte",""),d.get("tipo_pago","transferencia"),d.get("estado","pendiente"),d.get("observaciones",""),total))
        pid=cur.lastrowid
        for i in items: db.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",(pid,i["producto"],i["cantidad"],i["precio_unitario"],i["subtotal"]))
        db.commit()
    return jsonify({"ok":True,"id":pid})

@app.route("/api/pedidos/<int:pid>", methods=["PUT"])
def upd_pedido(pid):
    d=request.json; items=d.pop("items",[]); total=sum(i["subtotal"] for i in items)
    db=get_db()
    if USE_PG:
        cur=db.cursor()
        cur.execute("UPDATE pedidos SET numero=%s,fecha=%s,cliente=%s,telefono=%s,provincia=%s,transporte=%s,tipo_pago=%s,estado=%s,observaciones=%s,total=%s WHERE id=%s",
            (d.get("numero",""),d["fecha"],d["cliente"],d.get("telefono",""),d.get("provincia",""),d.get("transporte",""),d.get("tipo_pago","transferencia"),d.get("estado","pendiente"),d.get("observaciones",""),total,pid))
        cur.execute("DELETE FROM pedido_items WHERE pedido_id=%s",(pid,))
        for i in items: cur.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (%s,%s,%s,%s,%s)",(pid,i["producto"],i["cantidad"],i["precio_unitario"],i["subtotal"]))
        db.commit()
    else:
        db.execute("UPDATE pedidos SET numero=?,fecha=?,cliente=?,telefono=?,provincia=?,transporte=?,tipo_pago=?,estado=?,observaciones=?,total=? WHERE id=?",
            (d.get("numero",""),d["fecha"],d["cliente"],d.get("telefono",""),d.get("provincia",""),d.get("transporte",""),d.get("tipo_pago","transferencia"),d.get("estado","pendiente"),d.get("observaciones",""),total,pid))
        db.execute("DELETE FROM pedido_items WHERE pedido_id=?",(pid,))
        for i in items: db.execute("INSERT INTO pedido_items (pedido_id,producto,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",(pid,i["producto"],i["cantidad"],i["precio_unitario"],i["subtotal"]))
        db.commit()
    return jsonify({"ok":True})

@app.route("/api/pedidos/<int:pid>", methods=["DELETE"])
def del_pedido(pid):
    db=get_db()
    if USE_PG:
        cur=db.cursor(); cur.execute("DELETE FROM pedido_items WHERE pedido_id=%s",(pid,)); cur.execute("DELETE FROM pedidos WHERE id=%s",(pid,)); db.commit()
    else:
        db.execute("DELETE FROM pedido_items WHERE pedido_id=?",(pid,)); db.execute("DELETE FROM pedidos WHERE id=?",(pid,)); db.commit()
    return jsonify({"ok":True})

@app.route("/api/clientes", methods=["GET"])
def get_clientes():
    return jsonify(q("""SELECT cliente,telefono,provincia,COUNT(DISTINCT id) as num_pedidos,MAX(fecha) as ultimo_pedido,
        SUM(CASE WHEN LEFT(fecha,4)='2025' THEN total ELSE 0 END) as total_2025,
        SUM(CASE WHEN LEFT(fecha,4)='2026' THEN total ELSE 0 END) as total_2026,
        SUM(total) as total_acumulado FROM pedidos GROUP BY cliente,telefono,provincia ORDER BY total_acumulado DESC"""))

@app.route("/api/clientes/<path:nombre>/pedidos", methods=["GET"])
def get_cliente_pedidos(nombre):
    sql="SELECT * FROM pedidos WHERE cliente={0} ORDER BY fecha DESC".format("%s" if USE_PG else "?")
    rows=q(sql,(nombre,)); result=[]
    for r in rows:
        p=dict(r)
        sql2="SELECT * FROM pedido_items WHERE pedido_id={0}".format("%s" if USE_PG else "?")
        p["items"]=q(sql2,(p["id"],)); result.append(p)
    return jsonify(result)

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)

with app.app_context():
    init_db()

@app.route("/inicializar-laguarida-2026")
def seed_now():
    try:
        init_db()
        return "✅ Datos cargados correctamente!"
    except Exception as e:
        return f"❌ Error: {str(e)}", 500
