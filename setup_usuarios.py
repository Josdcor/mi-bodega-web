import sqlite3

def crear_tabla_usuarios():
    conn = sqlite3.connect("bodega.db")
    cursor = conn.cursor()
    
    # Borramos la tabla si existe para asegurar que se cree limpia (solo para esta prueba)
    cursor.execute("DROP TABLE IF EXISTS usuarios")
    
    cursor.execute('''CREATE TABLE usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT UNIQUE,
                        clave TEXT,
                        rol TEXT)''')
    
    # Insertar el usuario Master
    cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?,?,?)", 
                   ("Master", "admin99", "SuperAdmin"))
    
    conn.commit()
    conn.close()
    print("✅ Base de datos reseteada. Usuario: Master | Clave: admin99")

if __name__ == "__main__":
    crear_tabla_usuarios()