import requests

def obtener_tasa_bcv(tasa_respaldo=36.50):
    """Obtiene la tasa oficial del BCV con fallback automático."""
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial", timeout=4)
        if response.status_code == 200:
            return float(response.json().get('promedio', tasa_respaldo))
    except Exception:
        pass
    return tasa_respaldo

def usd_a_bs(monto_usd, tasa):
    """Convierte un monto en USD a Bolívares."""
    return round(float(monto_usd) * float(tasa), 2)

def bs_a_usd(monto_bs, tasa):
    """Convierte un monto en Bolívares a USD."""
    if tasa <= 0:
        return 0.0
    return round(float(monto_bs) / float(tasa), 2)

def calcular_margen_ganancia(costo_usd, precio_usd):
    """Calcula el porcentaje de ganancia sobre el costo."""
    if costo_usd <= 0:
        return 0.0
    ganancia = precio_usd - costo_usd
    porcentaje = (ganancia / costo_usd) * 100
    return round(porcentaje, 2)

def calcular_vuelto(total_usd, pago_usd, pago_bs, tasa):
    """
    Calcula el vuelto faltante o sobrante en USD y Bs. aceptando pagos mixtos.
    Retorna: (es_suficiente: bool, vuelto_usd: float, vuelto_bs: float)
    """
    total_pagado_usd = pago_usd + bs_a_usd(pago_bs, tasa)
    diferencia_usd = round(total_pagado_usd - total_usd, 2)
    
    if diferencia_usd >= 0:
        return True, diferencia_usd, usd_a_bs(diferencia_usd, tasa)
    else:
        return False, abs(diferencia_usd), usd_a_bs(abs(diferencia_usd), tasa)