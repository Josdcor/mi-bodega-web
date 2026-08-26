import sqlite3
import os

def conectar():
    return sqlite3.connect("bodega.db")

def inicializar_bd():
    # Si el archivo existe pero está dando error, podrías borrarlo manualmente 
    # o dejar que el script intente conectar.
    conexion = conectar()
    cursor = conexion.cursor()

    try:
        # Tabla de Productos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT,
                precio REAL,
                stock_actual INTEGER,
                stock_minimo INTEGER
            )
        ''')

        # Tabla de Movimientos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                tipo TEXT,
                cantidad INTEGER,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responsable TEXT,
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')

        # Insertar datos de prueba iniciales
        cursor.execute("SELECT COUNT(*) FROM productos")
        if cursor.fetchone()[0] == 0:
            productos = [
                ('Aceite vegetal 1L', 'Abarrotes', 2.50, 3, 10),
                ('Azúcar 1kg', 'Abarrotes', 1.20, 15, 5),
                ('Leche entera 1L', 'Lácteos', 1.80, 2, 20)
            ]
            cursor.executemany("INSERT INTO productos (nombre, categoria, precio, stock_actual, stock_minimo) VALUES (?, ?, ?, ?, ?)", productos)
        
        conexion.commit()
        print("✅ Base de datos creada y verificada con éxito.")
    except sqlite3.Error as e:
        print(f"❌ Error al crear la base de datos: {e}")
    finally:
        conexion.close()

if __name__ == "__main__":
    # Borrar si existe para limpiar el error de 'file is not a database'
    if os.path.exists("bodega.db"):
        try:
            os.remove("bodega.db")
        except:
            pass 
    inicializar_bd()