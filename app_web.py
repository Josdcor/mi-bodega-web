import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Bodega Pro - Gestión Total", layout="wide", page_icon="🛡️")

def conectar_db():
    return sqlite3.connect("bodega.db", check_same_thread=False)

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 37.50 # Tasa de respaldo si falla el API

tasa = obtener_tasa_bcv()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🛡️ Acceso Seguro - Bodega")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        c = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT rol FROM usuarios WHERE nombre=? AND clave=?", (u, c))
            resultado = cursor.fetchone()
            conn.close()
            if resultado:
                st.session_state.update({'autenticado': True, 'usuario_nombre': u, 'rol': resultado[0]})
                st.rerun()
            else: st.error("Usuario o clave incorrecta")

if not st.session_state['autenticado']:
    login()
else:
    # Sidebar
    st.sidebar.title("📦 Mi Bodega Pro")
    st.sidebar.write(f"Sesión: **{st.session_state['usuario_nombre']}**")
    st.sidebar.info(f"Tasa BCV: **{tasa:.2f} Bs.**")
    
    opciones = ["Dashboard", "Inventario", "Gastos 💸", "Historial"]
    if st.session_state['rol'] == "SuperAdmin": opciones.append("Usuarios ⚙️")
    menu = st.sidebar.radio("Navegación:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['autenticado'] = False
        st.rerun()

    conn = conectar_db()

    # --- HISTORIAL (CON BORRADO MAESTRO) ---
    if menu == "Historial":
        st.title("📜 Historial de Movimientos")
        
        # Filtros rápidos
        df_h = pd.read_sql_query('''SELECT m.id, m.fecha, p.nombre as producto, m.tipo, m.cantidad, m.responsable 
                                    FROM movimientos m JOIN productos p ON m.producto_id = p.id 
                                    ORDER BY m.fecha DESC''', conn)
        
        st.dataframe(df_h, use_container_width=True)

        # SECCIÓN DE BORRADO - SOLO PARA MASTER
        if st.session_state['rol'] == "SuperAdmin":
            st.divider()
            st.subheader("🗑️ Zona de Limpieza (Solo Master)")
            col1, col2 = st.columns(2)
            
            with col1:
                id_borrar = st.number_input("ID de movimiento a borrar", min_value=1, step=1)
                if st.button("Eliminar Registro Específico"):
                    conn.execute("DELETE FROM movimientos WHERE id=?", (id_borrar,))
                    conn.commit()
                    st.success(f"Movimiento {id_borrar} eliminado.")
                    st.rerun()
            
            with col2:
                st.write("Cuidado: Esta acción es irreversible")
                if st.button("🚨 VACIAR TODO EL HISTORIAL"):
                    conn.execute("DELETE FROM movimientos")
                    conn.commit()
                    st.warning("Historial vaciado por completo.")
                    st.rerun()

    # --- GASTOS (NUEVA FUNCIÓN) ---
    elif menu == "Gastos 💸":
        st.title("💸 Registro de Gastos Operativos")
        st.info("Aquí puedes anotar gastos de gasolina, comida para animales, etc.")
        
        with st.form("form_gastos"):
            desc = st.text_input("Descripción del gasto")
            monto = st.number_input("Monto en Dólares ($)", min_value=0.0)
            if st.form_submit_button("Registrar Gasto"):
                # Aquí podrías crear una tabla de gastos si quieres guardarlos permanentemente
                st.success(f"Gasto de ${monto} registrado (Visualización en Dashboard próximamente)")

    # --- RESTO DEL CÓDIGO (Dashboard, Inventario, Usuarios...) ---
    # (Mantén aquí el código de Dashboard e Inventario que ya tenías funcionando)
    elif menu == "Dashboard":
        st.title("📊 Resumen General")
        df_total = pd.read_sql_query("SELECT SUM(precio * stock_actual) as cap FROM productos", conn)
        cap = df_total['cap'].iloc[0] or 0
        st.metric("Capital en Mercancía", f"${cap:,.2f}")
        st.bar_chart(pd.read_sql_query("SELECT nombre, stock_actual FROM productos", conn), x="nombre", y="stock_actual")

    elif menu == "Inventario":
        st.title("📦 Gestión de Productos")
        # Tu código de inventario con las filas rojas aquí...
        df_inv = pd.read_sql_query("SELECT * FROM productos", conn)
        st.dataframe(df_inv, use_container_width=True)

    elif menu == "Usuarios ⚙️":
        st.title("Control de Personal")
        # Tu código de gestión de usuarios aquí...
