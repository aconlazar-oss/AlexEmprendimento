# J.A.R.V.I.S. — tu asistente personal con Claude

Un asistente de voz estilo Iron Man que corre en tu computadora. Le hablas desde el navegador,
te responde en voz alta, te ayuda con el negocio de huevos y controla tu PC.

## Qué puede hacer

**Negocio**
- "Jarvis, ¿cuántas bandejas tengo que vender para ganar 300 soles al día vendiendo solo a bodegas?"
- "Registra una venta de 15 bandejas a 13 soles con 50 a la bodega Rosa."
- "Compré 2 jabas a 140 soles cada una." · "¿Cómo me fue esta semana?"
- "El precio en la granja subió a 6 soles el kilo." (actualiza los supuestos de la calculadora)

**PC**
- "Abre Excel" · "Abre YouTube" · "Busca en Google el precio del huevo en Lima"
- "Abre mi calculadora de huevos" · "Abre la carpeta de descargas"
- "Anota que mañana debo llamar a la granja de Huaral"
- "Recuérdame en 20 minutos salir a repartir"

## Instalación (una sola vez)

1. Instala [Python 3.10 o superior](https://www.python.org/downloads/) (en Windows marca *Add Python to PATH*).
2. Crea una clave de API en <https://platform.claude.com> → *API Keys*.
3. Guárdala como variable de entorno `ANTHROPIC_API_KEY`:
   - Windows (PowerShell): `setx ANTHROPIC_API_KEY "sk-ant-..."` y cierra/abre la terminal.
   - Mac/Linux: agrega `export ANTHROPIC_API_KEY="sk-ant-..."` a tu `~/.bashrc` o `~/.zshrc`.

## Usarlo

- Windows: doble clic en `iniciar.bat`
- Mac/Linux: `./iniciar.sh`

Se abre `http://localhost:8000` en el navegador. Usa **Google Chrome o Microsoft Edge** (son los que reconocen voz).

- Toca el reactor o presiona **espacio** para hablar.
- **Modo "Jarvis"**: queda escuchando siempre y responde cuando empiezas la frase con "Jarvis…".
- También puedes escribir abajo.

## Cómo está hecho

| Archivo | Qué hace |
|---|---|
| `servidor.py` | Servidor local (solo accesible desde tu PC) |
| `cerebro.py` | Personalidad de Jarvis y conversación con Claude (modelo `claude-opus-5-5`) |
| `negocio.py` | Cálculos y registro de ventas; replica la hoja `analisis/calculadora_huevos.xlsx` |
| `pc.py` | Abrir apps, webs, carpetas, notas y recordatorios |
| `static/index.html` | Interfaz HUD con reconocimiento y síntesis de voz del navegador |

Tus ventas, notas y supuestos se guardan en `jarvis/datos/` (no se suben a git).

**Agregar programas:** edita el diccionario `APPS` (o `SITIOS`) en `pc.py`.
Por seguridad Jarvis no ejecuta comandos libres, solo lo que esté en esas listas.

**Costo:** cada mensaje consume tokens de la API de Claude. Jarvis usa esfuerzo bajo para responder rápido;
una conversación normal cuesta centavos. Revisa tu consumo en la consola de Anthropic.
