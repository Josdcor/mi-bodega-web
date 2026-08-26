import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import io
from datetime import datetime, date
import calculadora
import os
import sqlite3
import pandas as pd
import streamlit as st

# 1. Definir la ruta dinámica a la base de datos
DB_PATH = os.path.join(os.path.dirname(__file__), "bodega.db")

# 2. Función para conectar y crear tablas si no existen
def inicializar_bd():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crear la tabla productos si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn

# 3. Llamar a la función para garantizar que la tabla exista
conn = inicializar_bd()

# 4. Ahora sí ejecutas la consulta de Pandas sin que falle en la línea 188
df_bajo = pd.read_sql_query(
    "SELECT nombre, stock_actual, stock_minimo FROM productos WHERE stock_actual <= stock_minimo",
    conn
)

st.set_page_config(
    page_title="Mi Bodega Pro - Sistema de Gestión", 
    page_icon="🏪", 
    layout="wide"
)

DB_NAME = "bodega.db"

# --- FUNCIONES DE UTILIDAD Y SEGURIDAD ---
def hash_clave(clave: str) -> str:
    """Encriptación SHA-256 para almacenamiento seguro de contraseñas."""
    return hashlib.sha256(clave.encode('utf-8')).hexdigest()

def conectar_db():
    """Conexión robusta con tiempo de espera extendido y modo WAL para prevenir bloqueos."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

# --- INICIALIZACIÓN BASE DE DATOS ---
def init_db():
    with conectar_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                clave TEXT NOT NULL,
                rol TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT,
                nombre TEXT NOT NULL,
                categoria TEXT,
                precio_usd REAL NOT NULL,
                costo_usd REAL DEFAULT 0,
                stock_actual REAL NOT NULL,
                stock_minimo REAL DEFAULT 5
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cedula TEXT,
                telefono TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                num_factura TEXT NOT NULL,
                producto_id INTEGER,
                cliente_id INTEGER,
                cantidad REAL NOT NULL,
                total_usd REAL NOT NULL,
                total_bs REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                es_credito INTEGER DEFAULT 0,
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL,
                estado TEXT DEFAULT 'Completada',
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                tipo TEXT NOT NULL,
                cantidad REAL NOT NULL,
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT NOT NULL,
                monto REAL NOT NULL,
                moneda TEXT DEFAULT 'USD',
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS abonos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                monto_usd REAL NOT NULL,
                monto_bs REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                fecha TEXT NOT NULL,
                responsable TEXT NOT NULL,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cierres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                total_ventas_usd REAL NOT NULL,
                total_ventas_bs REAL NOT NULL,
                total_gastos_usd REAL NOT NULL,
                saldo_neto_usd REAL NOT NULL,
                responsable TEXT NOT NULL
            )
        """)
        
        # --- MIGRACIÓN AUTOMÁTICA DE COLUMNAS FALTANTES ---
        try:
            cursor.execute("ALTER TABLE ventas ADD COLUMN es_credito INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE ventas ADD COLUMN cliente_id INTEGER")
        except sqlite3.OperationalError:
            pass

        # Usuarios iniciales con contraseñas encriptadas SHA-256
        cursor.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rol) VALUES ('Jose', ?, 'SuperAdmin')", (hash_clave('1234'),))
        cursor.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rol) VALUES ('admin', ?, 'Admin')", (hash_clave('admin123'),))
        
        cursor.execute("UPDATE usuarios SET clave = ? WHERE nombre = 'Jose'", (hash_clave('1234'),))
        cursor.execute("UPDATE usuarios SET clave = ? WHERE nombre = 'admin'", (hash_clave('admin123'),))
        
        conn.commit()

init_db()

# --- CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.session_state.rol = ""
    st.session_state.alerta_stock = False

# --- PANTALLA DE LOGIN (ESTILO TARJETA EXACTO) ---
if not st.session_state.autenticado:
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        st.markdown("# 🏪 Mi Bodega Pro")
        st.markdown("### Iniciar Sesión")
        
        with st.form("login_form", clear_on_submit=False, border=True):
            usuario_input = st.text_input("Usuario")
            clave_input = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("🔑 Ingresar", type="primary", use_container_width=True)
            
            if btn_login:
                if not usuario_input or not clave_input:
                    st.warning("Ingrese usuario y contraseña.")
                else:
                    try:
                        clave_hashed = hash_clave(clave_input.strip())
                        with conectar_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT rol FROM usuarios WHERE nombre = ? AND clave = ?", (usuario_input.strip(), clave_hashed))
                            row = cursor.fetchone()
                        
                        if row:
                            st.session_state.autenticado = True
                            st.session_state.usuario = usuario_input.strip()
                            st.session_state.rol = row[0]
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas.")
                    except sqlite3.Error as e:
                        st.error(f"Error en base de datos: {e}")
    st.stop()

