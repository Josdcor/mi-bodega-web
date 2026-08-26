import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date

# Intento de importación del módulo personalizado de calculadora si existe en el proyecto
try:
    import calculadora
except ImportError:
    calculadora = None

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Mi Bodega Pro", page_icon="🏪", layout="wide")

# --- CONEXIÓN Y CREACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect("bodega.db", check_same_thread=False)

def init_db():
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_usd REAL NOT NULL,
            stock_actual REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_factura TEXT,
            producto_id INTEGER,
            cliente_id INTEGER,
            cantidad REAL,
            total_usd REAL,
            total_bs REAL,
            metodo_pago TEXT,
            fecha TEXT,
            responsable TEXT,
            estado TEXT DEFAULT 'Activa'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS abonos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            monto_usd REAL,
            monto_bs REAL,
            metodo_pago TEXT,
            fecha TEXT,
            responsable TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT,
            monto REAL,
            moneda TEXT,
            fecha TEXT,
            responsable TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            tipo TEXT,
            cantidad REAL,
            fecha TEXT,
            responsable TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)
    
    # Crear usuario administrador por defecto si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)", ("admin", "1234", "SuperAdmin"))
        
    conn.commit()

init_db()

# --- ESTADO DE SESIÓN (LOGIN Y AUTENTICACIÓN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = ""
if "rol_actual" not in st.session_state:
    st.session_state["rol_actual"] = ""

# --- PANTALLA DE INICIO DE SESIÓN ---
if not st.session_state["autenticado"]:
    st.title("🏪 Mi Bodega Pro")
    st.subheader("🔑 Iniciar Sesión")
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("form_login"):
            usr_input = st.text_input("Usuario")
            pwd_input = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("🔓 Ingresar", use_container_width=True)
            
            if btn_login:
                cursor = conn.cursor()
                cursor.execute("SELECT nombre, rol FROM usuarios WHERE nombre = ? AND clave = ?", (usr_input.strip(), pwd_input.strip()))
                user_record = cursor.fetchone()
                
                if user_record:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = user_record[0]
                    st.session_state["rol_actual"] = user_record[1]
                    st.success(f"Bienvenido {user_record[0]} ({user_record[1]})")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
    st.stop()  # Detiene la ejecución del resto del script hasta autenticarse

# --- DATOS DE SESIÓN Y SIDEBAR ---
usuario_actual = st.session_state["usuario_actual"]
rol_actual = st.session_state["rol_actual"]

st.sidebar.title("🏪 Mi Bodega Pro")
st.sidebar.caption(f"👤 Usuario: **{usuario_actual}** ({rol_actual})")

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = ""
    st.session_state["rol_actual"] = ""
    st.rerun()

st.sidebar.divider()
tasa = st.sidebar.number_input("Tasa de Cambio (Bs./$):", min_value=1.0, value=36.5, step=0.1)

# Opciones del menú según el rol
if rol_actual == "SuperAdmin":
    menu_opciones = [
        "🛒 Nueva Venta",
        "📦 Inventario / Productos",
        "👥 Clientes",
        "💰 Abonos",
        "🔒 Cierre de Caja",
        "🚫 Anulación de Ventas",
        "📊 Dashboard",
        "🧮 Calculadora",
        "💸 Gastos / Caja Chica",
        "📜 Historial y Transacciones",
        "⚙️ Gestión de Usuarios"
    ]
else:  # Rol Vendedor
    menu_opciones = [
        "🛒 Nueva Venta",
        "📦 Inventario / Productos",
        "👥 Clientes",
        "💰 Abonos",
        "🧮 Calculadora",
        "💸 Gastos / Caja Chica"
    ]

menu = st.sidebar.selectbox("Menú Principal", menu_opciones)

