import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime
import urllib.parse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Bodega Pro - Gestión Real", layout="wide", page_icon="🚀")

def conectar_db():
    conn = sqlite3.connect("bodega.db", check_same_thread=False)
    # CREAR TABLA DE GASTOS SI NO EXISTE
    conn.execute('''CREATE TABLE IF NOT EXISTS gastos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, descripcion TEXT, monto REAL, fecha TEXT)''')
    return conn

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 40.00 

tasa = obtener_tasa_bcv()
conn = conectar_db()

# --- (Saltamos la parte del Login que ya tienes igual) ---

if 'autenticado' in st.session_state and st.session_state['autenticado']:
    st.sidebar.title("📦 Menú")
    menu = st.sidebar.radio("Navegación:", ["Dashboard", "Inventario", "Gastos 💸", "Historial"])
    
    # --- 📊 DASHBOARD (DONDE SE UBICAN LOS GASTOS) ---
    if menu == "Dashboard":
        st.title("📊 Balance General")
        
        # Calcular Capital
        df_cap = pd.read_sql_query("SELECT SUM(precio * stock_actual) as cap FROM productos", conn)
        total_cap = df_cap['cap'].iloc[0] or 0
        
        # Calcular Gastos Totales
        df_gastos_sum = pd.read_sql_query("SELECT SUM(monto) as total FROM gastos", conn)
        total_gastos = df_gastos_sum['total'].iloc[0] or 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Mercancía en $", f"${total_cap:,.2f}")
        col2.metric("Gastos Acumulados", f"${total_gastos:,.2f}", delta=f"-{total_gastos}", delta_color="inverse")
        col3.metric("Disponible Neto", f"${(total_cap - total_gastos):,.2f}")

        st.divider()
        st.subheader("📝 Detalle de Gastos Recientes")
        df_lista_gastos = pd.read_sql_query("SELECT fecha, descripcion, monto FROM gastos ORDER BY id DESC LIMIT 5", conn)
        st.table(df_lista_gastos)

    # --- 💸 SECCIÓN DE GASTOS (DONDE LOS REGISTRAS) ---
    elif menu == "Gastos 💸":
        st.title("💸 Registro de Gastos Operativos")
        with st.form("nuevo_gasto"):
            desc = st.text_input("Descripción (Ej: Vacunas, Gasolina moto)")
            monto = st.number_input("Monto en $", min_value=0.0, step=0.5)
            if st.form_submit_button("Guardar Gasto"):
                fecha_g = datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT INTO gastos (descripcion, monto, fecha) VALUES (?, ?, ?)", (desc, monto, fecha_g))
                conn.commit()
                st.success("Gasto guardado correctamente")
                st.rerun()
        
        st.divider()
        if st.session_state['rol'] == "SuperAdmin":
            if st.button("🚨 Borrar todos los gastos"):
                conn.execute("DELETE FROM gastos")
                conn.commit()
                st.rerun()

    # --- (El resto de secciones: Inventario e Historial se mantienen igual) ---
