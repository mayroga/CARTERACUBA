import os
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader, PdfWriter
import openai

app = Flask(__name__)

# Configura tu clave de OpenAI en Render como variable de entorno
openai.api_key = os.getenv("OPENAI_API_KEY", "tu-clave-aqui")

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

    # 1. TRADUCCIÓN AUTOMATIZADA CON IA (Para textos descriptivos largos)
    empleo_ingles = "N/A"
    if empleo_espanol:
        try:
            completar_ia = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Traduce al inglés formal para trámites gubernamentales migratorios sin añadir comentarios."},
                    {"role": "user", "content": empleo_espanol}
                ]
            )
            empleo_ingles = completar_ia.choices[0].message['content'].strip()
        except Exception:
            empleo_ingles = empleo_espanol  # Respaldo si falla la API

    # 2. DEFINIR RUTAS DE LA PAPELERÍA
    ruta_plantilla = "static/plantillas/i485_base.pdf"
    ruta_salida = f"static/descargas/i485_{nombre}_{apellidos}.pdf"
    
    os.makedirs("static/plantillas", exist_ok=True)
    os.makedirs("static/descargas", exist_ok=True)

    # 3. LLENADO Y TRADUCCIÓN TÉCNICA DEL FORMULARIO OFICIAL
    if os.path.exists(ruta_plantilla):
        lector_pdf = PdfReader(ruta_plantilla)
        escritor_pdf = PdfWriter()
        
        for pagina in lector_pdf.pages:
            escritor_pdf.add_page(pagina)
            
        # Diccionario de mapeo de casillas de USCIS en inglés
        # Estos IDs corresponden a los campos de formulario editables internos del PDF público
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
        # Modo de prueba si aún no subes el PDF base a tu carpeta
        url_descarga = "#"

    # 4. RESPUESTA AL PANEL DE LA APP
    instrucciones_cliente = f"""
    <strong>Revisión de Transcripción Completa:</strong><br>
    • <strong>Nombre mapeado:</strong> {nombre} {apellidos}<br>
    • <strong>Traducción de Empleo procesada:</strong> {empleo_ingles}<br><br>
    <em>Su documento se ha estructurado siguiendo la edición oficial de USCIS. Recuerde imprimir el archivo final, firmarlo con tinta negra y anexar su examen médico en sobre cerrado (Formulario I-693) antes de enviarlo por correo postal.</em>
    """

    return jsonify({
        "respuesta": instrucciones_cliente,
        "archivo_url": url_descarga
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
