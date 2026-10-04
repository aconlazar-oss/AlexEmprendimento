"""Herramientas de Jarvis para controlar la PC donde corre el servidor.

Por seguridad, Jarvis NO ejecuta comandos arbitrarios: solo abre aplicaciones
de una lista conocida (APPS), páginas web, carpetas y archivos.
"""

import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

SISTEMA = platform.system()  # "Windows", "Darwin" (Mac) o "Linux"
NOTAS = Path(__file__).parent / "datos" / "notas"

# Nombre hablado -> comando por sistema operativo. Agrega aquí tus programas.
APPS = {
    "calculadora": {"Windows": ["calc"], "Darwin": ["open", "-a", "Calculator"], "Linux": ["gnome-calculator"]},
    "bloc de notas": {"Windows": ["notepad"], "Darwin": ["open", "-a", "TextEdit"], "Linux": ["gedit"]},
    "explorador": {"Windows": ["explorer"], "Darwin": ["open", "."], "Linux": ["xdg-open", "."]},
    "excel": {"Windows": ["cmd", "/c", "start", "", "excel"], "Darwin": ["open", "-a", "Microsoft Excel"], "Linux": ["libreoffice", "--calc"]},
    "word": {"Windows": ["cmd", "/c", "start", "", "winword"], "Darwin": ["open", "-a", "Microsoft Word"], "Linux": ["libreoffice", "--writer"]},
    "chrome": {"Windows": ["cmd", "/c", "start", "", "chrome"], "Darwin": ["open", "-a", "Google Chrome"], "Linux": ["google-chrome"]},
    "spotify": {"Windows": ["cmd", "/c", "start", "", "spotify:"], "Darwin": ["open", "-a", "Spotify"], "Linux": ["spotify"]},
    "whatsapp": {"Windows": ["cmd", "/c", "start", "", "whatsapp:"], "Darwin": ["open", "-a", "WhatsApp"], "Linux": ["xdg-open", "https://web.whatsapp.com"]},
}

SITIOS = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "whatsapp web": "https://web.whatsapp.com",
    "google drive": "https://drive.google.com",
    "sisap midagri": "https://sistemas.midagri.gob.pe/sisap/portal2/mayorista/",
}

# Recordatorios pendientes que la interfaz web consulta y lee en voz alta.
_eventos = []
_eventos_lock = threading.Lock()


def _abrir_ruta(ruta):
    if SISTEMA == "Windows":
        os.startfile(ruta)  # noqa: S606 - abre con el programa por defecto
    elif SISTEMA == "Darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


def abrir_aplicacion(nombre):
    nombre = nombre.lower().strip()
    if nombre in SITIOS:
        return abrir_web(SITIOS[nombre])
    app = APPS.get(nombre)
    if not app:
        return {"error": f"No conozco la aplicación '{nombre}'. Conocidas: {sorted(APPS) + sorted(SITIOS)}. "
                         "Se pueden agregar en jarvis/pc.py."}
    cmd = app.get(SISTEMA)
    if not cmd or (not shutil.which(cmd[0]) and cmd[0] not in ("cmd", "open")):
        return {"error": f"'{nombre}' no está disponible en este sistema ({SISTEMA})."}
    subprocess.Popen(cmd)
    return {"ok": True, "abierto": nombre}


def abrir_web(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return {"ok": True, "url": url}


def buscar_en_google(consulta):
    return abrir_web("https://www.google.com/search?q=" + urllib.parse.quote_plus(consulta))


def abrir_carpeta(ruta):
    destino = {
        "escritorio": Path.home() / "Desktop",
        "descargas": Path.home() / "Downloads",
        "documentos": Path.home() / "Documents",
        "notas": NOTAS,
        "analisis": Path(__file__).parent.parent / "analisis",
    }.get(ruta.lower().strip(), Path(ruta).expanduser())
    if not destino.exists():
        return {"error": f"No existe: {destino}"}
    _abrir_ruta(str(destino))
    return {"ok": True, "abierto": str(destino)}


def abrir_calculadora_huevos():
    ruta = Path(__file__).parent.parent / "analisis" / "calculadora_huevos.xlsx"
    _abrir_ruta(str(ruta))
    return {"ok": True, "abierto": str(ruta)}


def crear_nota(titulo, contenido):
    NOTAS.mkdir(parents=True, exist_ok=True)
    seguro = "".join(c for c in titulo if c.isalnum() or c in " -_").strip() or "nota"
    ruta = NOTAS / f"{datetime.now():%Y-%m-%d_%H%M} {seguro}.txt"
    ruta.write_text(contenido, encoding="utf-8")
    return {"ok": True, "archivo": str(ruta)}


def programar_recordatorio(mensaje, minutos):
    if minutos <= 0 or minutos > 24 * 60:
        return {"error": "minutos debe estar entre 1 y 1440"}

    def disparar():
        time.sleep(minutos * 60)
        with _eventos_lock:
            _eventos.append({"tipo": "recordatorio", "mensaje": mensaje})

    threading.Thread(target=disparar, daemon=True).start()
    hora = datetime.fromtimestamp(time.time() + minutos * 60)
    return {"ok": True, "mensaje": mensaje, "sonara_a_las": hora.strftime("%H:%M")}


def tomar_eventos():
    with _eventos_lock:
        pendientes = list(_eventos)
        _eventos.clear()
    return pendientes


def estado_sistema():
    disco = shutil.disk_usage(Path.home())
    return {
        "fecha_hora": datetime.now().strftime("%A %d/%m/%Y %H:%M"),
        "sistema": f"{SISTEMA} {platform.release()}",
        "disco_libre_gb": round(disco.free / 1e9, 1),
        "disco_total_gb": round(disco.total / 1e9, 1),
        "cpus": os.cpu_count(),
    }
