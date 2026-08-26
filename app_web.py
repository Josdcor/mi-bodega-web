import asyncio
import io
import os
import sqlite3
import sys
import urllib.parse
from datetime import date, datetime

import pandas as pd
import requests
import streamlit as st

# --- 1. CONFIGURACIÓN DE ENTORNO ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Mi Bodega Pro - Gestión Total", layout="wide", page_icon="🚀"
)


# --- 2. BASE DE DATOS E INICIALIZACIÓN ---
def conectar_db():
    return sqlite3.connect("bodega.db", check_same_thread=False)


def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS usuarios 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rol TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS productos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, nombre TEXT, categoria TEXT, precio REAL DEFAULT 0.0, costo REAL DEFAULT 0.0, stock_actual REAL DEFAULT 0.0, stock_minimo REAL DEFAULT 0.0, precio_venta REAL DEFAULT 0.0)""")

    # Migraciones automáticas de estructura
    cursor.execute("PRAGMA table_info(productos)")
    cols_prod = [col[1] for col in cursor.fetchall()]
    if "precio_venta" not in cols_prod:
        cursor.execute(
            "ALTER TABLE productos ADD COLUMN precio_venta REAL DEFAULT 0.0"
        )
    if "precio" not in cols_prod:
        cursor.execute(
            "ALTER TABLE productos ADD COLUMN precio REAL DEFAULT 0.0"
        )

    cursor.execute(
        "UPDATE productos SET precio_venta = precio WHERE (precio_venta IS NULL OR precio_venta = 0) AND precio > 0"
    )
    cursor.execute(
        "UPDATE productos SET precio = precio_venta WHERE (precio IS NULL OR precio = 0) AND precio_venta > 0"
    )

    cursor.execute("""CREATE TABLE IF NOT EXISTS movimientos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, tipo TEXT, cantidad REAL, fecha TEXT, responsable TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS gastos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, descripcion TEXT, monto REAL, fecha TEXT, moneda TEXT DEFAULT 'USD', responsable TEXT DEFAULT 'Admin')""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS cierres_caja 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, responsable TEXT, total_usd REAL, total_bs REAL, diferencia_usd REAL, diferencia_bs REAL, estado TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS clientes 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, telefono TEXT, limite_credito REAL DEFAULT 0.0)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS abonos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, monto_usd REAL, monto_bs REAL, metodo_pago TEXT, fecha TEXT, responsable TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS ventas 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, cantidad REAL, total_usd REAL, total_bs REAL, metodo_pago TEXT, fecha TEXT, responsable TEXT, cliente_id INTEGER DEFAULT NULL, num_factura TEXT DEFAULT NULL, estado TEXT DEFAULT 'Completada')""")

    # Usuarios base
    cursor.execute("SELECT * FROM usuarios WHERE nombre=?", ("Master",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)",
            ("Master", "admin99", "SuperAdmin"),
        )

    cursor.execute("SELECT * FROM usuarios WHERE nombre=?", ("Vendedor",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)",
            ("Vendedor", "vendedor123", "Vendedor"),
        )

    conn.commit()
    conn.close()


inicializar_db()
conn = conectar_db()


# --- 3. FUNCIONES AUXILIARES ---
def guardar_producto(
    codigo, nombre, categoria, precio, costo, stock_actual, stock_minimo
):
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO productos (codigo, nombre, categoria, precio, precio_venta, costo, stock_actual, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                codigo,
                nombre,
                categoria,
                precio,
                precio,
                costo,
                stock_actual,
                stock_minimo,
            ),
        )
        conn.commit()
        return True, f"✅ '{nombre}' guardado exitosamente."
    except sqlite3.IntegrityError:
        return False, "❌ El código de producto ya existe."
    except Exception as e:
        return False, f"❌ Error: {e}"


def actualizar_producto(
    id_prod, nombre, categoria, precio, costo, stock_actual, stock_minimo
):
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE productos 
            SET nombre=?, categoria=?, precio=?, precio_venta=?, costo=?, stock_actual=?, stock_minimo=?
            WHERE id=?
        """,
            (
                nombre,
                categoria,
                precio,
                precio,
                costo,
                stock_actual,
                stock_minimo,
                id_prod,
            ),
        )
        conn.commit()
        return True, "✅ Producto actualizado correctamente."
    except Exception as e:
        return False, f"❌ Error: {e}"


