import sqlite3

DB_NAME = "bodega.db"

def conectar():
    """Establece conexión con la base de datos SQLite."""
    return sqlite3.connect(DB_NAME)

def inicializar_bd():
    """Crea la estructura unificada de tablas e inserta datos iniciales sin destruir registros preexistentes."""
    conn = conectar()
    cursor = conn.cursor()

    try:
        # 1. TABLA USUARIOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                clave TEXT NOT NULL,
                rol TEXT NOT NULL
            )
        ''')

        # 2. TABLA PRODUCTOS (Esquema Completo Unificado)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT DEFAULT 'General',
                precio_usd REAL NOT NULL DEFAULT 0.0,
                costo_usd REAL DEFAULT 0.0,
                stock_actual REAL NOT NULL DEFAULT 0.0,
                stock_minimo REAL DEFAULT 5.0
            )
        ''')

        # Migración suave de compatibilidad por si existían esquemas viejos
        cursor.execute("PRAGMA table_info(productos)")
        cols = [col[1] for col in cursor.fetchall()]
        if "precio" in cols and "precio_usd" not in cols:
            cursor.execute("ALTER TABLE productos ADD COLUMN precio_usd REAL DEFAULT 0.0")
            cursor.execute("UPDATE productos SET precio_usd = precio WHERE precio_usd = 0.0")

        # 3. TABLA CLIENTES
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT
            )
        ''')

        # 4. TABLA VENTAS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                num_factura TEXT NOT NULL,
                producto_id INTEGER,
                cliente_id INTEGER,
                cantidad REAL NOT NULL,
                total_usd REAL NOT NULL,
                total_bs REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL,
                estado TEXT DEFAULT 'Activa',
                FOREIGN KEY (producto_id) REFERENCES productos (id),
                FOREIGN KEY (cliente_id) REFERENCES clientes (id)
            )
        ''')

        # 5. TABLA MOVIMIENTOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                tipo TEXT NOT NULL,
                cantidad REAL NOT NULL,
                fecha TEXT NOT NULL,
                responsable TEXT,
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')

        # 6. TABLA GASTOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT NOT NULL,
                monto REAL NOT NULL,
                moneda TEXT NOT NULL DEFAULT 'USD',
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL
            )
        ''')

        # 7. TABLA ABONOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS abonos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                monto_usd REAL NOT NULL,
                monto_bs REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id)
            )
        ''')

        # --- DATOS INICIALES SEGUROS ---

        # Cargar usuarios base si la tabla está vacía
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", ("Master", "admin99", "SuperAdmin"))
            cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", ("Admin", "1234", "SuperAdmin"))
            cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", ("Vendedor", "0000", "Vendedor"))

        # Cargar inventario inicial si la tabla está vacía
        cursor.execute("SELECT COUNT(*) FROM productos")
        if cursor.fetchone()[0] == 0:
            productos_inventario = [
                ("P001", "Harina PAN 1kg", "Víveres", 1.20, 0.95, 80, 10),
                ("P002", "Arroz Blanco 1kg", "Víveres", 1.10, 0.85, 60, 10),
                ("P003", "Aceite Vegetal 1L", "Víveres", 2.50, 2.00, 35, 5),
                ("P004", "Azúcar Refinada 1kg", "Víveres", 1.30, 1.00, 50, 10),
                ("P005", "Pasta 500g", "Víveres", 1.15, 0.80, 45, 8),
                ("P006", "Refresco 2L", "Bebidas", 2.20, 1.70, 24, 6),
                ("P007", "Queso Blanco Duro (kg)", "Charcutería", 5.50, 4.20, 15, 3),
                ("P008", "Detergente 1kg", "Limpieza", 3.00, 2.20, 20, 5)
            ]
            cursor.executemany('''
                INSERT INTO productos (codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', productos_inventario)

        conn.commit()
        print("✅ Base de datos inicializada y verificada con éxito.")

    except sqlite3.Error as e:
        print(f"❌ Error al inicializar la base de datos: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inicializar_bd()