# --- NOTIFICACIÓN EMERGENTE DE STOCK CRÍTICO ---
if not st.session_state.alerta_stock:
    with conectar_db() as conn:
        df_bajo = pd.read_sql_query("SELECT nombre, stock_actual, stock_minimo FROM productos WHERE stock_actual <= stock_minimo", conn)
    if not df_bajo.empty:
        st.toast(f"⚠️ ¡Atención! Hay {len(df_bajo)} productos con stock crítico.", icon="📦")
    st.session_state.alerta_stock = True

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🏪 Mi Bodega Pro")
st.sidebar.markdown(f"👤 **Usuario:** {st.session_state.usuario} ({st.session_state.rol})")

if st.sidebar.button("🔒 Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.session_state.rol = ""
    st.session_state.alerta_stock = False
    st.rerun()

st.sidebar.divider()

# Tasa de cambio editable
tasa_bcv_defecto = calculadora.obtener_tasa_bcv()
tasa_bcv = st.sidebar.number_input("Tasa de Cambio (Bs./$):", value=float(tasa_bcv_defecto), step=0.10, format="%.2f")

# Respaldo automático de base de datos
try:
    with open(DB_NAME, "rb") as db_file:
        st.sidebar.download_button(
            label="💾 Respaldar Base de Datos",
            data=db_file,
            file_name=f"respaldo_bodega_{datetime.now().strftime('%Y%m%d')}.db",
            mime="application/x-sqlite3",
            use_container_width=True
        )
except Exception:
    pass

st.sidebar.markdown("### Menú Principal")

opcion = st.sidebar.selectbox(
    "Menú Principal Selectbox", 
    [
        "🛒 Nueva Venta",
        "📦 Inventario / Productos",
        "👥 Clientes",
        "💰 Abonos",
        "🔒 Cierre de Caja",
        "🔴 Anulación de Ventas",
        "📊 Dashboard",
        "🧮 Calculadora",
        "💸 Gastos / Caja Chica",
        "📜 Historial y Transacciones",
        "⚙️ Gestión de Usuarios"
    ],
    label_visibility="collapsed"
)

# --- MÓDULO 1: NUEVA VENTA (POS / PAGOS MIXTOS / RECTIBO) ---
if opcion == "🛒 Nueva Venta":
    st.header("🛒 Punto de Venta Directo")
    
    with conectar_db() as conn:
        prods = pd.read_sql_query("SELECT id, codigo, nombre, precio_usd, stock_actual FROM productos WHERE stock_actual > 0", conn)
        clientes_df = pd.read_sql_query("SELECT id, nombre FROM clientes", conn)

    if prods.empty:
        st.warning("⚠️ No hay productos disponibles en inventario.")
    else:
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            prod_dict = {f"{row['codigo'] or 'SIN-COD'} | {row['nombre']} (Stock: {row['stock_actual']}) - ${row['precio_usd']:.2f}": row for _, row in prods.iterrows()}
            seleccion = st.selectbox("Seleccionar Producto / Código de Barras", list(prod_dict.keys()))
            prod_sel = prod_dict[seleccion]
        with col_s2:
            cant = st.number_input("Cantidad", min_value=1.0, max_value=float(prod_sel['stock_actual']), value=1.0, step=1.0)
            
        st.divider()
        st.subheader("💳 Método de Pago y Tipo de Operación")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            es_credito = st.checkbox("📌 ¿Venta a Crédito / Fiado?")
            cliente_id = None
            if es_credito:
                if clientes_df.empty:
                    st.error("Registre clientes antes de realizar una venta a crédito.")
                else:
                    cli_dict = {row['nombre']: row['id'] for _, row in clientes_df.iterrows()}
                    cli_sel = st.selectbox("Cliente a Fiarle", list(cli_dict.keys()))
                    cliente_id = cli_dict[cli_sel]

        with col_m2:
            metodo = st.selectbox("Método Principal", ["Efectivo $", "Pago Móvil (Bs)", "Zelle", "Punto de Venta", "Biopago", "Mixto Pago"])
        
        total_usd = round(prod_sel['precio_usd'] * cant, 2)
        total_bs = calculadora.usd_a_bs(total_usd, tasa_bcv)

        with col_m3:
            if metodo == "Mixto Pago":
                monto_efectivo_usd = st.number_input("Monto en Efectivo $", min_value=0.0, max_value=total_usd, value=0.0)
                restante_bs = calculadora.usd_a_bs(total_usd - monto_efectivo_usd, tasa_bcv)
                st.caption(f"Restante a pagar en Bs: **{restante_bs:,.2f} Bs.**")

        st.markdown(f"### Total Pagar: **${total_usd:.2f} USD** / **{total_bs:,.2f} Bs.**")

        if st.button("Procesar Venta", type="primary", use_container_width=True):
            if es_credito and not cliente_id:
                st.error("Debe seleccionar un cliente válido para procesar una venta a crédito.")
            else:
                with conectar_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ? AND stock_actual >= ?", (cant, prod_sel['id'], cant))
                    
                    if cursor.rowcount > 0:
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        num_fact = f"FAC-{int(datetime.now().timestamp())}"
                        
                        cursor.execute("""
                            INSERT INTO ventas (num_factura, producto_id, cliente_id, cantidad, total_usd, total_bs, metodo_pago, es_credito, fecha, responsable, estado)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completada')
                        """, (num_fact, prod_sel['id'], cliente_id, cant, total_usd, total_bs, metodo, 1 if es_credito else 0, fecha_actual, st.session_state.usuario))
                        
                        cursor.execute("""
                            INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                            VALUES (?, 'Venta Web', ?, ?, ?)
                        """, (prod_sel['id'], cant, fecha_actual, st.session_state.usuario))
                        
                        conn.commit()
                        st.success(f"✅ Venta procesada con éxito. Ticket: **{num_fact}**")

                        # Generar recibo imprimible
                        ticket_txt = f"================================\n"
                        ticket_txt += f"        MI BODEGA PRO           \n"
                        ticket_txt += f"================================\n"
                        ticket_txt += f"Comprobante: {num_fact}\n"
                        ticket_txt += f"Fecha: {fecha_actual}\n"
                        ticket_txt += f"Cajero: {st.session_state.usuario}\n"
                        ticket_txt += f"--------------------------------\n"
                        ticket_txt += f"Prod: {prod_sel['nombre']}\n"
                        ticket_txt += f"Cant: {cant} x ${prod_sel['precio_usd']:.2f}\n"
                        ticket_txt += f"Total USD: ${total_usd:.2f}\n"
                        ticket_txt += f"Total Bs: {total_bs:,.2f} Bs.\n"
                        ticket_txt += f"Método: {metodo} {'(FIADO)' if es_credito else ''}\n"
                        ticket_txt += f"================================\n"

                        st.download_button("🖨️ Descargar Recibo / Ticket", ticket_txt, file_name=f"Ticket_{num_fact}.txt", mime="text/plain")
                    else:
                        st.error("❌ Stock insuficiente.")

# --- MÓDULO 2: INVENTARIO / PRODUCTOS ---
elif opcion == "📦 Inventario / Productos":
    st.header("📦 Control de Inventario y Productos")
    
    tab_ver, tab_agregar, tab_editar = st.tabs(["Ver Inventario", "Registrar Nuevo Producto", "Editar / Eliminar Producto"])
    
    with tab_ver:
        with conectar_db() as conn:
            df = pd.read_sql_query("SELECT id, codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo FROM productos", conn)
        
        if not df.empty:
            df['precio_bs'] = df['precio_usd'].apply(lambda x: calculadora.usd_a_bs(x, tasa_bcv))
            busqueda = st.text_input("🔍 Buscar por nombre o código", "")
            if busqueda:
                df = df[df['nombre'].str.contains(busqueda, case=False, na=False) | df['codigo'].str.contains(busqueda, case=False, na=False)]
                
            st.dataframe(df.style.highlight_between(left=0, right=df['stock_minimo'], subset=['stock_actual'], color='#ff4b4b44'), use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar Inventario CSV", csv, "inventario.csv", "text/csv")
        else:
            st.info("No hay productos registrados.")
            
    with tab_agregar:
        with st.form("form_prod"):
            cod = st.text_input("Código de Producto")
            nom = st.text_input("Nombre del Producto")
            cat = st.text_input("Categoría", value="Abarrotes")
            p_usd = st.number_input("Precio Venta ($)", min_value=0.01, step=0.5)
            c_usd = st.number_input("Costo ($)", min_value=0.0, step=0.5)
            stk = st.number_input("Stock Inicial", min_value=1.0, step=1.0)
            stk_min = st.number_input("Stock Mínimo Alerta", min_value=1.0, value=5.0, step=1.0)
            
            if st.form_submit_button("Guardar Producto"):
                if not nom.strip():
                    st.warning("El nombre es requerido.")
                else:
                    with conectar_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO productos (codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cod.strip(), nom.strip(), cat.strip(), p_usd, c_usd, stk, stk_min))
                        conn.commit()
                    st.success("Producto registrado correctamente.")
                    st.rerun()

    with tab_editar:
        with conectar_db() as conn:
            prods_df = pd.read_sql_query("SELECT * FROM productos", conn)
        
        if prods_df.empty:
            st.info("No hay productos registrados para modificar o eliminar.")
        else:
            prod_dict = {f"ID: {row['id']} | {row['nombre']} ({row['codigo'] or 'SIN-COD'})": row for _, row in prods_df.iterrows()}
            sel_p_key = st.selectbox("Seleccionar Producto", list(prod_dict.keys()))
            p_info = prod_dict[sel_p_key]

            col_e1, col_e2 = st.columns(2)
            
            with col_e1:
                st.subheader("✏️ Modificar Producto")
                with st.form("form_edit_prod"):
                    e_cod = st.text_input("Código", value=str(p_info['codigo'] or ''))
                    e_nom = st.text_input("Nombre", value=str(p_info['nombre']))
                    e_cat = st.text_input("Categoría", value=str(p_info['categoria'] or ''))
                    e_precio = st.number_input("Precio ($)", min_value=0.01, value=float(p_info['precio_usd']), step=0.5)
                    e_costo = st.number_input("Costo ($)", min_value=0.0, value=float(p_info['costo_usd']), step=0.5)
                    e_stock = st.number_input("Stock Actual", min_value=0.0, value=float(p_info['stock_actual']), step=1.0)
                    e_stock_min = st.number_input("Stock Mínimo", min_value=1.0, value=float(p_info['stock_minimo']), step=1.0)

                    if st.form_submit_button("Actualizar Producto", type="primary"):
                        with conectar_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE productos 
                                SET codigo = ?, nombre = ?, categoria = ?, precio_usd = ?, costo_usd = ?, stock_actual = ?, stock_minimo = ?
                                WHERE id = ?
                            """, (e_cod.strip(), e_nom.strip(), e_cat.strip(), e_precio, e_costo, e_stock, e_stock_min, p_info['id']))
                            conn.commit()
                        st.success("✅ Producto actualizado correctamente.")
                        st.rerun()

            with col_e2:
                st.subheader("🗑️ Eliminar Producto")
                st.warning(f"¿Desea eliminar permanentemente el producto **{p_info['nombre']}**?")
                if st.button("🗑️ Eliminar Definitivamente", type="primary", key="btn_del_prod"):
                    with conectar_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM productos WHERE id = ?", (p_info['id'],))
                        conn.commit()
                    st.success("✅ Producto eliminado con éxito.")
                    st.rerun()

# --- MÓDULO 3: CLIENTES Y CUENTAS POR COBRAR (FIADOS) ---
elif opcion == "👥 Clientes":
    st.header("👥 Gestión de Clientes y Estado de Cuentas (Fiados)")
    tab_l, tab_r = st.tabs(["Lista de Clientes y Saldos", "Registrar Cliente"])
    
    with tab_l:
        with conectar_db() as conn:
            df_cli = pd.read_sql_query("SELECT * FROM clientes", conn)
            
        if not df_cli.empty:
            # Cálculo dinámico de saldos fiados
            saldos = []
            for _, cli in df_cli.iterrows():
                with conectar_db() as conn:
                    v_credito = pd.read_sql_query("SELECT SUM(total_usd) as tot FROM ventas WHERE cliente_id = ? AND es_credito = 1 AND estado = 'Completada'", conn, params=(cli['id'],))['tot'].fillna(0).iloc[0]
                    v_abonos = pd.read_sql_query("SELECT SUM(monto_usd) as tot FROM abonos WHERE cliente_id = ?", conn, params=(cli['id'],))['tot'].fillna(0).iloc[0]
                saldos.append(v_credito - v_abonos)
                
            df_cli['Saldo Pendiente ($)'] = saldos
            st.dataframe(df_cli, use_container_width=True)
        else:
            st.info("No hay clientes registrados.")
            
    with tab_r:
        with st.form("form_cli"):
            nombre_cli = st.text_input("Nombre Completo")
            cedula_cli = st.text_input("Cédula / RIF")
            telefono_cli = st.text_input("Teléfono")
            if st.form_submit_button("Guardar Cliente"):
                if nombre_cli.strip():
                    with conectar_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO clientes (nombre, cedula, telefono) VALUES (?, ?, ?)", 
                                       (nombre_cli.strip(), cedula_cli.strip(), telefono_cli.strip()))
                        conn.commit()
                    st.success("Cliente guardado con éxito.")
                else:
                    st.warning("Ingrese el nombre del cliente.")

# --- MÓDULO 4: ABONOS ---
elif opcion == "💰 Abonos":
    st.header("💰 Registro de Abonos a Cuentas Fiadas")
    with conectar_db() as conn:
        clientes_df = pd.read_sql_query("SELECT id, nombre FROM clientes", conn)
    
    if clientes_df.empty:
        st.info("No hay clientes registrados en el sistema.")
    else:
        cli_dict = {row['nombre']: row['id'] for _, row in clientes_df.iterrows()}
        cliente_sel = st.selectbox("Seleccionar Cliente", list(cli_dict.keys()))
        
        # Mostrar deuda actual
        with conectar_db() as conn:
            c_id = cli_dict[cliente_sel]
            v_cred = pd.read_sql_query("SELECT SUM(total_usd) as tot FROM ventas WHERE cliente_id = ? AND es_credito = 1 AND estado = 'Completada'", conn, params=(c_id,))['tot'].fillna(0).iloc[0]
            v_abo = pd.read_sql_query("SELECT SUM(monto_usd) as tot FROM abonos WHERE cliente_id = ?", conn, params=(c_id,))['tot'].fillna(0).iloc[0]
            deuda = v_cred - v_abo

        st.info(f"Deuda Actual de **{cliente_sel}**: **${deuda:.2f} USD**")

        monto_abono = st.number_input("Monto Abono ($)", min_value=0.1, step=1.0)
        metodo_abono = st.selectbox("Método de Pago", ["Efectivo $", "Pago Móvil (Bs)", "Zelle"])
        
        if st.button("Registrar Abono"):
            with conectar_db() as conn:
                cursor = conn.cursor()
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                monto_bs = calculadora.usd_a_bs(monto_abono, tasa_bcv)
                
                cursor.execute("""
                    INSERT INTO abonos (cliente_id, monto_usd, monto_bs, metodo_pago, fecha, responsable)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (c_id, monto_abono, monto_bs, metodo_abono, fecha, st.session_state.usuario))
                conn.commit()
            st.success(f"✅ Abono de ${monto_abono:.2f} guardado para {cliente_sel}.")

