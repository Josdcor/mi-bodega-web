import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Mi Bodega Pro",
    page_icon="🏪",
    layout="wide"
)

# --- CLASE CALCULADORA Y AUXILIARES ---
class CalculadoraTasa:
    @staticmethod
    def usd_a_bs(monto_usd, tasa):
        return float(monto_usd) * float(tasa)

    @staticmethod
    def bs_a_usd(monto_bs, tasa):
        return float(monto_bs) / float(tasa) if tasa > 0 else 0.0

calculadora = CalculadoraTasa()

def hash_clave(clave):
    return hashlib.sha256(clave.encode()).hexdigest()

# --- CONEXIÓN Y BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect("bodega.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def es_postgres():
    return False

def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Tabla Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)
    
    # Tabla Productos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio_usd REAL NOT NULL,
            costo_usd REAL NOT NULL,
            stock_actual REAL NOT NULL,
            stock_minimo REAL DEFAULT 5.0
        )
    """)

    # Tabla Clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            cedula TEXT
        )
    """)

    # Tabla Ventas
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
            estado TEXT DEFAULT 'Completada'
        )
    """)

    # Tabla Abonos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS abonos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            monto_usd REAL NOT NULL,
            monto_bs REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            nota TEXT,
            fecha TEXT NOT NULL,
            responsable TEXT NOT NULL
        )
    """)

    # Tabla Gastos
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

    # Tabla Movimientos (Kárdex)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            fecha TEXT NOT NULL,
            responsable TEXT NOT NULL
        )
    """)

    # Tabla Cierres
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

    # Crear Usuario Admin por Defecto si no existe
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)",
            ("admin", hash_clave("admin123"), "SuperAdmin")
        )

    conn.commit()
    conn.close()

def ejecutar_sql(query, params=(), fetch=None):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    res = None
    if fetch == "one":
        res = cursor.fetchone()
    elif fetch == "all":
        res = cursor.fetchall()
        
    conn.commit()
    conn.close()
    return res

inicializar_db()

# --- ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario" not in st.session_state:
    st.session_state.usuario = ""
if "rol" not in st.session_state:
    st.session_state.rol = ""

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🏪 Sistema Mi Bodega Pro")
    st.subheader("Inicio de Sesión")
    
    with st.form("form_login"):
        usr_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Ingresar", type="primary")
        
        if btn_login:
            res = ejecutar_sql(
                "SELECT nombre, rol FROM usuarios WHERE nombre = ? AND clave = ?",
                (usr_input.strip(), hash_clave(pass_input.strip())),
                fetch="one"
            )
            if res:
                st.session_state.autenticado = True
                st.session_state.usuario = res["nombre"]
                st.session_state.rol = res["rol"]
                st.success(f"Bienvenido {res['nombre']}")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# --- BARRA LATERAL (SIDEBAR) ---
st.sidebar.title(f"👤 {st.session_state.usuario} ({st.session_state.rol})")
tasa_bcv = st.sidebar.number_input("Tasa BCV (Bs/$)", min_value=1.0, value=60.0, step=0.5)

opcion = st.sidebar.radio("Menú Principal", [
    "📦 Productos / Inventario",
    "🛒 Registrar Venta",
    "👥 Clientes y Créditos",
    "💳 Abonos",
    "🔒 Cierre de Caja",
    "🔴 Anulación de Ventas",
    "📊 Dashboard",
    "🧮 Calculadora",
    "💸 Gastos / Caja Chica",
    "📜 Historial y Transacciones",
    "⚙️ Gestión de Usuarios"
])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario = ""
    st.session_state.rol = ""
    st.rerun()

# ==========================================
# MÓDULOS DE LA APLICACIÓN
# ==========================================

# MÓDULO 1: PRODUCTOS / INVENTARIO
if opcion == "📦 Productos / Inventario":
    st.header("📦 Gestión de Inventario y Productos")
    
    tab_p1, tab_p2 = st.tabs(["Lista de Productos", "➕ Registrar Nuevo Producto"])
    
    with tab_p1:
        conn = conectar_db()
        try:
            df_prod = pd.read_sql_query("SELECT id, codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo FROM productos ORDER BY nombre ASC", conn)
        finally:
            conn.close()

        if not df_prod.empty:
            st.dataframe(
                df_prod,
                use_container_width=True,
                column_config={
                    "precio_usd": st.column_config.NumberColumn("Precio USD", format="$%.2f"),
                    "costo_usd": st.column_config.NumberColumn("Costo USD", format="$%.2f"),
                    "stock_actual": st.column_config.NumberColumn("Stock Actual"),
                    "stock_minimo": st.column_config.NumberColumn("Stock Mínimo")
                },
                hide_index=True
            )
        else:
            st.info("No hay productos registrados en el inventario.")

    with tab_p2:
        with st.form("form_reg_producto", clear_on_submit=True):
            cod_p = st.text_input("Código de Barras / SKU")
            nom_p = st.text_input("Nombre del Producto")
            cat_p = st.text_input("Categoría", value="General")
            c1, c2 = st.columns(2)
            costo_p = c1.number_input("Costo USD ($)", min_value=0.01, step=0.5)
            precio_p = c2.number_input("Precio Venta USD ($)", min_value=0.01, step=0.5)
            c3, c4 = st.columns(2)
            stk_p = c3.number_input("Stock Inicial", min_value=0.0, step=1.0)
            stk_min_p = c4.number_input("Stock Mínimo Alerta", min_value=1.0, value=5.0, step=1.0)
            
            if st.form_submit_button("Guardar Producto", type="primary"):
                if nom_p.strip():
                    try:
                        ejecutar_sql("""
                            INSERT INTO productos (codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cod_p.strip(), nom_p.strip(), cat_p.strip(), precio_p, costo_p, stk_p, stk_min_p))
                        st.success(f"✅ Producto **{nom_p}** registrado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar producto: {e}")
                else:
                    st.warning("Ingrese un nombre válido para el producto.")