def exportar_a_excel(df, nombre_hoja="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return output.getvalue()


def generar_texto_ticket(
    num_factura, fecha, cliente_nombre, responsable, items, metodo_pago, tasa_bcv
):
    texto = "================================\n"
    texto += "         MI BODEGA PRO          \n"
    texto += "     COMPROBANTE DE VENTA       \n"
    texto += "================================\n"
    texto += f"Ticket #: {num_factura}\n"
    texto += f"Fecha: {fecha}\n"
    texto += f"Cliente: {cliente_nombre}\n"
    texto += f"Cajero: {responsable}\n"
    texto += f"Tasa Usada: {tasa_bcv:.2f} Bs./$\n"
    texto += "--------------------------------\n"
    texto += "CANT  PRODUCTO        SUBTOTAL   \n"
    texto += "--------------------------------\n"

    tot_usd = 0.0
    tot_bs = 0.0
    for it in items:
        tot_usd += it["subtotal_usd"]
        tot_bs += it["subtotal_bs"]
        nom = (it["nombre"][:15]).ljust(15)
        texto += f"{it['cantidad']:<4}  {nom}  ${it['subtotal_usd']:>6.2f}\n"

    texto += "--------------------------------\n"
    texto += f"TOTAL USD: ${tot_usd:,.2f}\n"
    texto += f"TOTAL BS:  {tot_bs:,.2f} Bs.\n"
    texto += f"Metodo Pago: {metodo_pago}\n"
    texto += "================================\n"
    texto += "   ¡Gracias por su preferencia! \n"
    texto += "================================\n"
    return texto


@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get(
            "https://ve.dolarapi.com/v1/dolares/oficial", timeout=5
        )
        return float(response.json()["promedio"])
    except:
        return 43.50


tasa_oficial = obtener_tasa_bcv()

# --- 4. ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "carrito" not in st.session_state:
    st.session_state["carrito"] = []
if "ultimo_ticket" not in st.session_state:
    st.session_state["ultimo_ticket"] = None
if "tasa_manual_activa" not in st.session_state:
    st.session_state["tasa_manual_activa"] = False
if "tasa_personalizada" not in st.session_state:
    st.session_state["tasa_personalizada"] = tasa_oficial


def login():
    st.title("🛡️ Acceso Seguro - Mi Bodega Pro")
    col_l1, col_l2 = st.columns([1, 1])
    with col_l1:
        with st.form("login_form"):
            u = st.text_input("Usuario")
            c = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar al Sistema"):
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT rol FROM usuarios WHERE nombre=? AND clave=?", (u, c)
                )
                resultado = cursor.fetchone()
                if resultado:
                    st.session_state.update(
                        {
                            "autenticado": True,
                            "usuario_nombre": u,
                            "rol": resultado[0],
                        }
                    )
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")


if not st.session_state["autenticado"]:
    login()