# --- MÓDULO 5: CIERRE DE CAJA ---
elif opcion == "🔒 Cierre de Caja":
    st.header("🔒 Cierre de Caja Diario")
    
    with conectar_db() as conn:
        ventas_hoy = pd.read_sql_query("SELECT total_usd, total_bs FROM ventas WHERE DATE(fecha) = DATE('now') AND estado = 'Completada'", conn)
        gastos_hoy = pd.read_sql_query("SELECT monto FROM gastos WHERE DATE(fecha) = DATE('now')", conn)
    
    tot_ventas_usd = ventas_hoy['total_usd'].sum() if not ventas_hoy.empty else 0.0
    tot_ventas_bs = ventas_hoy['total_bs'].sum() if not ventas_hoy.empty else 0.0
    tot_gastos_usd = gastos_hoy['monto'].sum() if not gastos_hoy.empty else 0.0
    saldo_neto = tot_ventas_usd - tot_gastos_usd
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventas Totales ($)", f"${tot_ventas_usd:.2f}")
    col2.metric("Ventas Totales (Bs)", f"{tot_ventas_bs:,.2f} Bs.")
    col3.metric("Gastos Totales ($)", f"${tot_gastos_usd:.2f}")
    col4.metric("Saldo Neto ($)", f"${saldo_neto:.2f}")
    
    st.divider()
    if st.button("Ejecutar Cierre de Caja de Hoy", type="primary"):
        with conectar_db() as conn:
            cursor = conn.cursor()
            fecha_cierre = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO cierres (fecha, total_ventas_usd, total_ventas_bs, total_gastos_usd, saldo_neto_usd, responsable)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fecha_cierre, tot_ventas_usd, tot_ventas_bs, tot_gastos_usd, saldo_neto, st.session_state.usuario))
            conn.commit()
        st.success(f"✅ Cierre diario registrado por **{st.session_state.usuario}**.")

