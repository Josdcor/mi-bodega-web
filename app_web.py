import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime
import urllib.parse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Bodega Pro - Gestión Total", layout="wide", page_icon="🚀")

def conectar_db():
    conn = sqlite3.connect("bodega.db", check_same_thread=False)
    # Crear tablas si no existen
    conn.execute('''CREATE TABLE IF NOT EXISTS productos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, precio REAL, stock_actual INTEGER, stock_minimo INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, tipo TEXT, cantidad INTEGER, fecha TEXT, responsable TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS gastos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, descripcion TEXT, monto REAL, fecha TEXT)''')
    return conn

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 43.50 # Ajusta según la tasa actual en Venezuela

tasa = obtener_tasa_bcv()
conn = conectar_db()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🛡️ Acceso Seguro")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        c = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            cursor = conn.cursor()
            cursor.execute("SELECT rol FROM usuarios WHERE nombre=? AND clave=?", (u, c))
            resultado = cursor.fetchone()
            if resultado:
                st.session_state.update({'autenticado': True, 'usuario_nombre': u, 'rol': resultado[0]})
                st.rerun()
            else: st.error("Credenciales incorrectas")

if not st.session_state['autenticado']:
    login()
else:
    # --- SIDEBAR ---
    st.sidebar.title("📦 Mi Bodega Pro")
    st.sidebar.info(f"Tasa BCV: **{tasa:.2f} Bs.**")
    menu = st.sidebar.radio("Ir a:", ["Dashboard", "Inventario", "Gastos 💸", "Historial"])

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Resumen del Negocio")
        
        df_cap = pd.read_sql_query("SELECT SUM(precio * stock_actual) as cap FROM productos", conn)
        total_cap = df_cap['cap'].iloc[0] or 0
        df_gas = pd.read_sql_query("SELECT SUM(monto) as total FROM gastos", conn)
        total_gas = df_gas['total'].iloc[0] or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Capital Mercancía", f"${total_cap:,.2f}")
        c2.metric("Gastos Totales", f"${total_gas:,.2f}", delta=f"-{total_gas}", delta_color="inverse")
        c3.metric("Neto Disponible", f"${(total_cap - total_gas):,.2f}")

        # Botón WhatsApp
        st.divider()
        reporte_txt = f"*REPORTE BODEGA*\nCapital: ${total_cap}\nGastos: ${total_gas}\nNeto: ${total_cap-total_gas}\nTasa: {tasa} Bs."
        url_wa = f"https://wa.me/?text={urllib.parse.quote(reporte_txt)}"
        st.markdown(f'<a href="{url_wa}" target="_blank"><button style="background:#25D366;color:white;border:none;padding:10px;border-radius:5px;">Enviar Reporte WhatsApp 🟢</button></a>', unsafe_allow_html=True)

    # --- INVENTARIO ---
    elif menu == "Inventario":
        st.title("📦 Inventario")
        df_inv = pd.read_sql_query("SELECT * FROM productos", conn)
        def color_stock(row):
            return ['background-color: #4a1a1a' if row.stock_actual <= row.stock_minimo else '' for _ in row.index]
        st.dataframe(df_inv.style.apply(color_stock, axis=1), use_container_width=True)
        
        with st.expander("Registrar Salida"):
            id_p = st.number_input("ID Producto", min_value=1)
            cant = st.number_input("Cantidad", min_value=1)
            if st.button("Confirmar"):
                conn.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?", (cant, id_p))
                conn.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Salida', ?, ?, ?)",
                            (id_p, cant, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state['usuario_nombre']))
                conn.commit()
                st.rerun()

    # --- GASTOS ---
    elif menu == "Gastos 💸":
        st.title("💸 Registro de Gastos")
        with st.form("g"):
            d = st.text_input("Descripción")
            m = st.number_input("Monto $", min_value=0.0)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO gastos (descripcion, monto, fecha) VALUES (?, ?, ?)", (d, m, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.rerun()
        st.table(pd.read_sql_query("SELECT * FROM gastos ORDER BY id DESC LIMIT 10", conn))

    # --- HISTORIAL ---
    elif menu == "Historial":
        st.title("📜 Historial")
        df_h = pd.read_sql_query('''SELECT m.id, m.fecha, p.nombre, m.tipo, m.cantidad, m.responsable 
                                    FROM movimientos m JOIN productos p ON m.producto_id = p.id ORDER BY m.id DESC''', conn)
        st.dataframe(df_h, use_container_width=True)
        
        if st.session_state['rol'] == "SuperAdmin":
            if st.button("🚨 VACIAR HISTORIAL"):
                conn.execute("DELETE FROM movimientos")
                conn.commit()
                st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['autenticado'] = False
        st.rerun()
