import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Mi Bodega Pro - Sistema Blindado", layout="wide", page_icon="🛡️")

def conectar_db():
    return sqlite3.connect("bodega.db", check_same_thread=False)

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 36.50

tasa = obtener_tasa_bcv()

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🛡️ Acceso de Seguridad")
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
            else: st.error("Credenciales incorrectas")

if not st.session_state['autenticado']:
    login()
else:
    # Sidebar
    st.sidebar.title("📦 Mi Bodega Pro")
    st.sidebar.write(f"Usuario: **{st.session_state['usuario_nombre']}**")
    st.sidebar.info(f"Tasa BCV: **{tasa:.2f} Bs.**")
    
    opciones = ["Dashboard", "Inventario", "Historial"]
    if st.session_state['rol'] == "SuperAdmin": opciones.append("Usuarios ⚙️")
    menu = st.sidebar.radio("Ir a:", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['autenticado'] = False
        st.rerun()

    conn = conectar_db()

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Resumen del Negocio")
        
        # Cálculos de Capital y Ganancia
        df_total = pd.read_sql_query("SELECT precio, stock_actual, (precio * stock_actual) as costo_total FROM productos", conn)
        capital_invertido = df_total['costo_total'].sum()
        
        # Alertas de Stock Bajo
        df_alerta = pd.read_sql_query("SELECT COUNT(*) as cuenta FROM productos WHERE stock_actual <= stock_minimo", conn)
        alertas = df_alerta['cuenta'].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Capital Invertido", f"${capital_invertido:,.2f}")
        col2.metric("En Bolívares", f"{capital_invertido * tasa:,.2f} Bs.")
        col3.metric("Productos Críticos", f"{alertas}", delta="- Reabastecer" if alertas > 0 else "OK", delta_color="inverse")

        st.subheader("📊 Niveles de Stock Actual")
        df_g = pd.read_sql_query("SELECT nombre, stock_actual, stock_minimo FROM productos", conn)
        if not df_g.empty:
            st.bar_chart(df_g, x="nombre", y="stock_actual", color="#6366f1")

    # --- INVENTARIO CON ALERTAS ---
    elif menu == "Inventario":
        st.title("📦 Inventario y Ventas")
        
        col_bus, col_filt = st.columns([3, 1])
        busqueda = col_bus.text_input("🔍 Buscar por nombre...")
        solo_critico = col_filt.checkbox("Ver solo Stock Bajo ⚠️")

        # Query de datos
        df_inv = pd.read_sql_query("SELECT id, nombre, precio as 'Costo $', stock_actual as 'Stock', stock_minimo FROM productos", conn)
        df_inv['Precio Bs.'] = (df_inv['Costo $'] * tasa).round(2)

        # Aplicar filtros
        if busqueda: df_inv = df_inv[df_inv['nombre'].str.contains(busqueda, case=False)]
        if solo_critico: df_inv = df_inv[df_inv['Stock'] <= df_inv['stock_minimo']]

        # Función para pintar de rojo las filas críticas
        def highlight_stock(row):
            return ['background-color: #4a1a1a' if row.Stock <= row.stock_minimo else '' for _ in row.index]

        st.dataframe(df_inv.style.apply(highlight_stock, axis=1), use_container_width=True)

        # Acciones
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🛒 Registrar Venta / Salida")
            id_v = st.number_input("ID del Producto", min_value=1, step=1)
            cant_v = st.number_input("Cantidad", min_value=1, value=1)
            if st.button("Confirmar Salida"):
                # Verificar stock antes de restar
                cursor = conn.cursor()
                cursor.execute("SELECT stock_actual FROM productos WHERE id=?", (id_v,))
                actual = cursor.fetchone()
                if actual and actual[0] >= cant_v:
                    conn.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?", (cant_v, id_v))
                    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Salida', ?, ?, ?)", 
                                (id_v, cant_v, fecha, st.session_state['usuario_nombre']))
                    conn.commit()
                    st.success("Venta registrada con éxito")
                    st.rerun()
                else: st.error("No hay suficiente stock o ID no existe")

        if st.session_state['rol'] in ["Admin", "SuperAdmin"]:
            with c2:
                st.subheader("➕ Agregar / Reponer Stock")
                with st.expander("Abrir Formulario"):
                    n = st.text_input("Nombre")
                    p = st.number_input("Costo Unitario ($)", min_value=0.0)
                    s = st.number_input("Stock", min_value=1)
                    m = st.number_input("Mínimo Alerta", min_value=1)
                    if st.button("Guardar en Base de Datos"):
                        conn.execute("INSERT INTO productos (nombre, categoria, precio, stock_actual, stock_minimo) VALUES (?,?,?,?,?)", (n, 'Gral', p, s, m))
                        conn.commit()
                        st.success("Guardado")
                        st.rerun()

    # --- HISTORIAL ---
    elif menu == "Historial":
        st.title("📜 Movimientos Recientes")
        df_h = pd.read_sql_query('''SELECT m.fecha, p.nombre, m.tipo, m.cantidad, m.responsable 
                                    FROM movimientos m JOIN productos p ON m.producto_id = p.id 
                                    ORDER BY m.fecha DESC LIMIT 50''', conn)
        st.table(df_h)

    # --- USUARIOS ---
    elif menu == "Usuarios ⚙️":
        st.title("Configuración de Personal")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("Registrar Socio o Vendedor")
            nu = st.text_input("Nombre de Usuario")
            nc = st.text_input("Clave")
            nr = st.selectbox("Rol", ["Operador", "Admin"])
            if st.button("Crear Acceso"):
                conn.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?,?,?)", (nu, nc, nr))
                conn.commit()
                st.rerun()
        with col_b:
            st.write("Lista de Accesos")
            df_u = pd.read_sql_query("SELECT id, nombre, rol FROM usuarios", conn)
            st.dataframe(df_u)