# =========================================================
# 1. NUEVA VENTA
# =========================================================
if menu == "🛒 Nueva Venta":
    st.title("🛒 Registrar Nueva Venta")
    df_p = pd.read_sql_query("SELECT id, nombre, precio_usd, stock_actual FROM productos WHERE stock_actual > 0", conn)
    
    if df_p.empty:
        st.warning("No hay productos registrados o disponibles en inventario.")
    else:
        with st.form("form_venta"):
            col1, col2 = st.columns(2)
            with col1:
                dict_p = {row['nombre']: row['id'] for _, row in df_p.iterrows()}
                p_sel = st.selectbox("Producto:", list(dict_p.keys()))
                prod_id = dict_p[p_sel]
                info_p = df_p[df_p['id'] == prod_id].iloc[0]
                
                cant = st.number_input("Cantidad:", min_value=0.01, value=1.0, max_value=float(info_p['stock_actual']))
            
            with col2:
                df_c = pd.read_sql_query("SELECT id, nombre FROM clientes", conn)
                dict_c = {"Cliente General": None}
                if not df_c.empty:
                    dict_c.update({row['nombre']: row['id'] for _, row in df_c.iterrows()})
                c_sel = st.selectbox("Cliente:", list(dict_c.keys()))
                cli_id = dict_c[c_sel]
                
                metodo = st.selectbox("Método de Pago:", ["Efectivo $", "Pago Móvil / Bolívares", "Zelle", "Punto de Venta", "Crédito/Fiado"])

            tot_usd = float(info_p['precio_usd']) * cant
            tot_bs = tot_usd * tasa
            st.info(f"Total a Pagar: **${tot_usd:,.2f}** | **{tot_bs:,.2f} Bs.**")

            if st.form_submit_button("🛒 Finalizar Venta"):
                cursor = conn.cursor()
                num_fac = f"FAC-{int(datetime.now().timestamp())}"
                fecha_now = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                cursor.execute("""
                    INSERT INTO ventas (num_factura, producto_id, cliente_id, cantidad, total_usd, total_bs, metodo_pago, fecha, responsable, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Activa')
                """, (num_fac, prod_id, cli_id, cant, tot_usd, tot_bs, metodo, fecha_now, usuario_actual))
                
                cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?", (cant, prod_id))
                cursor.execute("""
                    INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                    VALUES (?, 'Venta Directa', ?, ?, ?)
                """, (prod_id, cant, fecha_now, usuario_actual))
                
                conn.commit()
                st.success(f"Venta registrada con éxito. Factura: {num_fac}")
                st.rerun()

# =========================================================
# 2. INVENTARIO / PRODUCTOS
# =========================================================
elif menu == "📦 Inventario / Productos":
    st.title("📦 Gestión de Productos e Inventario")
    
    with st.expander("➕ Registrar Nuevo Producto"):
        with st.form("form_prod"):
            nom_p = st.text_input("Nombre del Producto")
            p_usd = st.number_input("Precio ($)", min_value=0.01, value=1.0)
            stk_p = st.number_input("Stock Inicial", min_value=0.0, value=10.0)
            if st.form_submit_button("Guardar Producto"):
                if nom_p.strip():
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO productos (nombre, precio_usd, stock_actual) VALUES (?, ?, ?)", (nom_p.strip(), p_usd, stk_p))
                    conn.commit()
                    st.success("Producto agregado con éxito.")
                    st.rerun()
                else:
                    st.warning("Ingrese un nombre válido.")

    st.subheader("Inventario Actual")
    df_prods = pd.read_sql_query("SELECT id, nombre, precio_usd, stock_actual FROM productos", conn)
    if not df_prods.empty:
        df_prods['precio_bs'] = df_prods['precio_usd'] * tasa
        st.dataframe(df_prods, use_container_width=True)
    else:
        st.info("No hay productos en el inventario.")

# =========================================================
# 3. CLIENTES
# =========================================================
elif menu == "👥 Clientes":
    st.title("👥 Gestión de Clientes")
    with st.form("form_cliente"):
        c_nom = st.text_input("Nombre / Razón Social")
        c_tel = st.text_input("Teléfono / Contacto")
        if st.form_submit_button("Guardar Cliente"):
            if c_nom.strip():
                cursor = conn.cursor()
                cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (?, ?)", (c_nom.strip(), c_tel.strip()))
                conn.commit()
                st.success("Cliente guardado exitosamente.")
                st.rerun()
            else:
                st.warning("Escriba el nombre del cliente.")

    st.subheader("Lista de Clientes")
    df_clis = pd.read_sql_query("SELECT * FROM clientes", conn)
    st.dataframe(df_clis, use_container_width=True)

