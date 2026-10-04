"""Servidor local de Jarvis. Ejecuta:  python servidor.py   y abre http://localhost:8000

Escucha solo en 127.0.0.1: la interfaz y el control de la PC no quedan expuestos a la red.
"""

import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

import pc
from cerebro import Jarvis

PUERTO = 8000
ESTATICOS = Path(__file__).parent / "static"
jarvis = Jarvis()


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ESTATICOS), **kwargs)

    def log_message(self, *args):
        pass

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/eventos":
            return self._json({"eventos": pc.tomar_eventos()})
        return super().do_GET()

    def do_POST(self):
        # Bloquea peticiones de otras páginas web abiertas en el navegador.
        origen = self.headers.get("Origin", "")
        if origen and origen not in (f"http://localhost:{PUERTO}", f"http://127.0.0.1:{PUERTO}"):
            return self._json({"error": "origen no permitido"}, 403)

        if self.path == "/api/reiniciar":
            jarvis.reiniciar()
            return self._json({"ok": True})
        if self.path != "/api/chat":
            return self._json({"error": "no encontrado"}, 404)

        largo = int(self.headers.get("Content-Length", 0))
        texto = json.loads(self.rfile.read(largo) or b"{}").get("mensaje", "").strip()
        if not texto:
            return self._json({"error": "mensaje vacío"}, 400)
        try:
            respuesta, acciones = jarvis.responder(texto)
            self._json({"respuesta": respuesta, "acciones": acciones})
        except anthropic.AuthenticationError:
            self._json({"respuesta": "Señor, mi clave de acceso a Claude no es válida. Revise ANTHROPIC_API_KEY."}, 500)
        except anthropic.RateLimitError:
            self._json({"respuesta": "Estoy recibiendo demasiadas peticiones, señor. Intente en un momento."}, 429)
        except anthropic.APIConnectionError:
            self._json({"respuesta": "No logro conectarme a mis servidores, señor. Revise el internet."}, 503)
        except anthropic.APIStatusError as e:
            self._json({"respuesta": f"Hubo un error con Claude, señor: código {e.status_code}."}, 500)


def main():
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    url = f"http://localhost:{PUERTO}"
    print(f"J.A.R.V.I.S. en línea: {url}   (Ctrl+C para apagar)")
    if "--sin-navegador" not in sys.argv:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nApagando sistemas. Hasta luego, señor.")


if __name__ == "__main__":
    main()