# MÓDULO 2: REGISTRAR VENTA
elif opcion == "🛒 Registrar Venta":
    st.header("🛒 Registrar Nueva Venta")
    
    # Campo de búsqueda dinámica
    busqueda = st.text_input("🔍 Buscar Producto por Nombre, Código o Categoría", placeholder="Ej: 750123..., Arroz, Lacteos...").strip().lower()

    conn = conectar_db()
    try:
        df_p = pd.read_sql_query("SELECT id, codigo, nombre, categoria, precio_usd, stock_actual FROM productos WHERE stock_actual > 0 ORDER BY nombre ASC", conn)
        df_c = pd.read_sql_query("SELECT id, nombre FROM clientes ORDER BY nombre ASC", conn)
    finally:
        conn.close()
        
    if df_p.empty:
        st.warning("⚠️ No hay productos disponibles con stock en el inventario.")
    else:
        # Filtrar el dataframe según el texto ingresado en el buscador
        if busqueda:
            df_p['codigo_str'] = df_p['codigo'].fillna('').astype(str).str.lower()
            df_p['nombre_str'] = df_p['nombre'].fillna('').astype(str).str.lower()
            df_p['cat_str'] = df_p['categoria'].fillna('').astype(str).str.lower()
            
            df_p = df_p[
                df_p['nombre_str'].str.contains(busqueda) | 
                df_p['codigo_str'].str.contains(busqueda) | 
                df_p['cat_str'].str.contains(busqueda)
            ]

        if df_p.empty:
            st.error(f"❌ No se encontraron productos que coincidan con '{busqueda}'.")
        else:
            # Crear las opciones con formato claro: [Código] Nombre (Categoría) - Stock - Precio
            opciones_prod = {}
            for _, row in df_p.iterrows():
                cod_str = f"[{row['codigo']}] " if row['codigo'] else ""
                cat_str = f" ({row['categoria']})" if row['categoria'] else ""
                label = f"{cod_str}{row['nombre']}{cat_str} | Stock: {row['stock_actual']} | ${float(row['precio_usd']):.2f}"
                opciones_prod[label] = row

            prod_sel_key = st.selectbox("Seleccionar Producto Encontrado", list(opciones_prod.keys()))
            prod_sel = opciones_prod[prod_sel_key]
            
            c_cant, c_pago = st.columns([1, 2])
            with c_cant:
                cant = st.number_input(
                    "Cantidad a Vender", 
                    min_value=0.1, 
                    max_value=float(prod_sel['stock_actual']), 
                    value=1.0, 
                    step=1.0
                )
            
            with c_pago:
                metodo = st.selectbox("Método de Pago", ["Efectivo USD", "Pago Móvil", "Transferencia Bs", "Zelle", "Efectivo Bs"])
            
            es_credito = st.checkbox("¿Es una venta a crédito (Fiado)?")
            cliente_id = None
            if es_credito:
                if df_c.empty:
                    st.error("No hay clientes registrados para asociar el crédito.")
                else:
                    opciones_cli = {row['nombre']: row['id'] for _, row in df_c.iterrows()}
                    cli_sel_key = st.selectbox("Seleccionar Cliente", list(opciones_cli.keys()))
                    cliente_id = opciones_cli[cli_sel_key]

            total_usd = float(prod_sel['precio_usd']) * cant
            total_bs = calculadora.usd_a_bs(total_usd, tasa_bcv)
            
            st.divider()
            col_v1, col_v2 = st.columns(2)
            col_v1.metric("Total USD", f"${total_usd:.2f}")
            col_v2.metric("Total Bs", f"{total_bs:,.2f} Bs.")
            
            if st.button("🛒 Procesar Venta", type="primary", use_container_width=True):
                if es_credito and not cliente_id:
                    st.error("Debe seleccionar un cliente válido para procesar a crédito.")
                else:
                    prod_row = ejecutar_sql("SELECT stock_actual FROM productos WHERE id = ?", (int(prod_sel['id']),), fetch="one")
                    if prod_row and float(prod_row[0]) >= cant:
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        num_fact = f"FAC-{int(datetime.now().timestamp())}"
                        pid = int(prod_sel['id'])
                        
                        try:
                            ejecutar_sql("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?", (cant, pid))
                            ejecutar_sql("""
                                INSERT INTO ventas (num_factura, producto_id, cliente_id, cantidad, total_usd, total_bs, metodo_pago, es_credito, fecha, responsable, estado)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completada')
                            """, (num_fact, pid, cliente_id, cant, total_usd, total_bs, metodo, 1 if es_credito else 0, fecha_actual, st.session_state.usuario))
                            
                            ejecutar_sql("""
                                INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                                VALUES (?, 'Venta', ?, ?, ?)
                            """, (pid, cant, fecha_actual, st.session_state.usuario))
                            
                            st.success(f"✅ Venta procesada con éxito. Ticket: **{num_fact}**")

                            ticket_txt = (
                                "================================\n"
                                "         MI BODEGA PRO          \n"
                                "================================\n"
                                f"Comprobante: {num_fact}\n"
                                f"Fecha: {fecha_actual}\n"
                                f"Cajero: {st.session_state.usuario}\n"
                                "--------------------------------\n"
                                f"Producto: {prod_sel['nombre']}\n"
                                f"Cantidad: {cant} x ${float(prod_sel['precio_usd']):.2f}\n"
                                f"Total USD: ${total_usd:.2f}\n"
                                f"Total Bs:  {total_bs:,.2f} Bs.\n"
                                f"Método:    {metodo} {'(FIADO)' if es_credito else ''}\n"
                                "================================\n"
                                "      ¡Gracias por su compra!   \n"
                                "================================\n"
                            )

                            st.download_button(
                                label="🖨️ Descargar Recibo / Ticket",
                                data=ticket_txt,
                                file_name=f"Ticket_{num_fact}.txt",
                                mime="text/plain"
                            )
                        except Exception as e:
                            st.error(f"❌ Error al procesar la transacción: {e}")
                    else:
                        st.error("❌ Stock insuficiente para realizar la venta.")
                        