# --- MÓDULO 6: ANULACIÓN DE VENTAS ---
elif opcion == "🔴 Anulación de Ventas":
    st.header("🔴 Anulación de Ventas")
    
    with conectar_db() as conn:
        ventas_df = pd.read_sql_query("""
            SELECT v.id, v.num_factura, p.nombre AS producto, v.producto_id, v.cantidad, v.total_usd, v.fecha 
            FROM ventas v 
            LEFT JOIN productos p ON v.producto_id = p.id 
            WHERE v.estado = 'Completada' ORDER BY v.id DESC LIMIT 50
        """, conn)
    
    if ventas_df.empty:
        st.info("No hay ventas activas disponibles para anular.")
    else:
        opciones_ventas = {f"{row['num_factura']} | {row['producto']} ({row['cantidad']} unid) - ${row['total_usd']:.2f}": row for _, row in ventas_df.iterrows()}
        sel_v = st.selectbox("Seleccione la venta a anular", list(opciones_ventas.keys()))
        v_data = opciones_ventas[sel_v]
        
        if st.button("⚠️ Confirmar Anulación", type="primary"):
            with conectar_db() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE ventas SET estado = 'Anulada' WHERE id = ?", (v_data['id'],))
                cursor.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (v_data['cantidad'], v_data['producto_id']))
                conn.commit()
            st.success(f"Venta {v_data['num_factura']} anulada y stock retornado al inventario.")