# =========================================================
# 4. ABONOS
# =========================================================
elif menu == "💰 Abonos":
    st.title("💰 Registrar Abonos a Deudas")
    df_cli = pd.read_sql_query("SELECT id, nombre FROM clientes", conn)
    if df_cli.empty:
        st.info("No hay clientes registrados.")
    else:
        dict_cli = {row['nombre']: row['id'] for _, row in df_cli.iterrows()}
        cli_sel = st.selectbox("Seleccionar Cliente:", list(dict_cli.keys()))
        c_id_sel = dict_cli[cli_sel]

        v_usd = pd.read_sql_query("SELECT SUM(total_usd) as t FROM ventas WHERE cliente_id = ? AND metodo_pago = 'Crédito/Fiado' AND estado != 'Anulada'", conn, params=[c_id_sel])['t'].iloc[0] or 0.0
        a_usd = pd.read_sql_query("SELECT SUM(monto_usd) as t FROM abonos WHERE cliente_id = ?", conn, params=[c_id_sel])['t'].iloc[0] or 0.0
        deuda_actual = v_usd - a_usd

        if deuda_actual <= 0:
            st.info("El cliente no posee deudas pendientes.")
        else:
            st.warning(f"Deuda Pendiente Actual: **${deuda_actual:,.2f}** ({deuda_actual * tasa:,.2f} Bs.)")
            
            with st.form("form_abono"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    moneda_abono = st.selectbox("Moneda recibida:", ["USD ($)", "Bolívares (Bs.)"])
                    max_monto_sugerido = float(deuda_actual) if moneda_abono == "USD ($)" else float(deuda_actual * tasa)
                    monto_abono = st.number_input("Monto a Abonar:", 
                                                  min_value=0.01, 
                                                  value=max_monto_sugerido)
                with col_a2:
                    metodo_abono = st.selectbox("Método de Pago:", ["Efectivo $", "Pago Móvil / Bolívares", "Zelle", "Punto de Venta"])
                
                if st.form_submit_button("💵 Procesar Abono"):
                    monto_usd_final = monto_abono if moneda_abono == "USD ($)" else monto_abono / tasa
                    monto_bs_final = monto_abono * tasa if moneda_abono == "USD ($)" else monto_abono
                    
                    if monto_usd_final > (deuda_actual + 0.01):
                        st.error(f"El monto ingresado (${monto_usd_final:,.2f}) supera la deuda actual (${deuda_actual:,.2f}).")
                    else:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO abonos (cliente_id, monto_usd, monto_bs, metodo_pago, fecha, responsable) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (c_id_sel, monto_usd_final, monto_bs_final, metodo_abono, datetime.now().strftime("%Y-%m-%d %H:%M"), usuario_actual))
                        conn.commit()
                        st.success("✅ Abono asentado correctamente.")
                        st.rerun()