else:
    usuario_actual = st.session_state.get("usuario_nombre", "")
    rol_actual = st.session_state.get("rol", "")

    st.sidebar.title("📦 Mi Bodega Pro")
    st.sidebar.write(f"👤 **Usuario:** `{usuario_actual}` ({rol_actual})")

    # --- CONTROL DE TASA Y RESPALDO EN SIDEBAR ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("💱 Configuración de Tasa")
    usar_manual = st.sidebar.toggle(
        "Habilitar Tasa Manual", value=st.session_state["tasa_manual_activa"]
    )
    st.session_state["tasa_manual_activa"] = usar_manual

    if usar_manual:
        tasa = st.sidebar.number_input(
            "Tasa Personalizada (Bs./$):",
            min_value=1.0,
            value=float(st.session_state["tasa_personalizada"]),
            step=0.5,
            format="%.2f",
        )
        st.session_state["tasa_personalizada"] = tasa
        st.sidebar.warning(f"⚠️ Usando tasa manual: **{tasa:.2f} Bs./$**")
    else:
        tasa = tasa_oficial
        st.sidebar.info(f"Tasa Oficial BCV: **{tasa:.2f} Bs./$**")

    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Copia de Seguridad")
    if os.path.exists("bodega.db"):
        with open("bodega.db", "rb") as f:
            bytes_db = f.read()
        st.sidebar.download_button(
            label="📥 Descargar Respaldo (.db)",
            data=bytes_db,
            file_name=f"bodega_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            mime="application/x-sqlite3",
            use_container_width=True,
            key="btn_backup_db",
        )

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["carrito"] = []
        st.rerun()

    # Alertas de stock
    df_alertas = pd.read_sql_query(
        "SELECT nombre, stock_actual, stock_minimo FROM productos WHERE stock_actual <= stock_minimo",
        conn,
    )
    if not df_alertas.empty:
        st.sidebar.warning(
            f"⚠️ **{len(df_alertas)} producto(s) en stock bajo!**"
        )
        with st.sidebar.expander("Ver lista"):
            for _, row in df_alertas.iterrows():
                st.write(f"• **{row['nombre']}**: {row['stock_actual']} un.")

    # --- NAVEGACIÓN ---
    modulos_base = [
        "🛒 Módulo de Ventas (POS)",
        "📋 Ver Inventario",
        "🤝 Fiados / Cuentas por Cobrar",
        "🔒 Cierre de Caja",
        "🚫 Anulación de Ventas",
        "🧮 Calculadora",
        "💸 Gastos / Caja Chica",
        "📜 Historial y Transacciones",
    ]

    if rol_actual in ["SuperAdmin", "Master"]:
        menu = st.sidebar.radio(
            "Navegación:",
            [
                "🛒 Módulo de Ventas (POS)",
                "📋 Ver Inventario",
                "📦 Cargar por Bulto",
                "✏️ Editar / Ajustar Producto",
                "🤝 Fiados / Cuentas por Cobrar",
                "🔒 Cierre de Caja",
                "🚫 Anulación de Ventas",
                "📊 Dashboard",
                "🧮 Calculadora",
                "💸 Gastos / Caja Chica",
                "📜 Historial y Transacciones",
                "👥 Gestión de Usuarios",
            ],
        )
    else:
        menu = st.sidebar.radio("Navegación:", modulos_base)

    # =========================================================
    # 1. MÓDULO DE VENTAS (POS)
    # =========================================================
    if menu == "🛒 Módulo de Ventas (POS)":
        st.title("🛒 Punto de Venta / Carrito de Compras")

        if st.session_state["ultimo_ticket"]:
            t_data = st.session_state["ultimo_ticket"]
            st.success("🎉 ¡Venta Procesada Exitosamente!")

            with st.expander(
                "🎟️ VER TICKET DE VENTA / NOTA DE ENTREGA", expanded=True
            ):
                col_t1, col_t2 = st.columns([1, 1])
                with col_t1:
                    texto_t = generar_texto_ticket(
                        t_data["num_factura"],
                        t_data["fecha"],
                        t_data["cliente"],
                        t_data["responsable"],
                        t_data["items"],
                        t_data["metodo_pago"],
                        t_data["tasa"],
                    )
                    st.code(texto_t, language="text")
                with col_t2:
                    st.markdown("### **Opciones de Recibo**")
                    st.download_button(
                        "📥 Descargar Ticket (.txt)",
                        data=texto_t,
                        file_name=f"Ticket_{t_data['num_factura']}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

                    texto_url = urllib.parse.quote(texto_t)
                    ws_url = (
                        f"https://api.whatsapp.com/send?text={texto_url}"
                    )
                    st.markdown(
                        f'<a href="{ws_url}" target="_blank" style="text-decoration:none;"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">📲 Enviar por WhatsApp</button></a>',
                        unsafe_allow_html=True,
                    )

                    st.write("")
                    if st.button(
                        "❌ Cerrar Recibo / Nueva Venta",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state["ultimo_ticket"] = None
                        st.rerun()
            st.divider()

        df_p = pd.read_sql_query(
            "SELECT id, codigo, nombre, COALESCE(precio_venta, precio, 0.0) as precio, stock_actual FROM productos WHERE stock_actual > 0",
            conn,
        )

        if df_p.empty:
            st.warning("No hay productos disponibles en inventario.")
        else:
            col_sel, col_car = st.columns([1.2, 1])

            with col_sel:
                st.subheader("1. Seleccionar Producto")
                opciones = [
                    f"{row['id']} - {row['nombre']} (${row['precio']:.2f} | Stock: {row['stock_actual']})"
                    for _, row in df_p.iterrows()
                ]
                prod_sel = st.selectbox("Buscar Producto:", opciones)
                id_p = int(prod_sel.split(" - ")[0])

                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, nombre, COALESCE(precio_venta, precio, 0.0), stock_actual FROM productos WHERE id=?",
                    (id_p,),
                )
                p_item = cursor.fetchone()

                cant = st.number_input(
                    "Cantidad:",
                    min_value=1.0,
                    max_value=float(p_item[3]),
                    value=1.0,
                    step=1.0,
                    key="pos_cant",
                )

                if st.button("➕ Agregar al Carrito", type="primary"):
                    sub_usd = p_item[2] * cant
                    st.session_state["carrito"].append(
                        {
                            "id": p_item[0],
                            "nombre": p_item[1],
                            "precio": p_item[2],
                            "cantidad": cant,
                            "subtotal_usd": sub_usd,
                            "subtotal_bs": sub_usd * tasa,
                        }
                    )
                    st.success(f"Añadido: {p_item[1]} (x{cant})")
                    st.rerun()

            with col_car:
                st.subheader("🛒 Carrito Actual")
                if len(st.session_state["carrito"]) == 0:
                    st.info("El carrito está vacío.")
                else:
                    df_car = pd.DataFrame(st.session_state["carrito"])
                    st.dataframe(
                        df_car[
                            [
                                "nombre",
                                "cantidad",
                                "subtotal_usd",
                                "subtotal_bs",
                            ]
                        ],
                        use_container_width=True,
                    )

                    tot_usd = df_car["subtotal_usd"].sum()
                    tot_bs = df_car["subtotal_bs"].sum()

                    st.markdown(f"### **Total USD:** `${tot_usd:.2f}`")
                    st.markdown(
                        f"### **Total Bs:** `{tot_bs:,.2f} Bs.`"
                    )

                    metodo_pago = st.selectbox(
                        "Método de Pago:",
                        [
                            "Efectivo $",
                            "Pago Móvil / Bolívares",
                            "Zelle",
                            "Punto de Venta",
                            "Crédito / Fiado",
                        ],
                    )

                    cliente_id_venta = None
                    nombre_cliente_ticket = "Cliente General"
                    if metodo_pago == "Crédito / Fiado":
                        df_cli = pd.read_sql_query(
                            "SELECT id, nombre FROM clientes", conn
                        )
                        if df_cli.empty:
                            st.error(
                                "⚠️ No hay clientes registrados. Registre un cliente en el módulo 'Fiados'."
                            )
                        else:
                            cli_opts = [
                                f"{row['id']} - {row['nombre']}"
                                for _, row in df_cli.iterrows()
                            ]
                            cli_sel = st.selectbox(
                                "Seleccionar Cliente a Fiación:", cli_opts
                            )
                            cliente_id_venta = int(cli_sel.split(" - ")[0])
                            nombre_cliente_ticket = cli_sel.split(" - ")[1]

                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button(
                        "🔴 PROCESAR VENTA",
                        type="primary",
                        use_container_width=True,
                    ):
                        if (
                            metodo_pago == "Crédito / Fiado"
                            and not cliente_id_venta
                        ):
                            st.error(
                                "Seleccione un cliente para procesar la venta fiada."
                            )
                        else:
                            fecha_ahora = datetime.now().strftime(
                                "%Y-%m-%d %H:%M"
                            )
                            num_fac = f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            cursor = conn.cursor()

                            for item in st.session_state["carrito"]:
                                cursor.execute(
                                    "UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?",
                                    (item["cantidad"], item["id"]),
                                )
                                cursor.execute(
                                    "INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Venta', ?, ?, ?)",
                                    (
                                        item["id"],
                                        item["cantidad"],
                                        fecha_ahora,
                                        usuario_actual,
                                    ),
                                )
                                cursor.execute(
                                    "INSERT INTO ventas (producto_id, cantidad, total_usd, total_bs, metodo_pago, fecha, responsable, cliente_id, num_factura, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completada')",
                                    (
                                        item["id"],
                                        item["cantidad"],
                                        item["subtotal_usd"],
                                        item["subtotal_bs"],
                                        metodo_pago,
                                        fecha_ahora,
                                        usuario_actual,
                                        cliente_id_venta,
                                        num_fac,
                                    ),
                                )
                            conn.commit()

                            st.session_state["ultimo_ticket"] = {
                                "num_factura": num_fac,
                                "fecha": fecha_ahora,
                                "cliente": nombre_cliente_ticket,
                                "responsable": usuario_actual,
                                "metodo_pago": metodo_pago,
                                "tasa": tasa,
                                "items": list(st.session_state["carrito"]),
                            }
                            st.session_state["carrito"] = []
                            st.rerun()

                    if c_btn2.button(
                        "🗑️ Vaciar Carrito", use_container_width=True
                    ):
                        st.session_state["carrito"] = []
                        st.rerun()

    # =========================================================
    # 2. VER INVENTARIO
    # =========================================================
    elif menu == "📋 Ver Inventario":
        st.title("📋 Inventario Actual")
        col_f, col_ex = st.columns([3, 1])
        with col_f:
            busqueda = st.text_input("🔍 Buscar por Nombre o Código:", "")

        df_inv = pd.read_sql_query(
            "SELECT id, codigo, nombre, categoria, costo, COALESCE(precio_venta, precio, 0.0) as precio, stock_actual, stock_minimo FROM productos",
            conn,
        )

        if not df_inv.empty:
            if busqueda:
                df_inv = df_inv[
                    df_inv["nombre"].str.contains(
                        busqueda, case=False, na=False
                    )
                    | df_inv["codigo"].str.contains(
                        busqueda, case=False, na=False
                    )
                ]

            df_display = df_inv.copy()
            df_display["PRECIO VENTA ($)"] = df_display["precio"].map(
                "${:,.2f}".format
            )
            df_display["PRECIO VENTA (Bs.)"] = (
                df_display["precio"] * tasa
            ).map("{:,.2f} Bs.".format)

            with col_ex:
                st.write(" ")
                excel_bytes = exportar_a_excel(
                    df_inv, nombre_hoja="Inventario"
                )
                st.download_button(
                    "📥 Descargar Excel",
                    data=excel_bytes,
                    file_name=f"Inventario_{date.today()}.xlsx",
                )

            st.dataframe(df_display, use_container_width=True)

    # =========================================================
    # 3. CARGAR POR BULTO
    # =========================================================
    elif menu == "📦 Cargar por Bulto":
        st.title("📦 Desglose de Bultos")
        col1, col2 = st.columns([1, 1])
        with col1:
            codigo = st.text_input("Código *")
            nombre_unidad = st.text_input("Nombre Producto *")
            categoria = st.selectbox(
                "Categoría",
                [
                    "Víveres",
                    "Bebidas",
                    "Charcutería",
                    "Limpieza",
                    "Higiene",
                    "Golosinas",
                    "Otros",
                ],
            )
            costo_bulto = st.number_input(
                "Costo del Bulto ($)", min_value=0.01, value=18.00
            )
            unidades_por_bulto = st.number_input(
                "Unidades por Bulto", min_value=1, value=20
            )
            bultos_comprados = st.number_input(
                "Bultos Comprados", min_value=1, value=1
            )
            margen_deseado = st.number_input(
                "% Margen Ganancia", min_value=0.0, value=30.0
            )
            stock_minimo = st.number_input(
                "Stock Mínimo", min_value=1, value=5
            )

        costo_unidad = (
            costo_bulto / unidades_por_bulto if unidades_por_bulto > 0 else 0.0
        )
        precio_venta_usd = costo_unidad * (1 + (margen_deseado / 100))
        total_unidades = unidades_por_bulto * bultos_comprados

        with col2:
            st.info(f"Costo Unidad: `${costo_unidad:.2f}`")
            st.success(
                f"Precio Venta USD: `${precio_venta_usd:.2f}` | Bs: `{precio_venta_usd * tasa:,.2f} Bs.`"
            )
            if st.button(
                "🚀 GUARDAR EN INVENTARIO",
                type="primary",
                use_container_width=True,
            ):
                if codigo.strip() and nombre_unidad.strip():
                    exito, msg = guardar_producto(
                        codigo,
                        nombre_unidad,
                        categoria,
                        round(precio_venta_usd, 2),
                        round(costo_unidad, 2),
                        total_unidades,
                        stock_minimo,
                    )
                    if exito:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM productos WHERE codigo=?", (codigo,)
                        )
                        p_id = cursor.fetchone()[0]
                        cursor.execute(
                            "INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Entrada', ?, ?, ?)",
                            (
                                p_id,
                                total_unidades,
                                datetime.now().strftime("%Y-%m-%d %H:%M"),
                                usuario_actual,
                            ),
                        )
                        conn.commit()
                        st.success(msg)
                    else:
                        st.error(msg)

    # =========================================================
    # 4. EDITAR / AJUSTAR PRODUCTO
    # =========================================================
    elif menu == "✏️ Editar / Ajustar Producto":
        st.title("✏️ Editar Producto")
        df_p = pd.read_sql_query(
            "SELECT id, codigo, nombre FROM productos", conn
        )
        if not df_p.empty:
            opciones = [
                f"{row['id']} - {row['nombre']} ({row['codigo']})"
                for _, row in df_p.iterrows()
            ]
            prod_sel = st.selectbox("Seleccionar producto:", opciones)
            id_sel = int(prod_sel.split(" - ")[0])

            cursor = conn.cursor()
            cursor.execute(
                "SELECT nombre, categoria, COALESCE(precio_venta, precio, 0.0), costo, stock_actual, stock_minimo FROM productos WHERE id=?",
                (id_sel,),
            )
            p = cursor.fetchone()

            with st.form("form_edit"):
                e_nombre = st.text_input("Nombre", value=p[0])
                e_cat = st.selectbox(
                    "Categoría",
                    [
                        "Víveres",
                        "Bebidas",
                        "Charcutería",
                        "Limpieza",
                        "Higiene",
                        "Golosinas",
                        "Otros",
                    ],
                )
                e_precio = st.number_input("Precio ($)", value=float(p[2]))
                e_costo = st.number_input("Costo ($)", value=float(p[3]))
                e_stock = st.number_input("Stock", value=float(p[4]))
                e_min = st.number_input("Stock Mínimo", value=float(p[5]))

                if st.form_submit_button("💾 Guardar Cambios"):
                    if e_stock != p[4]:
                        dif = e_stock - p[4]
                        tipo_mov = (
                            "Ajuste Entrada" if dif > 0 else "Ajuste Salida"
                        )
                        cursor.execute(
                            "INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, ?, ?, ?, ?)",
                            (
                                id_sel,
                                tipo_mov,
                                abs(dif),
                                datetime.now().strftime("%Y-%m-%d %H:%M"),
                                usuario_actual,
                            ),
                        )
                    ok, msg = actualizar_producto(
                        id_sel,
                        e_nombre,
                        e_cat,
                        e_precio,
                        e_costo,
                        e_stock,
                        e_min,
                    )
                    st.success(msg) if ok else st.error(msg)
                    st.rerun()

    # =========================================================
    # 5. FIADOS Y CUENTAS POR COBRAR
    # =========================================================
    elif menu == "🤝 Fiados / Cuentas por Cobrar":
        st.title("🤝 Módulo de Fiados y Cuentas por Cobrar")

        tab_estado, tab_abono, tab_registro = st.tabs(
            ["📊 Estado de Cuentas", "💵 Registrar Abono", "👤 Registrar Cliente"]
        )

        with tab_registro:
            st.subheader("Registrar Nuevo Cliente")
            with st.form("form_nuevo_cliente"):
                cli_nombre = st.text_input("Nombre y Apellido *")
                cli_tlf = st.text_input("Teléfono")
                cli_limite = st.number_input(
                    "Límite de Crédito ($)", min_value=0.0, value=50.0
                )

                if st.form_submit_button("💾 Guardar Cliente"):
                    if cli_nombre.strip():
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO clientes (nombre, telefono, limite_credito) VALUES (?, ?, ?)",
                                (
                                    cli_nombre.strip(),
                                    cli_tlf.strip(),
                                    cli_limite,
                                ),
                            )
                            conn.commit()
                            st.success(f"Cliente '{cli_nombre}' registrado.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("El nombre de cliente ya existe.")
                    else:
                        st.warning("Ingrese el nombre del cliente.")

        with tab_estado:
            df_c = pd.read_sql_query(
                "SELECT id, nombre, telefono, limite_credito FROM clientes",
                conn,
            )
            if df_c.empty:
                st.info("No hay clientes registrados.")
            else:
                lista_saldos = []
                for _, cli in df_c.iterrows():
                    c_id = cli["id"]
                    tot_fiado = (
                        pd.read_sql_query(
                            "SELECT SUM(total_usd) as usd FROM ventas WHERE cliente_id=? AND metodo_pago='Crédito / Fiado' AND estado!='Anulada'",
                            conn,
                            params=[c_id],
                        )["usd"].iloc[0]
                        or 0.0
                    )
                    tot_abonado = (
                        pd.read_sql_query(
                            "SELECT SUM(monto_usd) as usd FROM abonos WHERE cliente_id=?",
                            conn,
                            params=[c_id],
                        )["usd"].iloc[0]
                        or 0.0
                    )

                    saldo_deuda = tot_fiado - tot_abonado
                    lista_saldos.append(
                        {
                            "ID": c_id,
                            "Cliente": cli["nombre"],
                            "Teléfono": cli["telefono"],
                            "Total Fiado ($)": tot_fiado,
                            "Total Abonado ($)": tot_abonado,
                            "Saldo Pendiente ($)": saldo_deuda,
                            "Saldo Pendiente (Bs.)": saldo_deuda * tasa,
                            "Límite ($)": cli["limite_credito"],
                        }
                    )

                df_saldos = pd.DataFrame(lista_saldos)
                st.dataframe(
                    df_saldos.style.format(
                        {
                            "Total Fiado ($)": "${:,.2f}",
                            "Total Abonado ($)": "${:,.2f}",
                            "Saldo Pendiente ($)": "${:,.2f}",
                            "Saldo Pendiente (Bs.)": "{:,.2f} Bs.",
                            "Límite ($)": "${:,.2f}",
                        }
                    ),
                    use_container_width=True,
                )

        with tab_abono:
            st.subheader("Registrar Pago / Abono de Deuda")
            df_c_abono = pd.read_sql_query(
                "SELECT id, nombre FROM clientes", conn
            )
            if df_c_abono.empty:
                st.info("No hay clientes registrados.")
            else:
                opts_c = [
                    f"{r['id']} - {r['nombre']}" for _, r in df_c_abono.iterrows()
                ]
                sel_c = st.selectbox(
                    "Seleccionar Cliente:", opts_c, key="abono_cli"
                )
                c_id_sel = int(sel_c.split(" - ")[0])

                tot_f = (
                    pd.read_sql_query(
                        "SELECT SUM(total_usd) as usd FROM ventas WHERE cliente_id=? AND metodo_pago='Crédito / Fiado' AND estado!='Anulada'",
                        conn,
                        params=[c_id_sel],
                    )["usd"].iloc[0]
                    or 0.0
                )
                tot_a = (
                    pd.read_sql_query(
                        "SELECT SUM(monto_usd) as usd FROM abonos WHERE cliente_id=?",
                        conn,
                        params=[c_id_sel],
                    )["usd"].iloc[0]
                    or 0.0
                )
                deuda_actual = tot_f - tot_a

                if deuda_actual <= 0:
                    st.success(
                        f"✅ El cliente no tiene deudas pendientes. (Saldo actual: **${deuda_actual:,.2f}**)"
                    )
                else:
                    st.warning(
                        f"Deuda Pendiente Actual: **${deuda_actual:,.2f} USD** / **{deuda_actual * tasa:,.2f} Bs.**"
                    )

                    with st.form("form_abono"):
                        monto_abono_usd = st.number_input(
                            "Monto a Abonar ($):",
                            min_value=0.01,
                            max_value=float(deuda_actual),
                            value=float(deuda_actual),
                        )
                        metodo_abono = st.selectbox(
                            "Método de Pago del Abono:",
                            [
                                "Efectivo $",
                                "Pago Móvil / Bolívares",
                                "Zelle",
                                "Punto de Venta",
                            ],
                        )

                        if st.form_submit_button("💵 Registrar Abono"):
                            fecha_abono = datetime.now().strftime(
                                "%Y-%m-%d %H:%M"
                            )
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO abonos (cliente_id, monto_usd, monto_bs, metodo_pago, fecha, responsable) VALUES (?, ?, ?, ?, ?, ?)",
                                (
                                    c_id_sel,
                                    monto_abono_usd,
                                    monto_abono_usd * tasa,
                                    metodo_abono,
                                    fecha_abono,
                                    usuario_actual,
                                ),
                            )
                            conn.commit()
                            st.success("✅ Abono registrado correctamente.")
                            st.rerun()

    # =========================================================
    # 6. CIERRE DE CAJA
    # =========================================================
    elif menu == "🔒 Cierre de Caja":
        st.title("🔒 Cierre de Caja")
        fecha_hoy = date.today().strftime("%Y-%m-%d")

        df_v_hoy = pd.read_sql_query(
            "SELECT total_usd, total_bs, metodo_pago FROM ventas WHERE fecha LIKE ? AND estado!='Anulada'",
            conn,
            params=[f"{fecha_hoy}%"],
        )

        tot_usd_sistema = df_v_hoy["total_usd"].sum() if not df_v_hoy.empty else 0.0
        tot_bs_sistema = df_v_hoy["total_bs"].sum() if not df_v_hoy.empty else 0.0

        st.subheader(f"Resumen de Ventas de Hoy ({fecha_hoy})")
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Total Ventas (USD)", f"${tot_usd_sistema:,.2f}")
        col_m2.metric("Total Ventas (Bs)", f"{tot_bs_sistema:,.2f} Bs.")

        st.divider()
        st.subheader("Cuadre Manual de Efectivo en Caja")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            efectivo_usd_real = st.number_input(
                "Efectivo Real en Dólares ($):", min_value=0.0, value=0.0
            )
        with col_c2:
            efectivo_bs_real = st.number_input(
                "Efectivo Real en Bolívares (Bs):", min_value=0.0, value=0.0
            )

        dif_usd = efectivo_usd_real - tot_usd_sistema
        dif_bs = efectivo_bs_real - tot_bs_sistema

        if st.button("🔒 Procesar Cierre de Caja", type="primary"):
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cierres_caja (fecha, responsable, total_usd, total_bs, diferencia_usd, diferencia_bs, estado) VALUES (?, ?, ?, ?, ?, ?, 'Cerrado')",
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    usuario_actual,
                    tot_usd_sistema,
                    tot_bs_sistema,
                    dif_usd,
                    dif_bs,
                ),
            )
            conn.commit()
            st.success("✅ Cierre de caja guardado con éxito.")

    # =========================================================
    # 7. ANULACIÓN DE VENTAS
    # =========================================================
    elif menu == "🚫 Anulación de Ventas":
        st.title("🚫 Anulación de Facturas / Ventas")
        df_v = pd.read_sql_query(
            "SELECT DISTINCT num_factura, fecha, responsable, total_usd FROM ventas WHERE estado='Completada' ORDER BY id DESC LIMIT 50",
            conn,
        )

        if df_v.empty:
            st.info("No hay ventas recientes activas para anular.")
        else:
            opts_f = [
                f"{r['num_factura']} | {r['fecha']} | ${r['total_usd']:.2f}"
                for _, r in df_v.iterrows()
            ]
            fac_sel = st.selectbox("Seleccione Factura a Anular:", opts_f)
            num_factura_target = fac_sel.split(" | ")[0]

            if st.button("🚨 Confirmar Anulación", type="primary"):
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT producto_id, cantidad FROM ventas WHERE num_factura=?",
                    (num_factura_target,),
                )
                items_anular = cursor.fetchall()

                for pid, cant in items_anular:
                    cursor.execute(
                        "UPDATE productos SET stock_actual = stock_actual + ? WHERE id=?",
                        (cant, pid),
                    )
                    cursor.execute(
                        "INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Anulación Venta', ?, ?, ?)",
                        (
                            pid,
                            cant,
                            datetime.now().strftime("%Y-%m-%d %H:%M"),
                            usuario_actual,
                        ),
                    )

                cursor.execute(
                    "UPDATE ventas SET estado='Anulada' WHERE num_factura=?",
                    (num_factura_target,),
                )
                conn.commit()
                st.success(f"Factura {num_factura_target} anulada y stock devuelto.")
                st.rerun()

    # =========================================================
    # 8. DASHBOARD (Admin / Master)
    # =========================================================
    elif menu == "📊 Dashboard":
        st.title("📊 Panel de Control y Estadísticas")
        tot_v = (
            pd.read_sql_query(
                "SELECT SUM(total_usd) as total FROM ventas WHERE estado!='Anulada'",
                conn,
            )["total"].iloc[0]
            or 0.0
        )
        tot_g = (
            pd.read_sql_query(
                "SELECT SUM(monto) as total FROM gastos", conn
            )["total"].iloc[0]
            or 0.0
        )
        prod_count = pd.read_sql_query("SELECT COUNT(*) as total FROM productos", conn)[
            "total"
        ].iloc[0]

        c1, c2, c3 = st.columns(3)
        c1.metric("Ventas Totales ($)", f"${tot_v:,.2f}")
        c2.metric("Gastos Totales ($)", f"${tot_g:,.2f}")
        c3.metric("Productos en Catálogo", f"{prod_count}")

    # =========================================================
    # 9. CALCULADORA
    # =========================================================
    elif menu == "🧮 Calculadora":
        st.title("🧮 Calculadora Rápida de Moneda y Margen")
        col_ca1, col_ca2 = st.columns(2)
        with col_ca1:
            st.subheader("Convertidor Divisa")
            monto_calc = st.number_input(
                "Monto:", min_value=0.0, value=10.0, key="c_monto"
            )
            op_tipo = st.radio("Convertir:", ["USD ➡️ Bs", "Bs ➡️ USD"])
            if op_tipo == "USD ➡️ Bs":
                st.success(f"**{monto_calc * tasa:,.2f} Bs.**")
            else:
                st.success(
                    f"**${monto_calc / tasa if tasa > 0 else 0:,.2f} USD**"
                )

        with col_ca2:
            st.subheader("Cálculo de Margen Ganancia")
            costo_in = st.number_input("Costo ($):", min_value=0.0, value=5.0)
            margen_in = st.number_input(
                "% Margen Deseado:", min_value=0.0, value=30.0
            )
            pv_calc = costo_in * (1 + (margen_in / 100))
            st.info(
                f"Precio Venta Sugerido: **${pv_calc:.2f}** ({pv_calc * tasa:,.2f} Bs.)"
            )

    # =========================================================
    # 10. GASTOS / CAJA CHICA
    # =========================================================
    elif menu == "💸 Gastos / Caja Chica":
        st.title("💸 Registro de Gastos / Caja Chica")
        with st.form("form_gasto"):
            desc = st.text_input("Descripción del Gasto *")
            monto_g = st.number_input(
                "Monto *", min_value=0.01, value=1.0, step=0.5
            )
            moneda_g = st.selectbox("Moneda", ["USD", "BS"])
            if st.form_submit_button("💾 Registrar Gasto"):
                if desc.strip():
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO gastos (descripcion, monto, fecha, moneda, responsable) VALUES (?, ?, ?, ?, ?)",
                        (
                            desc.strip(),
                            monto_g,
                            datetime.now().strftime("%Y-%m-%d %H:%M"),
                            moneda_g,
                            usuario_actual,
                        ),
                    )
                    conn.commit()
                    st.success("Gasto registrado.")
                    st.rerun()

        df_gastos = pd.read_sql_query(
            "SELECT * FROM gastos ORDER BY id DESC", conn
        )
        st.dataframe(df_gastos, use_container_width=True)

    # =========================================================
    # 11. HISTORIAL Y TRANSACCIONES
    # =========================================================
    elif menu == "📜 Historial y Transacciones":
        st.title("📜 Historial de Transacciones")
        tab_h_ventas, tab_h_movs = st.tabs(
            ["🛒 Historial de Ventas", "📦 Movimientos de Inventario"]
        )

        with tab_h_ventas:
            df_hv = pd.read_sql_query(
                "SELECT * FROM ventas ORDER BY id DESC LIMIT 100", conn
            )
            st.dataframe(df_hv, use_container_width=True)

        with tab_h_movs:
            df_hm = pd.read_sql_query(
                "SELECT * FROM movimientos ORDER BY id DESC LIMIT 100", conn
            )
            st.dataframe(df_hm, use_container_width=True)

    # =========================================================
    # 12. GESTIÓN DE USUARIOS (SuperAdmin / Master)
    # =========================================================
    elif menu == "👥 Gestión de Usuarios":
        st.title("👥 Gestión de Usuarios del Sistema")
        with st.form("form_user"):
            nuevo_u = st.text_input("Nombre de Usuario *")
            nueva_p = st.text_input("Contraseña *", type="password")
            nuevo_r = st.selectbox("Rol", ["Vendedor", "SuperAdmin"])
            if st.form_submit_button("👤 Crear Usuario"):
                if nuevo_u.strip() and nueva_p.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO usuarios (nombre, clave, rol) VALUES (?, ?, ?)",
                            (nuevo_u.strip(), nueva_p.strip(), nuevo_r),
                        )
                        conn.commit()
                        st.success("Usuario creado con éxito.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("El usuario ya existe.")

        df_usr = pd.read_sql_query("SELECT id, nombre, rol FROM usuarios", conn)
        st.dataframe(df_usr, use_container_width=True)
        
    else:
        st.warning(f"Deuda Pendiente Actual: **${deuda_actual:,.2f}** ({deuda_actual * tasa:,.2f} Bs.)")
        
        with st.form("form_abono"):
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                moneda_abono = st.selectbox("Moneda recibida:", ["USD ($)", "Bolívares (Bs.)"])
                # Se ajusta el valor por defecto/máximo sugerido según la moneda elegida
                max_monto_sugerido = float(deuda_actual) if moneda_abono == "USD ($)" else float(deuda_actual * tasa)
                monto_abono = st.number_input("Monto a Abonar:", 
                                              min_value=0.01, 
                                              value=max_monto_sugerido)
            with col_a2:
                metodo_abono = st.selectbox("Método de Pago:", ["Efectivo $", "Pago Móvil / Bolívares", "Zelle", "Punto de Venta"])
            
            if st.form_submit_button("💵 Procesar Abono"):
                monto_usd_final = monto_abono if moneda_abono == "USD ($)" else monto_abono / tasa
                monto_bs_final = monto_abono * tasa if moneda_abono == "USD ($)" else monto_abono
                
                # Validación para no abonar más de la deuda actual (con margen flotante)
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
    # 6. CIERRE DE CAJA
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
        
        # Consulta de Ventas Activas
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
        
        # Consulta de Abonos de Deudas recibidos en la fecha
        query_a = "SELECT monto_usd, monto_bs, metodo_pago, responsable FROM abonos WHERE fecha LIKE ?"
        params_a = [f"{fecha_cierre}%"]
        if cajero_sel != "Todos":
            query_a += " AND responsable = ?"
            params_a.append(cajero_sel)
        df_abonos_dia = pd.read_sql_query(query_a, conn, params=params_a)

        # Consulta de Gastos
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
    # 7. ANULACIÓN DE VENTAS CON REINTEGRO DE STOCK
    # =========================================================
    elif menu == "🚫 Anulación de Ventas":
        st.title("🚫 Anulación de Ventas con Reintegro de Stock")

        try:
            # Obtener facturas/ventas que no estén anuladas (incluyendo MAX(id) para evitar KeyError)
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

                # Detalle de los productos pertenecientes a esa transacción
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

                        # 1. Reintegrar stock y registrar movimiento
                        for _, item in df_detalles.iterrows():
                            prod_id = item['producto_id']
                            cant = item['cantidad']
                            cursor.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (cant, prod_id))
                            cursor.execute("""
                                INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable)
                                VALUES (?, 'Anulación Venta', ?, ?, ?)
                            """, (prod_id, cant, datetime.now().strftime("%Y-%m-%d %H:%M"), usuario_actual))

                        # 2. Cambiar estado a 'Anulada'
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
    # 8. DASHBOARD (Solo Admin / Master)
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
    # 9. CALCULADORA
    # =========================================================
    elif menu == "🧮 Calculadora":
        st.title("🧮 Calculadora de Precios y Conversión")
        if 'calculadora' in globals() and calculadora and hasattr(calculadora, 'mostrar'):
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
    # 10. GASTOS / CAJA CHICA
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
    # 11. HISTORIAL Y TRANSACCIONES
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
    # 12. GESTIÓN DE USUARIOS (Solo Admin / Master)
    # =========================================================
    elif menu == "👥 Gestión de Usuarios":
        st.title("⚙️ Gestión de Usuarios")
        
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

        # --- MODIFICAR USUARIO / CAMBIAR CONTRASEÑA ---
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