# --- MÓDULO 7: DASHBOARD ---
elif opcion == "📊 Dashboard":
    st.header("📊 Dashboard del Negocio")
    
    with conectar_db() as conn:
        df_v = pd.read_sql_query("SELECT total_usd, fecha FROM ventas WHERE estado = 'Completada'", conn)
        df_p = pd.read_sql_query("SELECT nombre, stock_actual FROM productos", conn)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📦 Stock por Producto")
        if not df_p.empty:
            st.bar_chart(df_p.set_index("nombre")["stock_actual"])
    with c2:
        st.subheader("💵 Tendencia de Ventas ($)")
        if not df_v.empty:
            st.line_chart(df_v["total_usd"])

# --- MÓDULO 8: CALCULADORA ---
elif opcion == "🧮 Calculadora":
    st.header("🧮 Conversor Rápido Divisas")
    c1, c2 = st.columns(2)
    with c1:
        m_usd = st.number_input("Monto USD ($)", min_value=0.0, value=1.0, step=1.0)
        res_bs = calculadora.usd_a_bs(m_usd, tasa_bcv)
        st.info(f"Equivalente: **{res_bs:,.2f} Bs.**")
    with c2:
        m_bs = st.number_input("Monto Bolívares (Bs)", min_value=0.0, value=tasa_bcv, step=10.0)
        res_usd = calculadora.bs_a_usd(m_bs, tasa_bcv)
        st.info(f"Equivalente: **${res_usd:.2f} USD**")