# =========================================================
# 5. CIERRE DE CAJA
# =========================================================
elif menu == "🔒 Cierre de Caja":
    st.title("🔒 Cierre de Caja y Arqueo de Turno")
    
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        fecha_cierre = st.date_input("Seleccionar Fecha", value=date.today()).strftime("%Y-%m-%d")
    with col_f2:
        df_usuarios = pd.read_sql_query("SELECT DISTINCT responsable FROM ventas", conn)
        lista_cajeros = ["Todos"] + (df_usuarios['responsable'].tolist() if not df_usuarios.empty else [])
        cajero_sel = st.selectbox("Filtrar por Cajero/Usuario:", lista_cajeros)
    
    query_v = """
        SELECT v.id, p.nombre as producto, v.cantidad, v.total_usd, v.total_bs, v.metodo_pago, v.fecha, v.responsable 
        FROM ventas v 
        JOIN productos p ON v.producto_id = p.id 
        WHERE v.fecha LIKE ? AND v.estado != 'Anulada'
    """
    params_v = [f"{fecha_cierre}%"]
    
    if cajero_sel != "Todos":
        query_v += " AND v.responsable = ?"
        params_v.append(cajero_sel)
        
    df_v = pd.read_sql_query(query_v, conn, params=params_v)
    
    query_a = "SELECT monto_usd, monto_bs, metodo_pago, responsable FROM abonos WHERE fecha LIKE ?"
    params_a = [f"{fecha_cierre}%"]
    if cajero_sel != "Todos":
        query_a += " AND responsable = ?"
        params_a.append(cajero_sel)
    df_abonos_dia = pd.read_sql_query(query_a, conn, params=params_a)

    df_gastos_dia = pd.read_sql_query("SELECT monto, moneda FROM gastos WHERE fecha LIKE ?", conn, params=[f"{fecha_cierre}%"])
    gastos_usd = df_gastos_dia[df_gastos_dia['moneda'] == 'USD']['monto'].sum() if not df_gastos_dia.empty else 0.0

    tot_ventas_usd = df_v['total_usd'].sum() if not df_v.empty else 0.0
    tot_abonos_usd = df_abonos_dia['monto_usd'].sum() if not df_abonos_dia.empty else 0.0
    ingresos_totales = tot_ventas_usd + tot_abonos_usd

    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    c_m1.metric("Ventas Directas ($)", f"${tot_ventas_usd:,.2f}")
    c_m2.metric("Cobro Deudas/Abonos ($)", f"${tot_abonos_usd:,.2f}")
    c_m3.metric("Gastos Totales ($)", f"${gastos_usd:,.2f}")
    c_m4.metric("Balance Neto ($)", f"${(ingresos_totales - gastos_usd):,.2f}")
    
    if df_v.empty and df_abonos_dia.empty:
        st.info("No se registraron ventas ni abonos para la fecha seleccionada.")
    else:
        st.subheader("Desglose de Ventas por Método de Pago")
        if not df_v.empty:
            df_metodos = df_v.groupby('metodo_pago')[['total_usd', 'total_bs']].sum().reset_index()
            st.dataframe(df_metodos, use_container_width=True)
        
        with st.expander("Ver Detalle de Ventas del Día"):
            st.dataframe(df_v, use_container_width=True)

        if not df_abonos_dia.empty:
            with st.expander("Ver Detalle de Abonos/Cobros de Deuda del Día"):
                st.dataframe(df_abonos_dia, use_container_width=True)

# =========================================================
# 6. ANULACIÓN DE VENTAS CON REINTEGRO DE STOCK
# =========================================================
elif menu == "🚫 Anulación de Ventas":
    st.title("🚫 Anulación de Ventas con Reintegro de Stock")

    try:
        df_ventas_activas = pd.read_sql_query("""
            SELECT MAX(id) as id, num_factura, fecha, responsable, cliente_id, SUM(total_usd) as total_usd, SUM(total_bs) as total_bs
            FROM ventas 
            WHERE estado != 'Anulada'
            GROUP BY num_factura, fecha, responsable, cliente_id
            ORDER BY id DESC
        """, conn)

        if not df_ventas_activas.empty:
            opciones_facturas = []
            for _, r in df_ventas_activas.iterrows():
                fac_code = r['num_factura'] if r['num_factura'] else f"ID-{r['id']}"
                opciones_facturas.append(f"{fac_code} | Fecha: {r['fecha']} | Total: ${r['total_usd']:.2f} | Cajero: {r['responsable']}")
            
            venta_sel_label = st.selectbox("Selecciona la transacción a anular:", opciones_facturas)
            num_fac_sel = venta_sel_label.split(" | ")[0]

            df_detalles = pd.read_sql_query("""
                SELECT v.id as venta_id, p.id as producto_id, p.nombre as producto, v.cantidad, v.total_usd, v.total_bs
                FROM ventas v
                JOIN productos p ON v.producto_id = p.id
                WHERE (v.num_factura = ? OR ('ID-' || v.id) = ?) AND v.estado != 'Anulada'
            """, conn, params=[num_fac_sel, num_fac_sel])

            st.write("**Productos incluidos en esta transacción:**")
            st.dataframe(df_detalles[["producto", "cantidad", "total_usd", "total_bs"]], use_container_width=True)

            st.warning("⚠️ Al confirmar la anulación, el estado de la venta cambiará a 'Anulada' y el stock se reintegrará automáticamente al inventario.")

            if st.button("❌ Confirmar Anulación y Reintegrar Stock", type="primary"):
                try:
                    cursor = conn.cursor()

                    for _, item in df_detalles.iterrows():
                        prod_id = item['producto_id']
                        cant = item['cantidad']
                        cursor.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (cant, prod_id))
                        cursor.execute("""
                            INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                            VALUES (?, 'Anulación Venta', ?, ?, ?)
                        """, (prod_id, cant, datetime.now().strftime("%Y-%m-%d %H:%M"), usuario_actual))

                    cursor.execute("UPDATE ventas SET estado = 'Anulada' WHERE num_factura = ? OR ('ID-' || id) = ?", (num_fac_sel, num_fac_sel))
                    
                    conn.commit()
                    st.success(f"La transacción {num_fac_sel} ha sido anulada exitosamente y los productos volvieron al inventario.")
                    st.rerun()

                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al procesar la anulación: {e}")
        else:
            st.info("No hay ventas activas disponibles para anular.")

    except Exception as e:
        st.error(f"Error al consultar el historial de ventas: {e}")

