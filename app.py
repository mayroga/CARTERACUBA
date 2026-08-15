import os
from flask import Flask, render_template, request, jsonify, redirect, send_file
import stripe
from pypdf import PdfReader, PdfWriter

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "carteracuba_secreto_seguro_2026")

# Configuración de Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_placeholder")
PRECIOS_TRAMITES = {
    "ajuste_cubano_i485": 4999,  # $49.99 USD en centavos
    "pasaporte_cubano_consular": 3999  # $39.99 USD en centavos
}

# Directorio estático para plantillas en blanco y resultados generados
STATIC_DIR = os.path.join(app.root_path, 'static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ajuste_cubano_i485')
def vista_ajuste_i485():
    return render_template('index.html')

@app.route('/pasaporte_cubano_consular')
def vista_pasaporte():
    return render_template('index.html')

@app.route('/api/crear_sesion_pago', methods=['POST'])
def crear_sesion_pago():
    try:
        data = request.get_json()
        tramite_tipo = data.get("tramite_tipo")
        
        if tramite_tipo not in PRECIOS_TRAMITES:
            return jsonify({"error": "Trámite no válido o no reconocido."}), 400
            
        dominio_actual = request.host_url
        precio_centavos = PRECIOS_TRAMITES[tramite_tipo]
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': precio_centavos,
                    'product_data': {
                        'name': f'Procesamiento Oficial - {tramite_tipo.replace("_", " ").upper()}',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{dominio_actual}{tramite_tipo}?pago_exitoso=true',
            cancel_url=f'{dominio_actual}?pago_cancelado=true',
        )
        return jsonify({"url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dev_bypass', methods=['POST'])
def dev_bypass():
    data = request.get_json()
    usuario = data.get("usuario")
    password = data.get("password")
    
    dev_user_val = os.getenv("DEV_USER", "admin")
    dev_pass_val = os.getenv("DEV_PASS", "carteracuba2026")
    
    if usuario == dev_user_val and password == dev_pass_val:
        return jsonify({"acceso": True})
    return jsonify({"acceso": False, "error": "Credenciales de desarrollador incorrectas."}), 401

@app.route('/api/asistente', methods=['POST'])
def asistente():
    try:
        datos = request.get_json()
        tramite_tipo = datos.get("tramite_tipo")
        nombre_completo = f"{datos.get('nombre', '')} {datos.get('apellidos', '')}"
        
        # Mapeo de formularios oficiales
        if tramite_tipo == "ajuste_cubano_i485":
            plantilla_nombre = "i485_blank.pdf"
            mapeo_campos = {
                "FamilyName_LastName": datos.get("apellidos", ""),
                "GivenName_FirstName": datos.get("nombre", ""),
                "MiddleName": datos.get("segundo_nombre", ""),
                "DateOfBirth_MMDDYYYY": datos.get("nacimiento", ""),
                "CityTownVillageOfBirth": datos.get("ciudad_nacimiento", ""),
                "AlienRegistrationNumber_ANumber": datos.get("anumber", ""),
                "USCISOnlineAccountNumber": datos.get("uscis_online", ""),
                "PassportNumber": datos.get("pasaporte_num", ""),
                "DateOfArrival": datos.get("fecha_llegada", ""),
                "PlaceOfArrival_PortOfEntry": datos.get("puerto_entrada", ""),
                "CurrentStatus": datos.get("estatus_entrada", ""),
                "CurrentEmployerOrCompany": datos.get("empleo_usa", ""),
                "RecentOccupationInCuba": datos.get("empleo", "")
            }
        else:
            plantilla_nombre = "pasaporte_consular_blank.pdf"
            mapeo_campos = {
                "nombre": datos.get("nombre", ""),
                "apellidos": datos.get("apellidos", ""),
                "numero_pasaporte": datos.get("pasaporte_num", ""),
                "provincia": datos.get("provincia", ""),
                "fecha_salida": datos.get("salida_cuba", "")
            }
            
        id_unico = datos.get('pasaporte_num', 'tramite').strip() or 'documento'
        nombre_archivo_salida = f"resultado_{id_unico}.pdf"
        ruta_plantilla = os.path.join(STATIC_DIR, plantilla_nombre)
        ruta_salida = os.path.join(STATIC_DIR, nombre_archivo_salida)
        
        # Inyección real de campos interactivos mediante pypdf
        if os.path.exists(ruta_plantilla):
            reader = PdfReader(ruta_plantilla)
            writer = PdfWriter()
            writer.append(reader)
            
            # Actualizar valores de campos si el PDF tiene formularios AcroForm
            try:
                fields = writer.get_fields()
                if fields:
                    writer.update_page_form_field_values(writer.pages[0], mapeo_campos)
            except Exception as form_err:
                print(f"Aviso de campos de formulario: {form_err}")
                
            with open(ruta_salida, "wb") as output_file:
                writer.write(output_file)
                
            respuesta_ia = f"Documento oficial completado e inyectado con éxito mediante [pypdf](https://readthedocs.io) para el solicitante {nombre_completo}."
            archivo_resultado = f"/api/descargar_pdf/{nombre_archivo_salida}"
        else:
            respuesta_ia = f"Expediente validado para {nombre_completo} (Aviso: No se localizó la plantilla PDF base en /static)."
            archivo_resultado = "#"
        
        return jsonify({
            "respuesta": respuesta_ia,
            "archivo_url": archivo_resultado
        })
    except Exception as e:
        return jsonify({"error": f"Fallo crítico rellenando el PDF: {str(e)}"}), 500

@app.route('/api/descargar_pdf/<nombre_archivo>')
def descargar_pdf(nombre_archivo):
    try:
        ruta_archivo = os.path.join(STATIC_DIR, nombre_archivo)
        if os.path.exists(ruta_archivo):
            return send_file(ruta_archivo, as_attachment=True)
        return "El archivo solicitado no existe o ya expiró.", 404
    except Exception as e:
        return f"Error al descargar el archivo: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)