# MÓDULO 3: CLIENTES Y CRÉDITOS
elif opcion == "👥 Clientes y Créditos":
    st.header("👥 Gestión de Clientes")
    
    with st.form("form_cliente", clear_on_submit=True):
        st.subheader("Registrar Nuevo Cliente")
        nom_c = st.text_input("Nombre y Apellido")
        ced_c = st.text_input("Cédula / DNI")
        tel_c = st.text_input("Teléfono")
        
        if st.form_submit_button("Guardar Cliente", type="primary"):
            if nom_c.strip():
                ejecutar_sql("INSERT INTO clientes (nombre, cedula, telefono) VALUES (?, ?, ?)", (nom_c.strip(), ced_c.strip(), tel_c.strip()))
                st.success(f"✅ Cliente **{nom_c}** registrado correctamente.")
                st.rerun()
            else:
                st.warning("Ingrese al menos el nombre del cliente.")

    st.subheader("📋 Lista de Clientes Registrados")
    conn = conectar_db()
    try:
        df_cli = pd.read_sql_query("SELECT id, nombre AS Nombre, cedula AS Cédula, telefono AS Teléfono FROM clientes ORDER BY nombre ASC", conn)
    finally:
        conn.close()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

# MÓDULO 4: ABONOS (FIADOS)
elif opcion == "💳 Abonos":
    st.header("💳 Abonos de Clientes (Fiados)")
    
    conn = conectar_db()
    try:
        df_c = pd.read_sql_query("SELECT id, nombre FROM clientes ORDER BY nombre ASC", conn)
    finally:
        conn.close()
        
    if df_c.empty:
        st.info("No hay clientes registrados.")
    else:
        opciones_cli = {row['nombre']: row['id'] for _, row in df_c.iterrows()}
        cliente_sel = st.selectbox("Seleccionar Cliente", list(opciones_cli.keys()))
        c_id = opciones_cli[cliente_sel]
        
        conn = conectar_db()
        try:
            res_v = pd.read_sql_query("SELECT SUM(total_usd) as total FROM ventas WHERE cliente_id = ? AND es_credito = 1 AND estado = 'Completada'", conn, params=(c_id,))
            res_a = pd.read_sql_query("SELECT SUM(monto_usd) as total FROM abonos WHERE cliente_id = ?", conn, params=(c_id,))
        finally:
            conn.close()
            
        v_cred = float(res_v['total'].iloc[0]) if not res_v.empty and res_v['total'].iloc[0] is not None else 0.0
        v_abo = float(res_a['total'].iloc[0]) if not res_a.empty and res_a['total'].iloc[0] is not None else 0.0
        deuda = v_cred - v_abo
        
        st.info(f"Deuda Actual de **{cliente_sel}**: **${deuda:.2f} USD**")

        if deuda > 0:
            with st.form("form_abono", clear_on_submit=True):
                monto_abono = st.number_input("Monto Abono ($)", min_value=0.01, max_value=float(deuda), step=1.0)
                metodo_abono = st.selectbox("Método de Pago", ["Efectivo USD", "Pago Móvil", "Transferencia Bs", "Zelle"])
                nota_abono = st.text_input("Nota / Referencia (Opcional)")
                
                if st.form_submit_button("Registrar Abono", type="primary"):
                    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    monto_bs = calculadora.usd_a_bs(monto_abono, tasa_bcv)
                    
                    ejecutar_sql("""
                        INSERT INTO abonos (cliente_id, monto_usd, monto_bs, metodo_pago, nota, fecha, responsable)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (c_id, monto_abono, monto_bs, metodo_abono, nota_abono.strip(), fecha, st.session_state.usuario))
                    
                    st.success(f"✅ Abono de ${monto_abono:.2f} guardado para {cliente_sel}.")
                    st.rerun()
        else:
            st.success("🎉 Este cliente no posee deudas pendientes.")

# MÓDULO 5: CIERRE DE CAJA
elif opcion == "🔒 Cierre de Caja":
    st.header("🔒 Cierre de Caja Diario")
    
    conn = conectar_db()
    try:
        if es_postgres():
            q_v = "SELECT total_usd, total_bs FROM ventas WHERE fecha::date = CURRENT_DATE AND estado = 'Completada'"
            q_g = "SELECT monto FROM gastos WHERE fecha::date = CURRENT_DATE"
        else:
            q_v = "SELECT total_usd, total_bs FROM ventas WHERE DATE(fecha) = DATE('now') AND estado = 'Completada'"
            q_g = "SELECT monto FROM gastos WHERE DATE(fecha) = DATE('now')"
            
        ventas_hoy = pd.read_sql_query(q_v, conn)
        gastos_hoy = pd.read_sql_query(q_g, conn)
    finally:
        conn.close()
    
    tot_ventas_usd = float(ventas_hoy['total_usd'].sum()) if not ventas_hoy.empty else 0.0
    tot_ventas_bs = float(ventas_hoy['total_bs'].sum()) if not ventas_hoy.empty else 0.0
    tot_gastos_usd = float(gastos_hoy['monto'].sum()) if not gastos_hoy.empty else 0.0
    saldo_neto = tot_ventas_usd - tot_gastos_usd
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventas Totales ($)", f"${tot_ventas_usd:.2f}")
    col2.metric("Ventas Totales (Bs)", f"{tot_ventas_bs:,.2f} Bs.")
    col3.metric("Gastos Totales ($)", f"${tot_gastos_usd:.2f}")
    col4.metric("Saldo Neto ($)", f"${saldo_neto:.2f}")
    
    st.divider()
    if st.button("Ejecutar Cierre de Caja de Hoy", type="primary"):
        fecha_cierre = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ejecutar_sql("""
            INSERT INTO cierres (fecha, total_ventas_usd, total_ventas_bs, total_gastos_usd, saldo_neto_usd, responsable)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fecha_cierre, tot_ventas_usd, tot_ventas_bs, tot_gastos_usd, saldo_neto, st.session_state.usuario))
        st.success(f"✅ Cierre diario registrado por **{st.session_state.usuario}**.")