# =========================================================
# 7. DASHBOARD (Solo Admin / Master)
# =========================================================
elif menu == "📊 Dashboard":
    st.title("📊 Dashboard y Analíticas")
    df_v_all = pd.read_sql_query("SELECT total_usd, fecha, metodo_pago FROM ventas WHERE estado != 'Anulada'", conn)
    if df_v_all.empty:
        st.info("Aún no hay suficientes ventas registradas para mostrar métricas.")
    else:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.subheader("Ventas por Método de Pago")
            st.bar_chart(df_v_all.groupby("metodo_pago")["total_usd"].sum())
        with col_d2:
            st.subheader("Resumen Total ($)")
            st.metric("Ingresos Históricos Totales", f"${df_v_all['total_usd'].sum():,.2f}")

# =========================================================
# 8. CALCULADORA
# =========================================================
elif menu == "🧮 Calculadora":
    st.title("🧮 Calculadora de Precios y Conversión")
    if calculadora and hasattr(calculadora, 'mostrar'):
        calculadora.mostrar(tasa)
    else:
        st.subheader("Conversor Rápido de Moneda")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            val_usd = st.number_input("Monto en USD ($):", min_value=0.0, value=1.0, step=1.0)
            st.write(f"Equivale a: **{val_usd * tasa:,.2f} Bs.**")
        with col_c2:
            val_bs = st.number_input("Monto en Bolívares (Bs.):", min_value=0.0, value=tasa, step=10.0)
            st.write(f"Equivale a: **${val_bs / tasa:,.2f} USD**")

