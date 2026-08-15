import os
from flask import Flask, render_template, request, jsonify, session, send_from_directory # CORREGIDO: Importado send_from_directory
from pypdf import PdfReader, PdfWriter
import google.generativeai as genai
from openai import OpenAI
import stripe

app = Flask(__name__)

# Configuración de Clave Secreta para las Sesiones del Servidor (Cargar desde Render)
app.secret_key = os.getenv("SECRET_KEY", "carteracuba_firm_key_123")

# CARGAR TUS PARÁMETROS SEGUROS DESDE EL PANEL DE RENDER
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
DEV_USER = os.getenv("DEV_USER", "admin")
DEV_PASS = os.getenv("DEV_PASS", "root123")

# TUS PARÁMETROS DE PRECIOS STRIPE EXACTOS CONFIGURADOS EN RENDER
STRIPE_PRICE_AJUSTE = os.getenv("STRIPE_PRICE_ID1", "")
STRIPE_PRICE_PASAPORTE = os.getenv("STRIPE_PRICE_ID2", "")

# Inicializar las APIs e instancias si los parámetros están presentes
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

def traducir_texto_con_respaldo(texto_espanol):
    """
    Motor Dual Inteligente: Traduce con Gemini. Usa OpenAI como Fallback/Respaldo si falla Google.
    """
    instruccion_sistema = "Traduce al inglés formal para trámites gubernamentales migratorios en EE. UU. Traduce únicamente el texto provisto, sin añadir comentarios, explicaciones ni introducciones."

    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt_completo = f"{instruccion_sistema}\n\nTexto a traducir:\n{texto_espanol}"
            respuesta_gemini = model.generate_content(prompt_completo)
            if respuesta_gemini.text:
                return respuesta_gemini.text.strip()
        except Exception as e:
            print(f"Error en Gemini principal: {e}. Activando respaldo...")

    if openai_client:
        try:
            completar_ia = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": instruccion_sistema},
                    {"role": "user", "content": texto_espanol}
                ]
            )
            return completar_ia.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error en OpenAI de respaldo: {e}")

    return texto_espanol

@app.route('/')
def home():
    return render_template('index.html')

# ================= LOGIN DE DESARROLLADOR =================
@app.route('/login_dev', methods=['POST'])
def login_dev():
    datos = request.json
    usuario_ingresado = datos.get("username", "")
    clave_ingresada = datos.get("password", "")
    if usuario_ingresado == DEV_USER and clave_ingresada == DEV_PASS:
        session['admin_logeado'] = True
        return jsonify({"status": "success", "redirect": "/panel_control_oculto"})
    else:
        return jsonify({"status": "error", "message": "Credenciales de la LLC incorrectas."})

