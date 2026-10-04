"""Herramientas de Jarvis para el negocio de venta de huevos en Lima.

Los supuestos replican la hoja "Supuestos" de analisis/calculadora_huevos.xlsx.
Se guardan en datos/supuestos.json para que Jarvis pueda actualizarlos por voz.
"""

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

DATOS = Path(__file__).parent / "datos"
SUPUESTOS_PATH = DATOS / "supuestos.json"
VENTAS_PATH = DATOS / "movimientos.json"

_lock = threading.Lock()

SUPUESTOS_INICIALES = {
    "precio_compra_kg": 5.9,
    "precio_venta_kg_mixto": 7.2,
    "precio_venta_kg_bodegas": 6.7,
    "precio_venta_kg_hogares": 7.8,
    "merma_pct": 0.02,
    "empaque_kg": 0.08,
    "combustible_kg": 0.10,
    "kg_por_bandeja": 1.85,
    "huevos_por_bandeja": 30,
    "bandejas_por_jaba": 12,
    "dias_trabajados_mes": 26,
    "dias_stock": 2,
}

# (gasto fijo al día, se aplica desde una ganancia diaria de)
NIVELES = [
    (30, 0, "Tú solo, con moto o mototaxi"),
    (100, 201, "Moto carguera o furgoneta y 1 ayudante"),
    (200, 501, "Distribuidora: camioneta, 2 ayudantes y almacén"),
]

CANALES = {"mixto", "bodegas", "hogares"}


def _leer(path, defecto):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return defecto


def _escribir(path, datos):
    DATOS.mkdir(exist_ok=True)
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def supuestos():
    return {**SUPUESTOS_INICIALES, **_leer(SUPUESTOS_PATH, {})}


def ver_supuestos():
    s = supuestos()
    return {"supuestos": s, "ganancia_limpia_por_kg": {c: round(_ganancia_kg(s, c), 3) for c in sorted(CANALES)}}


def actualizar_supuesto(clave, valor):
    if clave not in SUPUESTOS_INICIALES:
        return {"error": f"Supuesto desconocido: {clave}. Válidos: {sorted(SUPUESTOS_INICIALES)}"}
    with _lock:
        guardados = _leer(SUPUESTOS_PATH, {})
        anterior = supuestos()[clave]
        guardados[clave] = valor
        _escribir(SUPUESTOS_PATH, guardados)
    return {"ok": True, "clave": clave, "anterior": anterior, "nuevo": valor}


def _ganancia_kg(s, canal):
    precio = s[f"precio_venta_kg_{canal}"]
    compra = s["precio_compra_kg"]
    return precio - compra - compra * s["merma_pct"] - s["empaque_kg"] - s["combustible_kg"]


def _gasto_fijo(ganancia_deseada):
    gasto, nivel = NIVELES[0][0], NIVELES[0][2]
    for g, desde, nombre in NIVELES:
        if ganancia_deseada >= desde:
            gasto, nivel = g, nombre
    return gasto, nivel


def calcular_meta_diaria(ganancia_deseada, canal="mixto"):
    if canal not in CANALES:
        return {"error": f"Canal inválido. Usa uno de: {sorted(CANALES)}"}
    s = supuestos()
    g_kg = _ganancia_kg(s, canal)
    if g_kg <= 0:
        return {"error": f"Con estos precios pierdes dinero en el canal {canal} (ganancia por kg {g_kg:.2f})."}
    gasto, nivel = _gasto_fijo(ganancia_deseada)
    kg = (ganancia_deseada + gasto) / g_kg
    bandejas = kg / s["kg_por_bandeja"]
    compra = kg * s["precio_compra_kg"]
    return {
        "canal": canal,
        "nivel_negocio": nivel,
        "gasto_fijo_dia": gasto,
        "ganancia_limpia_por_kg": round(g_kg, 3),
        "kg_dia": round(kg, 1),
        "bandejas_dia": round(bandejas, 1),
        "huevos_dia": round(bandejas * s["huevos_por_bandeja"]),
        "jabas_dia": round(bandejas / s["bandejas_por_jaba"], 1),
        "ventas_dia_soles": round(kg * s[f"precio_venta_kg_{canal}"], 2),
        "compra_dia_soles": round(compra, 2),
        "capital_trabajo_soles": round(compra * s["dias_stock"], 2),
        "ganancia_mes_soles": round(ganancia_deseada * s["dias_trabajados_mes"], 2),
    }


def registrar_movimiento(tipo, bandejas, precio_por_bandeja, cliente="", nota=""):
    if tipo not in ("venta", "compra", "gasto"):
        return {"error": "tipo debe ser venta, compra o gasto"}
    mov = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "bandejas": bandejas,
        "precio_por_bandeja": precio_por_bandeja,
        "total": round(bandejas * precio_por_bandeja, 2),
        "cliente": cliente,
        "nota": nota,
    }
    with _lock:
        movs = _leer(VENTAS_PATH, [])
        movs.append(mov)
        _escribir(VENTAS_PATH, movs)
    return {"ok": True, "registrado": mov}


def resumen(periodo="hoy"):
    hoy = date.today()
    desde = {"hoy": hoy, "semana": hoy - timedelta(days=6), "mes": hoy.replace(day=1)}.get(periodo)
    if desde is None:
        return {"error": "periodo debe ser hoy, semana o mes"}
    movs = [m for m in _leer(VENTAS_PATH, []) if date.fromisoformat(m["fecha"][:10]) >= desde]
    tot = {t: sum(m["total"] for m in movs if m["tipo"] == t) for t in ("venta", "compra", "gasto")}
    bandejas_vendidas = sum(m["bandejas"] for m in movs if m["tipo"] == "venta")
    bandejas_compradas = sum(m["bandejas"] for m in movs if m["tipo"] == "compra")
    clientes = {}
    for m in movs:
        if m["tipo"] == "venta" and m["cliente"]:
            clientes[m["cliente"]] = clientes.get(m["cliente"], 0) + m["total"]
    return {
        "periodo": periodo,
        "desde": desde.isoformat(),
        "ventas_soles": round(tot["venta"], 2),
        "compras_soles": round(tot["compra"], 2),
        "gastos_soles": round(tot["gasto"], 2),
        "flujo_neto_soles": round(tot["venta"] - tot["compra"] - tot["gasto"], 2),
        "bandejas_vendidas": bandejas_vendidas,
        "bandejas_compradas": bandejas_compradas,
        "mejores_clientes": sorted(clientes.items(), key=lambda x: -x[1])[:5],
        "num_movimientos": len(movs),
    }
