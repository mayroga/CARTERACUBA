import os
from flask import Flask, render_template, request, jsonify, session, send_from_directory
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
    VALOR AÑADIDO CENTRAL: Motor Cognitivo Inteligente que traduce del Español 
    al Inglés Técnico/Formal Gubernamental exigido por USCIS y agencias de EE.UU.
    Usa Gemini 1.5 Flash como principal y OpenAI GPT-4o-Mini como respaldo.
    """
    if not texto_espanol or texto_espanol.strip() == "":
        return "N/A"
        
    instruccion_sistema = (
        "Translate the following text into formal, technical English for US government immigration paperwork. "
        "Do not include any conversational filler, explanations, preambles, or notes. "
        "Provide only the direct translation, preserving dates, acronyms, or numbers exactly as given."
    )

    # --- INTENTO 1: GEMINI 1.5 FLASH (Motor Principal) ---
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt_completo = f"{instruccion_sistema}\n\nTexto original en español:\n{texto_espanol}"
            respuesta_gemini = model.generate_content(prompt_completo)
            if respuesta_gemini.text:
                return respuesta_gemini.text.strip()
        except Exception as e:
            print(f"Error en Gemini principal: {e}. Activando respaldo automático...")

    # --- INTENTO 2: OPENAI GPT-4o-MINI (Respaldo) ---
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

    # Retorno de emergencia si ambas inteligencias artificiales fallan
    return texto_espanol


@app.route('/')
def home():
    """Carga de la interfaz web adaptada para agencias automatizadas."""
    return render_template('index.html')


# ================= LOGIN DE DESARROLLADOR TRADICIONAL =================
@app.route('/login_dev', methods=['POST'])
def login_dev():
    datos = request.json or {}
    usuario_ingresado = datos.get("username", "")
    clave_ingresada = datos.get("password", "")
    if usuario_ingresado == DEV_USER and clave_ingresada == DEV_PASS:
        session['admin_logeado'] = True
        return jsonify({"status": "success", "redirect": "/panel_control_oculto"})
    else:
        return jsonify({"status": "error", "message": "Credenciales de la LLC incorrectas."})


# ================= RUTA DE VALIDACIÓN DE CREDENCIALES BYPASS DEV =================
@app.route('/api/dev_bypass', methods=['POST'])
def dev_bypass():
    """Valida de forma asíncrona el usuario y clave de Render para saltar Stripe gratis."""
    datos = request.json or {}
    usuario = datos.get("usuario", "")
    clave = datos.get("password", "")
    
    if usuario == DEV_USER and clave == DEV_PASS:
        return jsonify({"acceso": True, "mensaje": "Autenticación de desarrollador correcta."})
    else:
        return jsonify({"acceso": False, "error": "Credenciales de desarrollo incorrectas."}), 401


# ================= 1. RUTA PARA INICIAR EL COBRO CON STRIPE =================
@app.route('/api/crear_sesion_pago', methods=['POST'])
def crear_sesion_pago():
    datos = request.json or {}
    tipo_tramite = datos.get("tramite_tipo", "")
    id_precio_elegido = STRIPE_PRICE_AJUSTE if tipo_tramite == "ajuste_cubano_i485" else STRIPE_PRICE_PASAPORTE
    if not id_precio_elegido:
        return jsonify({"error": "Configuración de precio (Price ID) no encontrada en Render."}), 400
    try:
        session_checkout = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': id_precio_elegido, 'quantity': 1}],
            mode='payment',
            success_url='https://onrender.com' + tipo_tramite,
            cancel_url='https://onrender.com',
        )
        return jsonify({"url": session_checkout.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
# ================= 2. ENRUTADOR PRINCIPAL POST-PAGO Y PROCESAMIENTO =================
@app.route('/api/asistente', methods=['POST'])
def asistente():
    datos_usuario = request.json or {}
    tipo_tramite = datos_usuario.get("tramite_tipo", "ajuste_cubano_i485")
    
    os.makedirs("static/plantillas", exist_ok=True)
    os.makedirs("static/descargas", exist_ok=True)

    # ------------------ FLUJO 1: LEY DE AJUSTE CUBANO (I-485) ------------------
    if tipo_tramite == "ajuste_cubano_i485":
        apellidos = datos_usuario.get("apellidos", "").upper()
        nombre = datos_usuario.get("nombre", "").upper()
        segundo_nombre = datos_usuario.get("segundo_nombre", "").upper()
        nacimiento = datos_usuario.get("nacimiento", "")
        sexo = datos_usuario.get("sexo", "")
        ciudad_nacimiento = datos_usuario.get("ciudad_nacimiento", "").upper()
        anumber = datos_usuario.get("anumber", "")
        uscis_online = datos_usuario.get("uscis_online", "")
        
        pasaporte_num = datos_usuario.get("pasaporte_num", "").upper()
        pasaporte_exp = datos_usuario.get("pasaporte_exp", "")
        fecha_llegada = datos_usuario.get("fecha_llegada", "")
        puerto_entrada_es = datos_usuario.get("puerto_entrada", "")
        estatus_entrada_es = datos_usuario.get("estatus_entrada", "")
        empleo_usa = datos_usuario.get("empleo_usa", "").upper()
        empleo_cuba_es = datos_usuario.get("empleo", "")
        arrestado = datos_usuario.get("arrestado", "NO")
        trabajo_ilegal = datos_usuario.get("trabajo_ilegal", "NO")

        # VALOR AÑADIDO: Traducción automática con respaldo de IA al inglés técnico gubernamental
        puerto_entrada_en = traducir_texto_con_respaldo(puerto_entrada_es) if puerto_entrada_es else ""
        estatus_entrada_en = traducir_texto_con_respaldo(estatus_entrada_es) if estatus_entrada_es else ""
        empleo_cuba_en = traducir_texto_con_respaldo(empleo_cuba_es) if empleo_cuba_es else "N/A"

        ruta_plantilla = "static/plantillas/i485_base.pdf"
        nombre_archivo_salida = f"i485_{nombre}_{apellidos}.pdf".replace(" ", "_")
        ruta_salida = f"static/descargas/{nombre_archivo_salida}"

        if os.path.exists(ruta_plantilla):
            lector_pdf = PdfReader(ruta_plantilla)
            escritor_pdf = PdfWriter()
            for pagina in lector_pdf.pages:
                escritor_pdf.add_page(pagina)
                
            # Mapeo completo e inyección invisible en el PDF escribible de USCIS
            campos_mapeados_pdf = {
                "form1.#subform.Pt1Line1_FamilyName": apellidos,
                "form1.#subform.Pt1Line1_GivenName": nombre,
                "form1.#subform.Pt1Line1_MiddleName": segundo_nombre,
                "form1.#subform.Pt1Line3_DOB": nacimiento,
                "form1.#subform.AlienNumber": anumber if anumber else "",
                "form1.#subform.Pt1Line4_AlienNumber": anumber if anumber else "",
                "form1.#subform.Pt1Line7_CountryOfBirth": "CUBA",
                "form1.#subform.Pt1Line8_CountryofCitizenshipNationality": "CUBA",
                "form1.#subform.CityOfBirth": ciudad_nacimiento,
                "form1.#subform.Gender": sexo,
                "form1.#subform.USCISOnlineNumber": uscis_online,
                "form1.#subform.PassportNumber": pasaporte_num,
                "form1.#subform.PassportExp": pasaporte_exp,
                "form1.#subform.DateOfLastArrival": fecha_llegada,
                "form1.#subform.PortOfEntry": puerto_entrada_en,
                "form1.#subform.StatusAtArrival": estatus_entrada_en,
                "form1.#subform.CurrentEmployer": empleo_usa,
                "form1.#subform.JobHistoryCuba": empleo_cuba_en,
                "form1.#subform.ArrestedCheck": arrestado,
                "form1.#subform.IllegalWorkCheck": trabajo_ilegal
            }
            try:
                escritor_pdf.update_page_form_field_values(escritor_pdf.pages, campos_mapeados_pdf)
                with open(ruta_salida, "wb") as archivo_salida:
                    escritor_pdf.write(archivo_salida)
                url_descarga = f"/static/descargas/{nombre_archivo_salida}"
            except Exception as error_pdf:
                print(f"Error crítico al estampar PDF de Ajuste: {error_pdf}")
                url_descarga = f"/{ruta_plantilla}"
        else:
            url_descarga = "#"
            
        instrucciones_cliente = f"""
        <strong>Formulario I-485 Automatizado y Traducido Exitosamente</strong><br>
        • <strong>Solicitante:</strong> {nombre} {segundo_nombre} {apellidos}<br>
        • <strong>Traducción de Ocupación en Cuba:</strong> {empleo_cuba_en}<br>
        • <strong>Puerto de Entrada Traducido:</strong> {puerto_entrada_en}<br><br>
        <em>Toda su información fue mecanografiada por el motor inteligente. Descargue su documento, verifique los datos inyectados, imprímalo y firme a mano con tinta negra en la casilla correspondiente.</em>
        """
        return jsonify({"respuesta": instrucciones_cliente, "archivo_url": url_descarga})

    # ------------------ FLUJO 2: PASAPORTE CUBANO CONSULAR ------------------
    elif tipo_tramite == "pasaporte_cubano_consular":
        nombre = datos_usuario.get("nombre", "").upper()
        apellidos = datos_usuario.get("apellidos", "").upper()
        tipo_solicitud = datos_usuario.get("tipo", "").upper()
        pasaporte_num = datos_usuario.get("pasaporte_num", "").upper()
        provincia = datos_usuario.get("provincia", "").upper()
        salida_cuba = datos_usuario.get("salida_cuba", "")
        
        ruta_plantilla_pasaporte = "static/plantillas/pasaporte_cuba_base.pdf"
        nombre_archivo_pasaporte = f"solicitud_pasaporte_{nombre}_{apellidos}.pdf".replace(" ", "_")
        ruta_salida_pasaporte = f"static/descargas/{nombre_archivo_pasaporte}"
        
        if os.path.exists(ruta_plantilla_pasaporte):
            lector_pdf = PdfReader(ruta_plantilla_pasaporte)
            escritor_pdf = PdfWriter()
            for pagina in lector_pdf.pages:
                escritor_pdf.add_page(pagina)
                
            campos_pasaporte_pdf = {
                "Nombres": nombre,
                "Apellidos": apellidos,
                "TipoTramite": tipo_solicitud,
                "NoPasaporte": pasaporte_num if pasaporte_num else "N/A",
                "ProvinciaNacimiento": provincia,
                "FechaSalidaCuba": salida_cuba
            }
            try:
                escritor_pdf.update_page_form_field_values(escritor_pdf.pages, campos_pasaporte_pdf)
                with open(ruta_salida_pasaporte, "wb") as archivo_salida:
                    escritor_pdf.write(archivo_salida)
                url_descarga = f"/static/descargas/{nombre_archivo_pasaporte}"
            except Exception as error_pdf:
                print(f"Error crítico al estampar PDF de Pasaporte: {error_pdf}")
                url_descarga = f"/{ruta_plantilla_pasaporte}"
        else:
            url_descarga = "#"
            
        instrucciones_pasaporte = f"""
        <strong>Planilla Consular de Cuba Automatizada</strong><br>
        • <strong>Solicitante:</strong> {nombre} {apellidos}<br>
        • <strong>Servicio Consular Solicitado:</strong> {tipo_solicitud}<br><br>
        <em>El formulario oficial se encuentra completamente rellenado por el sistema con sus datos normalizados. Descargue el archivo, imprímalo, adhiera su foto fondo blanco y firme únicamente dentro del recuadro con tinta negra sin tocar los bordes.</em>
        """
        return jsonify({"respuesta": instrucciones_pasaporte, "archivo_url": url_descarga})
        
    return jsonify({"error": "Tipo de trámite no reconocido por el sistema."}), 400


# ================= 3. MANEJO CENTRALIZADO DE DESCARGAS =================
@app.route('/static/descargas/<path:filename>')
def descargar_archivo(filename):
    """Obliga al navegador del cliente a descargar el archivo en vez de abrir una pestaña rota."""
    return send_from_directory('static/descargas', filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
