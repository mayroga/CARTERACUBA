import os
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader, PdfWriter
import google.generativeai as genai
import openai

app = Flask(__name__)

# Configuración de credenciales seguras (Variables de Entorno en Render)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Inicializar las APIs si las llaves están presentes
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

def traducir_texto_con_respaldo(texto_espanol):
    """
    Intenta traducir primero con Gemini. 
    Si falla, utiliza OpenAI como respaldo automático.
    """
    instruccion_sistema = "Traduce al inglés formal para trámites gubernamentales migratorios en EE. UU. Traduce únicamente el texto provisto, sin agregar comentarios, explicaciones ni introducciones."
    
    # --- INTENTO 1: GEMINI (Motor Principal) ---
    if GEMINI_API_KEY:
        try:
            # Usamos el modelo estándar y rápido para tareas de texto
            model = genai.GenerativeModel('gemini-pro')
            prompt_completo = f"{instruccion_sistema}\n\nTexto a traducir:\n{texto_espanol}"
            respuesta_gemini = model.generate_content(prompt_completo)
            if respuesta_gemini.text:
                return respuesta_gemini.text.strip()
        except Exception as e:
            print(f"Gemini falló: {e}. Iniciando respaldo con OpenAI...")

    # --- INTENTO 2: OPENAI (Respaldo) ---
    if OPENAI_API_KEY:
        try:
            completar_ia = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": instruccion_sistema},
                    {"role": "user", "content": texto_espanol}
                ]
            )
            return completar_ia.choices.message['content'].strip()
        except Exception as e:
            print(f"OpenAI también falló: {e}")
            
    # Si ambas APIs fallan o no hay llaves configuradas, devuelve el texto original
    return texto_espanol

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/asistente', methods=['POST'])
def asistente():
    datos_usuario = request.json
    
    nombre = datos_usuario.get("nombre", "")
    apellidos = datos_usuario.get("apellidos", "")
    nacimiento = datos_usuario.get("nacimiento", "")
    anumber = datos_usuario.get("anumber", "")
    empleo_espanol = datos_usuario.get("empleo", "")

    # Ejecutar la traducción inteligente con el sistema de respaldo
    empleo_ingles = "N/A"
    if empleo_espanol:
        empleo_ingles = traducir_texto_con_respaldo(empleo_espanol)

    # Definir rutas internas del servidor
    ruta_plantilla = "static/plantillas/i485_base.pdf"
    ruta_salida = f"static/descargas/i485_{nombre}_{apellidos}.pdf"
    
    os.makedirs("static/plantillas", exist_ok=True)
    os.makedirs("static/descargas", exist_ok=True)

    # Llenado técnico del formulario interactivo oficial en inglés
    if os.path.exists(ruta_plantilla):
        lector_pdf = PdfReader(ruta_plantilla)
        escritor_pdf = PdfWriter()
        
        for pagina in lector_pdf.pages:
            escritor_pdf.add_page(pagina)
            
        campos_mapeados_pdf = {
            "Part1_FamilyName": apellidos,
            "Part1_GivenName": nombre,
            "Part1_DOB": nacimiento,
            "Part1_ANumber": anumber if anumber else "None",
            "Part1_CountryOfBirth": "CUBA",
            "Part1_EmploymentHistory": empleo_ingles
        }
        
        escritor_pdf.update_page_form_field_values(escritor_pdf.pages, campos_mapeados_pdf)
        
        with open(ruta_salida, "wb") as archivo_salida:
            escritor_pdf.write(archivo_salida)
            
        url_descarga = f"/{ruta_salida}"
    else:
        url_descarga = "#"

    # Preparar el texto de resolución limpia para la pantalla azul de la app
    instrucciones_cliente = f"""
    <strong>Revisión de Transcripción Completa:</strong><br>
    • <strong>Nombre del solicitante:</strong> {nombre} {apellidos}<br>
    • <strong>Traducción de Ocupación (Inglés):</strong> {empleo_ingles}<br><br>
    <em>Su Formulario I-485 público ha sido rellenado en inglés de forma automatizada por nuestro sistema. Por favor, descargue el documento, imprímalo y verifique que toda la información dictada coincida exactamente con sus documentos oficiales.</em>
    """

    return jsonify({
        "respuesta": instrucciones_cliente,
        "archivo_url": url_descarga
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