# MÓDULO 6: ANULACIÓN DE VENTAS
elif opcion == "🔴 Anulación de Ventas":
    st.header("🔴 Anulación de Ventas")
    
    conn = conectar_db()
    try:
        ventas_df = pd.read_sql_query("""
            SELECT v.id, v.num_factura, p.nombre AS producto, v.producto_id, v.cantidad, v.total_usd, v.fecha 
            FROM ventas v 
            LEFT JOIN productos p ON v.producto_id = p.id 
            WHERE v.estado = 'Completada' ORDER BY v.id DESC LIMIT 50
        """, conn)
    finally:
        conn.close()
    
    if ventas_df.empty:
        st.info("No hay ventas activas disponibles para anular.")
    else:
        opciones_ventas = {
            f"{row['num_factura']} | {row['producto']} ({row['cantidad']} unid) - ${float(row['total_usd']):.2f}": row 
            for _, row in ventas_df.iterrows()
        }
        sel_v = st.selectbox("Seleccione la venta a anular", list(opciones_ventas.keys()))
        v_data = opciones_ventas[sel_v]
        
        if st.button("⚠️ Confirmar Anulación", type="primary"):
            try:
                ejecutar_sql("UPDATE ventas SET estado = 'Anulada' WHERE id = ?", (int(v_data['id']),))
                ejecutar_sql("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (float(v_data['cantidad']), int(v_data['producto_id'])))
                
                fecha_act = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ejecutar_sql("""
                    INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                    VALUES (?, 'Anulación Venta', ?, ?, ?)
                """, (int(v_data['producto_id']), float(v_data['cantidad']), fecha_act, st.session_state.usuario))
                
                st.success(f"Venta {v_data['num_factura']} anulada y stock retornado al inventario.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al procesar la anulación: {e}")

# MÓDULO 7: DASHBOARD
elif opcion == "📊 Dashboard":
    st.header("📊 Dashboard del Negocio")
    
    conn = conectar_db()
    try:
        df_v = pd.read_sql_query("SELECT total_usd, fecha FROM ventas WHERE estado = 'Completada'", conn)
        df_p = pd.read_sql_query("SELECT nombre, stock_actual FROM productos ORDER BY stock_actual ASC", conn)
    finally:
        conn.close()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📦 Stock por Producto")
        if not df_p.empty:
            df_p['stock_actual'] = df_p['stock_actual'].astype(float)
            st.bar_chart(df_p.set_index("nombre")["stock_actual"])
        else:
            st.info("Sin productos registrados.")
            
    with c2:
        st.subheader("💵 Tendencia de Ventas ($)")
        if not df_v.empty:
            df_v['total_usd'] = df_v['total_usd'].astype(float)
            st.line_chart(df_v["total_usd"])
        else:
            st.info("Sin historial de ventas.")

# MÓDULO 8: CALCULADORA DE PRECIOS POR UNIDAD
elif opcion == "🧮 Calculadora":
    st.header("🧮 Calculadora de Costos y Precio de Venta por Unidad")
    st.caption("Determina el costo real por unidad incluyendo gastos operativos y aplicando el margen de ganancia deseado.")
    
    col_calc1, col_calc2 = st.columns(2)
    
    with col_calc1:
        st.subheader("📦 Datos de Compra al Mayor")
        costo_bulto_usd = st.number_input("Costo del Bulto / Saco / Caja ($)", min_value=0.01, value=18.00, step=1.0)
        unidades_por_bulto = st.number_input("Cantidad de Unidades por Bulto", min_value=1.0, value=20.0, step=1.0)
        gastos_adicionales_usd = st.number_input("Gastos Adicionales (Flete, Pasajes) ($)", min_value=0.00, value=2.00, step=0.50)
        
    with col_calc2:
        st.subheader("📈 Margen de Ganancia e Impuestos")
        opcion_ganancia = st.radio("Seleccionar % de Ganancia", ["20%", "30%", "40%", "Otro %"], index=1, horizontal=True)
        
        if opcion_ganancia == "20%":
            pct_ganancia = 20.0
        elif opcion_ganancia == "30%":
            pct_ganancia = 30.0
        elif opcion_ganancia == "40%":
            pct_ganancia = 40.0
        else:
            pct_ganancia = st.number_input("Porcentaje Personalizado (%)", min_value=0.0, value=35.0, step=1.0)

        incluir_iva = st.checkbox("¿Incluir IVA / Impuesto (16%) en el costo base?")
        pct_iva = 16.0 if incluir_iva else 0.0

    st.divider()

    costo_total_compra = costo_bulto_usd + gastos_adicionales_usd
    costo_base_unidad = costo_total_compra / unidades_por_bulto
    
    if incluir_iva:
        costo_base_unidad += (costo_base_unidad * (pct_iva / 100.0))

    precio_venta_unidad_usd = costo_base_unidad * (1.0 + (pct_ganancia / 100.0))
    precio_venta_unidad_bs = calculadora.usd_a_bs(precio_venta_unidad_usd, tasa_bcv)
    ganancia_neta_unidad = precio_venta_unidad_usd - costo_base_unidad
    ganancia_neta_bulto = ganancia_neta_unidad * unidades_por_bulto

    st.subheader("📊 Desglose de Resultados")
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    res_col1.metric("Costo Real u. ($)", f"${costo_base_unidad:.2f}")
    res_col2.metric("Precio Venta u. ($)", f"${precio_venta_unidad_usd:.2f}")
    res_col3.metric("Precio Venta u. (Bs)", f"{precio_venta_unidad_bs:,.2f} Bs.")
    res_col4.metric("Ganancia Bulto ($)", f"${ganancia_neta_bulto:.2f}")

    st.info(f"💡 **Resumen:** Comprando el bulto a **${costo_bulto_usd:.2f}** con **${gastos_adicionales_usd:.2f}** en gastos, cada una de las **{int(unidades_por_bulto)}** unidades te cuesta **${costo_base_unidad:.2f}**. Vendiendo cada unidad a **${precio_venta_unidad_usd:.2f}** ({precio_venta_unidad_bs:,.2f} Bs.), ganas **${ganancia_neta_unidad:.2f}** por unidad ({pct_ganancia}% margen).")

    st.divider()
    st.subheader("📥 Cargar Resultado Directo al Inventario")
    
    with st.form("form_cargar_inv"):
        nom_prod = st.text_input("Nombre del Producto", placeholder="Ej: Arroz Primor 1Kg")
        cod_prod = st.text_input("Código de Barras (Opcional)")
        cat_prod = st.text_input("Categoría", value="Abarrotes")
        stk_inicial = st.number_input("Stock a Agregar (Unidades)", min_value=1.0, value=unidades_por_bulto, step=1.0)
        
        if st.form_submit_button("💾 Guardar / Actualizar en Inventario", type="primary"):
            if not nom_prod.strip():
                st.warning("Ingrese un nombre de producto válido.")
            else:
                prod_existente = ejecutar_sql("SELECT id, stock_actual FROM productos WHERE LOWER(nombre) = LOWER(?)", (nom_prod.strip(),), fetch="one")
                
                if prod_existente:
                    nuevo_stock = float(prod_existente[1]) + stk_inicial
                    ejecutar_sql("""
                        UPDATE productos 
                        SET precio_usd = ?, costo_usd = ?, stock_actual = ?
                        WHERE id = ?
                    """, (round(precio_venta_unidad_usd, 2), round(costo_base_unidad, 2), nuevo_stock, int(prod_existente[0])))
                    st.success(f"✅ Producto **{nom_prod}** actualizado. Nuevo precio: **${precio_venta_unidad_usd:.2f}**, Stock total: **{nuevo_stock}** unid.")
                else:
                    ejecutar_sql("""
                        INSERT INTO productos (codigo, nombre, categoria, precio_usd, costo_usd, stock_actual, stock_minimo)
                        VALUES (?, ?, ?, ?, ?, ?, 5.0)
                    """, (cod_prod.strip(), nom_prod.strip(), cat_prod.strip(), round(precio_venta_unidad_usd, 2), round(costo_base_unidad, 2), stk_inicial))
                    st.success(f"✅ Producto **{nom_prod}** creado en inventario a **${precio_venta_unidad_usd:.2f}** con **{stk_inicial}** unid.")

# MÓDULO 9: GASTOS / CAJA CHICA
elif opcion == "💸 Gastos / Caja Chica":
    st.header("💸 Gastos Operativos")
    
    with st.form("form_gasto_cc", clear_on_submit=True):
        desc = st.text_input("Descripción del Gasto", placeholder="Ej: Compra de bolsas, pago de transporte")
        monto = st.number_input("Monto ($)", min_value=0.01, step=0.50)
        
        if st.form_submit_button("Guardar Gasto", type="primary"):
            if desc.strip():
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ejecutar_sql(
                    "INSERT INTO gastos (descripcion, monto, moneda, fecha, responsable) VALUES (?, ?, 'USD', ?, ?)",
                    (desc.strip(), monto, fecha, st.session_state.usuario)
                )
                st.success("✅ Gasto registrado con éxito.")
                st.rerun()
            else:
                st.warning("Debe ingresar una descripción para el gasto.")

    st.subheader("📋 Historial de Gastos")
    conn = conectar_db()
    try:
        df_g = pd.read_sql_query("SELECT id, descripcion, monto, moneda, fecha, responsable FROM gastos ORDER BY id DESC", conn)
    finally:
        conn.close()

    if not df_g.empty:
        st.dataframe(
            df_g,
            use_container_width=True,
            column_config={
                "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm")
            },
            hide_index=True
        )
    else:
        st.info("No hay gastos registrados.")