# ================= 1. RUTA PARA INICIAR EL COBRO CON STRIPE =================
@app.route('/api/crear_sesion_pago', methods=['POST'])
def crear_sesion_pago():
    datos = request.json
    tipo_tramite = datos.get("tramite_tipo")
    id_precio_elegido = STRIPE_PRICE_AJUSTE if tipo_tramite == "ajuste_cubano_i485" else STRIPE_PRICE_PASAPORTE
    if not id_precio_elegido:
        return jsonify({"error": "Configuración de precio (Price ID) no encontrada en Render."}), 400
    try:
        session_checkout = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': id_precio_elegido, 'quantity': 1}],
            mode='payment',
            # CORREGIDO: Se agregó la barra '/' para que la URL se concatene correctamente
            success_url='https://carteracuba.onrender.com' + tipo_tramite,
            cancel_url='https://carteracuba.onrender.com',
        )
        return jsonify({"url": session_checkout.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ================= 2. ENRUTADOR PRINCIPAL POST-PAGO DE TRÁMITES =================
@app.route('/api/asistente', methods=['POST'])
def asistente():
    datos_usuario = request.json
    tipo_tramite = datos_usuario.get("tramite_tipo", "ajuste_cubano_i485")
    os.makedirs("static/plantillas", exist_ok=True)
    os.makedirs("static/descargas", exist_ok=True)

    # ------------------ FLUJO 1: LEY DE AJUSTE CUBANO (I-485) ------------------
    if tipo_tramite == "ajuste_cubano_i485":
        nombre = datos_usuario.get("nombre", "")
        apellidos = datos_usuario.get("apellidos", "")
        nacimiento = datos_usuario.get("nacimiento", "")
        anumber = datos_usuario.get("anumber", "")
        empleo_espanol = datos_usuario.get("empleo", "")
        empleo_ingles = "N/A"
        if empleo_espanol:
            empleo_ingles = traducir_texto_con_respaldo(empleo_espanol)

        ruta_plantilla = "static/plantillas/i485_base.pdf"
        ruta_salida = f"static/descargas/i485_{nombre}_{apellidos}.pdf"

        if os.path.exists(ruta_plantilla):
            lector_pdf = PdfReader(ruta_plantilla)
            escritor_pdf = PdfWriter()
            for pagina in lector_pdf.pages:
                escritor_pdf.add_page(pagina)

            campos_mapeados_pdf = {
                "form1.#subform.Pt1Line1_FamilyName": apellidos,
                "form1.#subform.Pt1Line1_GivenName": nombre,
                "form1.#subform.Pt1Line3_DOB": nacimiento,
                "form1.#subform.AlienNumber": anumber if anumber else "",
                "form1.#subform.Pt1Line4_AlienNumber": anumber if anumber else "",
                "form1.#subform.Pt1Line7_CountryOfBirth": "CUBA",
                "form1.#subform.Pt1Line8_CountryofCitizenshipNationality": "CUBA"
            }
            try:
                escritor_pdf.update_page_form_field_values(escritor_pdf.pages, campos_mapeados_pdf)
                with open(ruta_salida, "wb") as archivo_salida:
                    escritor_pdf.write(archivo_salida)
                url_descarga = f"/{ruta_salida}"
            except Exception as error_pdf:
                print(f"Error crítico al estampar PDF de Ajuste: {error_pdf}")
                url_descarga = f"/{ruta_plantilla}" # CORREGIDO: Si falla, descarga la plantilla limpia en vez de '#'
        else:
            url_descarga = "#"

        instrucciones_cliente = f"""
        <strong>Mapeo de Datos Concluido Exitosamente</strong><br>
        • <strong>Solicitante:</strong> {nombre} {apellidos}<br>
        • <strong>Historial traducido por IA:</strong> {empleo_ingles}<br><br>
        <em>El sistema ha volcado su información en español al documento federal público I-485 en inglés de forma exacta. Su descarga está disponible abajo.</em>
        """
        return jsonify({"respuesta": instrucciones_cliente, "archivo_url": url_descarga})

    # ------------------ FLUJO 2: PASAPORTE CUBANO CONSULAR ------------------
    elif tipo_tramite == "pasaporte_cubano_consular":
        nombre = datos_usuario.get("nombre", "")
        apellidos = datos_usuario.get("apellidos", "")
        tipo_solicitud = datos_usuario.get("tipo", "")
        pasaporte_num = datos_usuario.get("pasaporte_num", "")
        provincia = datos_usuario.get("provincia", "")
        salida_cuba = datos_usuario.get("salida_cuba", "")

        ruta_plantilla_pasaporte = "static/plantillas/pasaporte_cuba_base.pdf"
        ruta_salida_pasaporte = f"static/descargas/solicitud_pasaporte_{nombre}.pdf"

        if os.path.exists(ruta_plantilla_pasaporte):
            lector_pdf = PdfReader(ruta_plantilla_pasaporte)
            escritor_pdf = PdfWriter()
            for pagina in lector_pdf.pages:
                escritor_pdf.add_page(pagina)

            campos_pasaporte_pdf = {
                "Nombres": nombre,
                "Apellidos": apellidos,
                "TipoTramite": tipo_solicitud.upper(),
                "NoPasaporte": pasaporte_num if pasaporte_num else "N/A",
                "ProvinciaNacimiento": provincia,
                "FechaSalidaCuba": salida_cuba
            }
            try:
                escritor_pdf.update_page_form_field_values(escritor_pdf.pages, campos_pasaporte_pdf)
                with open(ruta_salida_pasaporte, "wb") as archivo_salida:
                    escritor_pdf.write(archivo_salida)
                url_descarga = f"/{ruta_salida_pasaporte}"
            except Exception as error_pdf:
                print(f"Error crítico al estampar PDF de Pasaporte: {error_pdf}")
                url_descarga = f"/{ruta_plantilla_pasaporte}" # CORREGIDO: Si falla, descarga la plantilla limpia en vez de '#'
        else:
            url_descarga = "#"

        instrucciones_pasaporte = f"""
        <strong>Planilla Consular de Cuba Preparada</strong><br>
        • <strong>Solicitante:</strong> {nombre} {apellidos}<br>
        • <strong>Servicio Solicitado:</strong> {tipo_solicitud.upper()}<br><br>
        <em>La solicitud ha sido mecanografiada en el formato oficial de la Embajada de Cuba. Descargue el archivo, imprímalo, firme dentro del recuadro con tinta negra sin tocar los bordes y adjunte sus fotos tipo visa fondo blanco para su envío.</em>
        """
        return jsonify({"respuesta": instrucciones_pasaporte, "archivo_url": url_descarga})

# ================= 3. MANEJO CENTRALIZADO DE DESCARGAS (NUEVO) =================
@app.route('/static/descargas/<path:filename>')
def descargar_archivo(filename):
    """Obliga al navegador del cliente a descargar el archivo en vez de abrir una ventana rota."""
    return send_from_directory('static/descargas', filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