# --- MÓDULO 9: GASTOS / CAJA CHICA ---
elif opcion == "💸 Gastos / Caja Chica":
    st.header("💸 Gastos Operativos")
    with st.form("form_gasto_cc"):
        desc = st.text_input("Descripción del Gasto")
        monto = st.number_input("Monto ($)", min_value=0.1, step=0.5)
        if st.form_submit_button("Guardar Gasto"):
            if desc.strip():
                with conectar_db() as conn:
                    cursor = conn.cursor()
                    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO gastos (descripcion, monto, moneda, fecha, responsable) VALUES (?, ?, 'USD', ?, ?)",
                                   (desc.strip(), monto, fecha, st.session_state.usuario))
                    conn.commit()
                st.success("Gasto registrado con éxito.")

    with conectar_db() as conn:
        df_g = pd.read_sql_query("SELECT * FROM gastos ORDER BY id DESC", conn)
    if not df_g.empty:
        st.dataframe(df_g, use_container_width=True)

# --- MÓDULO 10: HISTORIAL Y TRANSACCIONES ---
elif opcion == "📜 Historial y Transacciones":
    st.header("📜 Historial General de Transacciones")
    with conectar_db() as conn:
        df_h = pd.read_sql_query("""
            SELECT v.id, v.num_factura, p.nombre AS producto, c.nombre AS cliente, v.cantidad, v.total_usd, v.total_bs, v.metodo_pago, v.es_credito, v.fecha, v.responsable, v.estado 
            FROM ventas v 
            LEFT JOIN productos p ON v.producto_id = p.id 
            LEFT JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.id DESC
        """, conn)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)

