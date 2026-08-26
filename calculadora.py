import streamlit as st
import pandas as pd
import requests

@st.cache_data(ttl=3600)
def obtener_tasa_bcv():
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
        return float(response.json()['promedio'])
    except:
        return 43.50

def calculadora_precios():
    st.title("🧮 Calculadora de Precios y Estructura de Costos")
    st.markdown("Calcula el **precio final de venta** de tus productos integrando el costo de compra, gastos adicionales (gasolina, transporte, fletes) y tu margen de ganancia.")

    # Obtener Tasa Oficial
    tasa = obtener_tasa_bcv()
    st.info(f"💵 **Tasa BCV Oficial:** `{tasa:.2f} Bs./$`")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Costo Base y Gastos Adicionales")
        costo_base = st.number_input("Costo de Compra Unitario ($) *", min_value=0.0, step=0.10, value=2.00, format="%.2f")
        
        st.markdown("---")
        st.caption("⛽ **Gastos de Logística (Gasolina, Flete, Embalaje, etc.)**")
        
        modalidad_gasto = st.radio(
            "¿Cómo deseas prorratear los gastos?",
            ["Por Lote / Viaje Completo", "Directo por Unidad"],
            horizontal=True
        )
        
        gasto_por_unidad = 0.0
        if modalidad_gasto == "Por Lote / Viaje Completo":
            gasto_total_lote = st.number_input("Monto total de gastos del viaje/lote ($)", min_value=0.0, step=0.50, value=5.00, format="%.2f")
            unidades_lote = st.number_input("Cantidad total de unidades en el lote", min_value=1, step=1, value=20)
            if unidades_lote > 0:
                gasto_por_unidad = gasto_total_lote / unidades_lote
                st.caption(f"💡 *Gasto de gasolina/transporte imputado:* **${gasto_por_unidad:.2f}** por unidad.")
        else:
            gasto_por_unidad = st.number_input("Gasto adicional por cada unidad ($)", min_value=0.0, step=0.05, value=0.25, format="%.2f")

        # Costo Total Real
        costo_total_unitario = costo_base + gasto_por_unidad

    with col2:
        st.subheader("2. Margen de Ganancia y Venta")
        porcentaje_ganancia = st.number_input("Porcentaje de Ganancia deseado (%)", min_value=0.0, max_value=500.0, step=5.0, value=30.0)
        
        # Cálculos de Precio
        precio_venta_usd = costo_total_unitario * (1 + (porcentaje_ganancia / 100))
        ganancia_usd = precio_venta_usd - costo_total_unitario
        
        # Conversiones a Bolívares
        costo_total_bs = costo_total_unitario * tasa
        precio_venta_bs = precio_venta_usd * tasa
        ganancia_bs = ganancia_usd * tasa

        st.markdown("---")
        st.subheader("📊 Resultados Calculados")
        
        m1, m2 = st.columns(2)
        m1.metric("Costo Real Unitario ($)", f"${costo_total_unitario:.2f}", help=f"Costo base (${costo_base:.2f}) + Gastos (${gasto_por_unidad:.2f})")
        m2.metric("Costo Real Unitario (Bs.)", f"{costo_total_bs:.2f} Bs.")

        m3, m4 = st.columns(2)
        m3.metric("🏷️ Precio Venta Sugerido ($)", f"${precio_venta_usd:.2f}")
        m4.metric("🏷️ Precio Venta Sugerido (Bs.)", f"{precio_venta_bs:.2f} Bs.")

        st.success(f"💰 **Ganancia neta estimada por unidad:** `${ganancia_usd:.2f}` / `{ganancia_bs:.2f} Bs.` ({porcentaje_ganancia:.0f}% sobre costo real)")

    # Tabla Desglose Detallado
    st.divider()
    st.subheader("📋 Tabla Desglose Estructurado")
    
    df_desglose = pd.DataFrame({
        "Concepto": [
            "1. Costo de Compra Base", 
            "2. Gastos Adicionales (Gasolina/Transporte)", 
            "3. COSTO REAL UNITARIO", 
            f"4. Margen de Ganancia ({porcentaje_ganancia:.0f}%)", 
            "5. PRECIO FINAL DE VENTA"
        ],
        "Monto USD ($)": [
            f"${costo_base:.2f}", 
            f"${gasto_por_unidad:.2f}", 
            f"${costo_total_unitario:.2f}", 
            f"${ganancia_usd:.2f}", 
            f"${precio_venta_usd:.2f}"
        ],
        "Monto Bolívares (Bs.)": [
            f"{costo_base * tasa:.2f} Bs.", 
            f"{gasto_por_unidad * tasa:.2f} Bs.", 
            f"{costo_total_bs:.2f} Bs.", 
            f"{ganancia_bs:.2f} Bs.", 
            f"{precio_venta_bs:.2f} Bs."
        ]
    })
    
    st.table(df_desglose)