# MÓDULO 10: HISTORIAL Y TRANSACCIONES
elif opcion == "📜 Historial y Transacciones":
    st.header("📜 Historial General de Transacciones")
    
    conn = conectar_db()
    try:
        df_h = pd.read_sql_query("""
            SELECT 
                v.id, 
                v.num_factura AS "Factura", 
                p.nombre AS "Producto", 
                COALESCE(c.nombre, 'Cliente Contado') AS "Cliente", 
                v.cantidad AS "Cantidad", 
                v.total_usd AS "Total USD", 
                v.total_bs AS "Total Bs", 
                v.metodo_pago AS "Método", 
                v.es_credito AS "Crédito", 
                v.fecha AS "Fecha", 
                v.responsable AS "Cajero", 
                v.estado AS "Estado" 
            FROM ventas v 
            LEFT JOIN productos p ON v.producto_id = p.id 
            LEFT JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.id DESC
        """, conn)
    finally:
        conn.close()

    if not df_h.empty:
        st.dataframe(
            df_h, 
            use_container_width=True,
            column_config={
                "Total USD": st.column_config.NumberColumn(format="$%.2f"),
                "Total Bs": st.column_config.NumberColumn(format="Bs. %,.2f"),
                "Crédito": st.column_config.CheckboxColumn(),
                "Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
            },
            hide_index=True
        )
    else:
        st.info("No hay registro de transacciones en la base de datos.")

