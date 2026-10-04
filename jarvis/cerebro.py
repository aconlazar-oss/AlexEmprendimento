"""El cerebro de Jarvis: conversa con Claude y ejecuta herramientas."""

import json
import threading

import anthropic

import negocio
import pc

MODELO = "claude-opus-5-5"

SISTEMA = """Eres J.A.R.V.I.S., el asistente personal de Alex, inspirado en el Jarvis de Iron Man.
Hablas en español latino, con elegancia británica, ingenio seco y lealtad total. Llamas a Alex "señor".

Tus respuestas se leen en voz alta, así que:
- Responde breve (1 a 3 frases) salvo que te pidan detalle.
- Nada de markdown, viñetas, emojis ni tablas. Escribe como se habla.
- Di los montos como "15 soles con 50" y redondea cifras para que suenen naturales.

Alex tiene un emprendimiento de venta de huevos en Lima (compra a granjas y vende a bodegas y hogares).
Usa las herramientas de negocio para cálculos, registrar ventas y compras, y dar resúmenes; nunca inventes cifras.
Puedes controlar su PC con las herramientas disponibles (abrir aplicaciones, webs, carpetas, notas, recordatorios).
Si te piden algo de la PC que tus herramientas no cubren, dilo con franqueza en vez de fingir que lo hiciste.
Antes de registrar una venta o compra, asegúrate de tener cantidad y precio; si falta algo, pregunta."""


def _tool(name, description, props, required):
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": props, "required": required, "additionalProperties": False},
    }


NUM = {"type": "number"}
STR = {"type": "string"}

HERRAMIENTAS = [
    _tool("calcular_meta_diaria",
          "Calcula cuántos kg, bandejas, huevos y jabas hay que vender al día para lograr una ganancia diaria, "
          "y cuánto capital de trabajo se necesita. Usa los supuestos guardados.",
          {"ganancia_deseada": {**NUM, "description": "Ganancia neta deseada por día en soles"},
           "canal": {"type": "string", "enum": ["mixto", "bodegas", "hogares"]}},
          ["ganancia_deseada"]),
    _tool("ver_supuestos", "Muestra precios y costos actuales del negocio y la ganancia limpia por kg de cada canal.", {}, []),
    _tool("actualizar_supuesto",
          "Cambia un supuesto del negocio (por ejemplo el precio de compra por kg cuando sube en la granja).",
          {"clave": {"type": "string", "enum": sorted(negocio.SUPUESTOS_INICIALES)}, "valor": NUM},
          ["clave", "valor"]),
    _tool("registrar_movimiento",
          "Registra una venta, compra de mercadería o gasto. Para gastos sin bandejas usa bandejas=1 y el monto como precio.",
          {"tipo": {"type": "string", "enum": ["venta", "compra", "gasto"]},
           "bandejas": NUM, "precio_por_bandeja": {**NUM, "description": "Soles por bandeja"},
           "cliente": STR, "nota": STR},
          ["tipo", "bandejas", "precio_por_bandeja"]),
    _tool("resumen", "Resumen de ventas, compras, gastos y mejores clientes.",
          {"periodo": {"type": "string", "enum": ["hoy", "semana", "mes"]}}, ["periodo"]),
    _tool("abrir_aplicacion", "Abre una aplicación o sitio conocido de la PC (calculadora, excel, chrome, spotify, youtube, gmail...).",
          {"nombre": STR}, ["nombre"]),
    _tool("abrir_web", "Abre una página web en el navegador.", {"url": STR}, ["url"]),
    _tool("buscar_en_google", "Abre una búsqueda de Google en el navegador.", {"consulta": STR}, ["consulta"]),
    _tool("abrir_carpeta", "Abre una carpeta: escritorio, descargas, documentos, notas, analisis, o una ruta.",
          {"ruta": STR}, ["ruta"]),
    _tool("abrir_calculadora_huevos", "Abre el Excel de la calculadora de rentabilidad de huevos.", {}, []),
    _tool("crear_nota", "Guarda una nota de texto en la PC.", {"titulo": STR, "contenido": STR}, ["titulo", "contenido"]),
    _tool("programar_recordatorio", "Programa un recordatorio que Jarvis dirá en voz alta dentro de N minutos.",
          {"mensaje": STR, "minutos": NUM}, ["mensaje", "minutos"]),
    _tool("estado_sistema", "Fecha, hora y estado de la PC (disco, sistema).", {}, []),
]

FUNCIONES = {
    "calcular_meta_diaria": negocio.calcular_meta_diaria,
    "ver_supuestos": negocio.ver_supuestos,
    "actualizar_supuesto": negocio.actualizar_supuesto,
    "registrar_movimiento": negocio.registrar_movimiento,
    "resumen": negocio.resumen,
    "abrir_aplicacion": pc.abrir_aplicacion,
    "abrir_web": pc.abrir_web,
    "buscar_en_google": pc.buscar_en_google,
    "abrir_carpeta": pc.abrir_carpeta,
    "abrir_calculadora_huevos": pc.abrir_calculadora_huevos,
    "crear_nota": pc.crear_nota,
    "programar_recordatorio": pc.programar_recordatorio,
    "estado_sistema": pc.estado_sistema,
}


def _ejecutar(bloque):
    try:
        resultado = FUNCIONES[bloque.name](**bloque.input)
        es_error = isinstance(resultado, dict) and "error" in resultado
    except Exception as e:  # el error vuelve a Claude para que lo explique
        resultado, es_error = {"error": f"{type(e).__name__}: {e}"}, True
    return {
        "type": "tool_result",
        "tool_use_id": bloque.id,
        "content": json.dumps(resultado, ensure_ascii=False, default=str),
        "is_error": es_error,
    }


class Jarvis:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.historial = []
        self.lock = threading.Lock()

    def reiniciar(self):
        with self.lock:
            self.historial = []

    def responder(self, texto):
        """Devuelve (respuesta_hablada, acciones_ejecutadas)."""
        with self.lock:
            inicio = len(self.historial)
            try:
                return self._turno(texto)
            except Exception:
                del self.historial[inicio:]  # no dejar el historial a medias
                raise

    def _turno(self, texto):
        inicio = len(self.historial)
        self.historial.append({"role": "user", "content": texto})
        acciones = []
        for _ in range(10):  # tope de rondas de herramientas por mensaje
            resp = self.client.beta.messages.create(
                model=MODELO,
                max_tokens=16000,
                system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
                tools=HERRAMIENTAS,
                messages=self.historial,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},  # respuestas rápidas para voz
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",  # si el modelo declina, otro modelo responde
            )
            if resp.stop_reason == "refusal":
                del self.historial[inicio:]
                return "Lo siento, señor, no puedo ayudarle con eso.", acciones

            self.historial.append({"role": "assistant", "content": resp.content})
            usos = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not usos:
                texto_final = " ".join(b.text for b in resp.content if b.type == "text").strip()
                return texto_final or "Hecho, señor.", acciones

            resultados = [_ejecutar(b) for b in usos]
            acciones += [{"herramienta": b.name, "entrada": b.input} for b in usos]
            self.historial.append({"role": "user", "content": resultados})

        del self.historial[inicio:]
        return "Señor, la tarea tomó demasiados pasos; la detuve por precaución.", acciones
