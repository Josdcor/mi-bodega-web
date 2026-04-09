import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime
import urllib.parse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Bodega Pro - Nube", layout="wide", page_icon="🚀")

def conectar_db():
    return sqlite3.connect("bodega.db", check_same_thread=False)

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 39.50 # Ajusta según la realidad actual

tasa = obtener_tasa_bcv()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🛡️ Acceso al Sistema")
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
            else: st.error("Clave incorrecta")

if not st.session_state['autenticado']:
    login()
else:
    # --- SIDEBAR ---
    st.sidebar.title("📦 Menú Principal")
    st.sidebar.info(f"Tasa BCV: **{tasa:.2f} Bs.**")
    
    opciones = ["Dashboard", "Inventario", "Gastos 💸", "Historial"]
    if st.session_state['rol'] == "SuperAdmin": opciones.append("Usuarios ⚙️")
    menu = st.sidebar.radio("Ir a:", opciones)

    conn = conectar_db()

    # --- FUNCIÓN WHATSAPP ---
    def generar_reporte_whatsapp():
        df_cap = pd.read_sql_query("SELECT SUM(precio * stock_actual) as cap FROM productos", conn)
        total_cap = df_cap['cap'].iloc[0] or 0
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        
        texto = f"*RESUMEN DE BODEGA ({fecha_hoy})*\n\n"
        texto += f"🔹 *Capital en Inventario:* ${total_cap:,.2f}\n"
        texto += f"🔹 *Tasa BCV:* {tasa:.2f} Bs.\n"
        texto += f"🔹 *Equivalente:* {(total_cap * tasa):,.2f} Bs.\n\n"
        texto += "✅ Reporte generado desde el Sistema Web."
        
        # Codificar para URL
        texto_url = urllib.parse.quote(texto)
        return f"https://wa.me/?text={texto_url}"

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Resumen del Negocio")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            df_total = pd.read_sql_query("SELECT SUM(precio * stock_actual) as cap FROM productos", conn)
            cap = df_total['cap'].iloc[0] or 0
            st.metric("Capital Invertido", f"${cap:,.2f}", f"{cap*tasa:,.2f} Bs.")
            
        with col2:
            st.write("📲 **Compartir Reporte**")
            link_wa = generar_reporte_whatsapp()
            st.markdown(f'''<a href="{link_wa}" target="_blank" style="text-decoration:none;">
                            <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer;">
                            Enviar a WhatsApp 🟢</button></a>''', unsafe_allow_html=True)

        st.divider()
        st.subheader("📦 Niveles de Mercancía")
        df_g =