# =========================================================
# 9. GASTOS / CAJA CHICA
# =========================================================
elif menu == "💸 Gastos / Caja Chica":
    st.title("💸 Registro de Gastos / Caja Chica")
    
    with st.form("form_gastos"):
        desc = st.text_input("Descripción del Gasto")
        monto_g = st.number_input("Monto", min_value=0.01, value=5.0)
        moneda_g = st.selectbox("Moneda", ["USD", "Bs"])
        if st.form_submit_button("💾 Registrar Gasto"):
            if desc.strip():
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO gastos (descripcion, monto, moneda, fecha, responsable) 
                    VALUES (?, ?, ?, ?, ?)
                """, (desc.strip(), monto_g, moneda_g, datetime.now().strftime("%Y-%m-%d %H:%M"), usuario_actual))
                conn.commit()
                st.success("Gasto asentado correctamente.")
                st.rerun()
            else:
                st.warning("Ingrese una descripción.")
                
    st.subheader("Historial Reciente de Gastos")
    df_g = pd.read_sql_query("SELECT id, descripcion, monto, moneda, fecha, responsable FROM gastos ORDER BY id DESC LIMIT 20", conn)
    st.dataframe(df_g, use_container_width=True)

# =========================================================
# 10. HISTORIAL Y TRANSACCIONES
# =========================================================
elif menu == "📜 Historial y Transacciones":
    st.title("📜 Historial de Ventas y Movimientos")
    tab_h_ventas, tab_h_movs = st.tabs(["🛒 Historial Ventas", "📦 Movimientos de Inventario"])
    
    with tab_h_ventas:
        df_hv = pd.read_sql_query("""
            SELECT v.id, v.num_factura, p.nombre as producto, v.cantidad, v.total_usd, v.total_bs, v.metodo_pago, v.fecha, v.responsable, v.estado
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            ORDER BY v.id DESC LIMIT 100
        """, conn)
        st.dataframe(df_hv, use_container_width=True)
        
    with tab_h_movs:
        df_hm = pd.read_sql_query("""
            SELECT m.id, p.nombre as producto, m.tipo, m.cantidad, m.fecha, m.responsable
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            ORDER BY m.id DESC LIMIT 100
        """, conn)
        st.dataframe(df_hm, use_container_width=True)

# =========================================================
# 11. GESTIÓN DE USUARIOS (Solo SuperAdmin)
# =========================================================
elif menu == "⚙️ Gestión de Usuarios":
    st.title("⚙️ Gestión de Usuarios del Sistema")
    
    tab_crear, tab_modificar, tab_listar = st.tabs([
        "➕ Crear Usuario", 
        "✏️ Modificar / Cambio de Clave", 
        "📋 Lista de Usuarios"
    ])

    # --- CREAR USUARIO ---
    with tab_crear:
        with st.form("form_crear_usuario", clear_on_submit=True):
            u_nom = st.text_input("Nombre de Usuario")
            u_pass = st.text_input("Contraseña", type="password")
            u_rol = st.selectbox("Rol de Acceso:", ["Vendedor", "SuperAdmin"])
            btn_crear = st.form_submit_button("👤 Crear Usuario")

            if btn_crear:
                if u_nom.strip() and u_pass.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)",
                            (u_nom.strip(), u_pass.strip(), u_rol)
                        )
                        conn.commit()
                        st.success(f"Usuario '{u_nom}' creado correctamente.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("El nombre de usuario ya se encuentra registrado.")
                    except Exception as e:
                        st.error(f"Error al registrar usuario: {e}")
                else:
                    st.warning("Por favor completa tanto el usuario como la contraseña.")

    # --- MODIFICAR USUARIO / CAMBIAR CLAVE ---
    with tab_modificar:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre, rol FROM usuarios")
            usuarios = cursor.fetchall()

            if usuarios:
                dict_usuarios = {f"{u[1]} (ID: {u[0]} - Rol: {u[2]})": u[0] for u in usuarios}
                user_sel = st.selectbox("Selecciona el usuario a modificar:", list(dict_usuarios.keys()))
                user_id = dict_usuarios[user_sel]

                with st.form("form_modificar_usuario"):
                    nueva_clave = st.text_input("Nueva Contraseña (dejar en blanco para no cambiar)", type="password")
                    nuevo_rol = st.selectbox("Nuevo Rol de Acceso:", ["Vendedor", "SuperAdmin"])
                    btn_modificar = st.form_submit_button("✏️ Actualizar Usuario")

                    if btn_modificar:
                        try:
                            cursor = conn.cursor()
                            if nueva_clave.strip():
                                cursor.execute(
                                    "UPDATE usuarios SET clave = ?, rol = ? WHERE id = ?",
                                    (nueva_clave.strip(), nuevo_rol, user_id)
                                )
                            else:
                                cursor.execute(
                                    "UPDATE usuarios SET rol = ? WHERE id = ?",
                                    (nuevo_rol, user_id)
                                )
                            conn.commit()
                            st.success("Datos de usuario actualizados correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
            else:
                st.info("No hay usuarios registrados en el sistema.")
        except Exception as e:
            st.error(f"Error al cargar la lista de usuarios: {e}")

    # --- LISTAR USUARIOS ---
    with tab_listar:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre, rol FROM usuarios")
            data = cursor.fetchall()

            if data:
                df_u = pd.DataFrame(data, columns=["ID", "Nombre de Usuario", "Rol"])
                st.dataframe(df_u, use_container_width=True)
            else:
                st.info("La tabla de usuarios está vacía.")
        except Exception as e:
            st.error(f"Error al consultar usuarios: {e}")