# --- MÓDULO 11: GESTIÓN DE USUARIOS ---
elif opcion == "⚙️ Gestión de Usuarios":
    st.header("⚙️ Administración de Usuarios")
    
    if st.session_state.rol not in ["Admin", "SuperAdmin"]:
        st.error("No tienes permisos de administración.")
    else:
        tab_u1, tab_u2, tab_u3, tab_u4 = st.tabs(["Lista de Usuarios", "Crear Usuario", "Cambiar Clave", "Eliminar Usuario"])
        
        with tab_u1:
            with conectar_db() as conn:
                df_u = pd.read_sql_query("SELECT id, nombre, rol FROM usuarios", conn)
            st.dataframe(df_u, use_container_width=True)
            
        with tab_u2:
            st.subheader("➕ Registrar Nuevo Usuario")
            with st.form("form_u"):
                n_usr = st.text_input("Nombre de Usuario")
                c_usr = st.text_input("Contraseña", type="password")
                r_usr = st.selectbox("Rol", ["Cajero", "Admin", "SuperAdmin"])
                
                if st.form_submit_button("Crear Usuario", type="primary"):
                    if n_usr.strip() and c_usr.strip():
                        try:
                            with conectar_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", 
                                               (n_usr.strip(), hash_clave(c_usr.strip()), r_usr))
                                conn.commit()
                            st.success("Usuario registrado de forma segura.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("El nombre de usuario ya existe.")
                    else:
                        st.warning("Debe ingresar usuario y contraseña.")

        with tab_u3:
            st.subheader("🔑 Cambiar Contraseña de Usuario")
            with conectar_db() as conn:
                usrs_df = pd.read_sql_query("SELECT id, nombre FROM usuarios", conn)
            
            if not usrs_df.empty:
                with st.form("form_cambiar_clave", clear_on_submit=True):
                    usr_sel_clave = st.selectbox("Seleccionar Usuario", usrs_df['nombre'].tolist())
                    nueva_clave = st.text_input("Nueva Contraseña", type="password")
                    btn_cambiar_pass = st.form_submit_button("Actualizar Contraseña", type="primary")
                    
                    if btn_cambiar_pass:
                        if nueva_clave.strip():
                            clave_hash_nueva = hash_clave(nueva_clave.strip())
                            with conectar_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE usuarios SET clave = ? WHERE nombre = ?", (clave_hash_nueva, usr_sel_clave))
                                conn.commit()
                            st.success(f"✅ Contraseña del usuario '{usr_sel_clave}' actualizada con éxito.")
                            st.rerun()
                        else:
                            st.warning("Ingrese una contraseña válida.")

        with tab_u4:
            st.subheader("🗑️ Eliminar Usuario")
            with conectar_db() as conn:
                usrs_df_del = pd.read_sql_query("SELECT id, nombre, rol FROM usuarios", conn)
            
            if not usrs_df_del.empty:
                # Filtrar para evitar que el usuario activo se elimine a sí mismo
                usrs_filtrados = usrs_df_del[usrs_df_del['nombre'] != st.session_state.usuario]
                
                if usrs_filtrados.empty:
                    st.info("No hay otros usuarios registrados que se puedan eliminar.")
                else:
                    usr_sel_del = st.selectbox("Seleccionar Usuario a Eliminar", usrs_filtrados['nombre'].tolist(), key="sel_usr_del")
                    st.warning(f"⚠️ Esta acción borrará al usuario **{usr_sel_del}** de la base de datos.")
                    
                    if st.button("🗑️ Eliminar Usuario Definitivamente", type="primary", key="btn_del_usr"):
                        with conectar_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM usuarios WHERE nombre = ?", (usr_sel_del,))
                            conn.commit()
                        st.success(f"✅ Usuario '{usr_sel_del}' eliminado.")
                        st.rerun()