# MÓDULO 11: GESTIÓN DE USUARIOS
elif opcion == "⚙️ Gestión de Usuarios":
    st.header("⚙️ Administración de Usuarios")
    
    if st.session_state.get("rol") not in ["Admin", "SuperAdmin"]:
        st.error("🔒 No tienes permisos de administración para acceder a esta sección.")
    else:
        tab_u1, tab_u2, tab_u3, tab_u4 = st.tabs(["📋 Lista de Usuarios", "➕ Crear Usuario", "🔑 Cambiar Clave", "🗑️ Eliminar Usuario"])
        
        with tab_u1:
            conn = conectar_db()
            try:
                df_u = pd.read_sql_query("SELECT id, nombre AS Usuario, rol AS Rol FROM usuarios", conn)
            finally:
                conn.close()
            st.dataframe(df_u, use_container_width=True, hide_index=True)
            
        with tab_u2:
            st.subheader("➕ Registrar Nuevo Usuario")
            with st.form("form_u", clear_on_submit=True):
                n_usr = st.text_input("Nombre de Usuario")
                c_usr = st.text_input("Contraseña", type="password")
                r_usr = st.selectbox("Rol de Acceso", ["Cajero", "Admin", "SuperAdmin"])
                
                if st.form_submit_button("Crear Usuario", type="primary"):
                    if n_usr.strip() and c_usr.strip():
                        try:
                            ejecutar_sql(
                                "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", 
                                (n_usr.strip(), hash_clave(c_usr.strip()), r_usr)
                            )
                            st.success(f"✅ Usuario **{n_usr.strip()}** creado exitosamente.")
                            st.rerun()
                        except Exception:
                            st.error("❌ El nombre de usuario ya existe o ocurrió un problema con la base de datos.")
                    else:
                        st.warning("Debe ingresar un nombre de usuario y contraseña válidos.")

        with tab_u3:
            st.subheader("🔑 Cambiar Contraseña")
            conn = conectar_db()
            try:
                usrs_df = pd.read_sql_query("SELECT id, nombre FROM usuarios", conn)
            finally:
                conn.close()
            
            if not usrs_df.empty:
                with st.form("form_cambiar_clave", clear_on_submit=True):
                    usr_sel_clave = st.selectbox("Seleccionar Usuario", usrs_df['nombre'].tolist())
                    nueva_clave = st.text_input("Nueva Contraseña", type="password")
                    
                    if st.form_submit_button("Actualizar Contraseña", type="primary"):
                        if nueva_clave.strip():
                            clave_encriptada = hash_clave(nueva_clave.strip())
                            ejecutar_sql(
                                "UPDATE usuarios SET clave = ? WHERE nombre = ?", 
                                (clave_encriptada, usr_sel_clave.strip())
                            )
                            st.success(f"✅ Contraseña del usuario **{usr_sel_clave}** actualizada.")
                        else:
                            st.warning("Ingrese una contraseña válida (no puede estar vacía).")

        with tab_u4:
            st.subheader("🗑️ Eliminar Usuario")
            conn = conectar_db()
            try:
                usrs_df_del = pd.read_sql_query("SELECT id, nombre, rol FROM usuarios", conn)
            finally:
                conn.close()
            
            if not usrs_df_del.empty:
                usrs_filtrados = usrs_df_del[usrs_df_del['nombre'] != st.session_state.usuario]
                if st.session_state.rol == "Admin":
                    usrs_filtrados = usrs_filtrados[usrs_filtrados['rol'] != "SuperAdmin"]
                
                if usrs_filtrados.empty:
                    st.info("No hay otros usuarios disponibles que pueda eliminar.")
                else:
                    usr_sel_del = st.selectbox("Seleccionar Usuario a Eliminar", usrs_filtrados['nombre'].tolist(), key="sel_usr_del")
                    st.warning(f"⚠️ **Atención:** Esta acción borrará permanentemente al usuario **{usr_sel_del}**.")
                    
                    if st.button("🗑️ Eliminar Usuario Definitivamente", type="primary", key="btn_del_usr"):
                        ejecutar_sql("DELETE FROM usuarios WHERE nombre = ?", (usr_sel_del,))
                        st.success(f"✅ Usuario **{usr_sel_del}** eliminado.")
                        st.rerun()
