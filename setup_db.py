import sqlite3

def inicializar_sistema():
    conn = sqlite3.connect("bodega.db")
    cursor = conn.cursor()

    # 1. TABLA USUARIOS
    cursor.execute("DROP TABLE IF EXISTS usuarios")
    cursor.execute('''
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')

    # 2. TABLA PRODUCTOS
    cursor.execute("DROP TABLE IF EXISTS productos")
    cursor.execute('''
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL DEFAULT 0.0,
            stock_actual INTEGER NOT NULL,
            stock_minimo INTEGER DEFAULT 5,
            categoria TEXT NOT NULL
        )
    ''')

    # 3. TABLA MOVIMIENTOS
    cursor.execute("DROP TABLE IF EXISTS movimientos")
    cursor.execute('''
        CREATE TABLE movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            responsable TEXT
        )
    ''')

    # 4. TABLA GASTOS
    cursor.execute("DROP TABLE IF EXISTS gastos")
    cursor.execute('''
        CREATE TABLE gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            monto REAL NOT NULL,
            fecha TEXT NOT NULL
        )
    ''')

    # DATOS INICIALES
    cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", 
                   ("Master", "admin99", "SuperAdmin"))

    productos_inventario = [
        ("P001", "Harina PAN 1kg", 1.20, 0.95, 80, 10, "Víveres"),
        ("P002", "Arroz Blanco 1kg", 1.10, 0.85, 60, 10, "Víveres"),
        ("P003", "Aceite Vegetal 1L", 2.50, 2.00, 35, 5, "Víveres"),
        ("P004", "Azúcar Refinada 1kg", 1.30, 1.00, 50, 10, "Víveres"),
        ("P005", "Pasta 500g", 1.15, 0.80, 45, 8, "Víveres"),
        ("P006", "Refresco 2L", 2.20, 1.70, 24, 6, "Bebidas"),
        ("P007", "Agua Mineral 1.5L", 0.80, 0.40, 40, 10, "Bebidas"),
        ("P008", "Jugo de Naranja 1L", 1.80, 1.30, 18, 5, "Bebidas"),
        ("P009", "Queso Blanco Duro (kg)", 5.50, 4.20, 15, 3, "Charcutería"),
        ("P010", "Jamón de Pierna (kg)", 7.00, 5.50, 12, 3, "Charcutería"),
        ("P011", "Detergente 1kg", 3.00, 2.20, 20, 5, "Limpieza"),
        ("P012", "Jabón de Baño", 0.90, 0.60, 50, 10, "Higiene"),
        ("P013", "Chocolate 100g", 1.50, 0.90, 30, 5, "Golosinas"),
    ]

    cursor.executemany('''
        INSERT INTO productos (codigo, nombre, precio, costo, stock_actual, stock_minimo, categoria)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', productos_inventario)

    conn.commit()
    conn.close()
    print("✅ Base de datos recreada con la columna 'responsable'.")

if __name__ == "__main__":
    inicializar_sistema()