import streamlit as st
import pandas as pd
import redis
import google.generativeai as genai
import os
import json

# Configuración de página
st.set_page_config(page_title="Analizador CSV con Gemini y Redis", layout="wide")

st.title("📊 Explorador de Datos con Redis y Gemini")

# Inicialización del cliente de Redis (Redis SDK para Python)
@st.cache_resource
def get_redis_client():
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    redis_username = os.environ.get("REDIS_USERNAME", "default")
    redis_password = os.environ.get("REDIS_PASSWORD", None)
    
    return redis.Redis(
        host=redis_host, 
        port=redis_port, 
        decode_responses=True,
        username=redis_username,
        password=redis_password
    )

try:
    r = get_redis_client()
    r.ping() # Probamos conexión
    st.sidebar.success("✅ Conectado a Redis")
except Exception as e:
    st.sidebar.error(f"❌ Error conectando a Redis: {e}")
    st.stop()

# Configuración de Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key or api_key == "tu_api_key_aqui":
    st.warning("⚠️ No se ha detectado la GEMINI_API_KEY en el entorno. Por favor, asegúrate de configurarla en el archivo .env")
else:
    genai.configure(api_key=api_key)
    st.sidebar.success("✅ Gemini API configurada")

def analyze_with_gemini(metadata_str):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Eres un analista de datos experto. Se ha subido un dataset y a continuación se te proporciona su estructura, columnas, tipos de datos y una pequeña muestra de las primeras filas.
    
    Información del Dataset:
    {metadata_str}
    
    Por favor, proporciona:
    1. Un Resumen Ejecutivo de qué trata probablemente este dataset.
    2. Un análisis breve de la estructura de los datos y cualquier posible problema de calidad que notes a simple vista.
    3. Tres sugerencias de análisis o preguntas que se podrían responder con estos datos.
    
    Responde en español de forma estructurada usando Markdown.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error en la API de Gemini: {e}"

# Interfaz de subida
uploaded_file = st.file_uploader("Sube tu archivo CSV para análisis", type=["csv"])

if uploaded_file is not None:
    # 1. Leemos el archivo a un DataFrame
    df = pd.read_csv(uploaded_file)
    
    # 2. Guardamos en Redis
    file_id = uploaded_file.name
    # Convertimos el dataframe a JSON para almacenarlo como un string en Redis (podría ser binario con pickle también)
    df_json = df.to_json(orient='records')
    
    # Almacenamos temporalmente en Redis (expira en 1 hora = 3600 segundos)
    r.setex(f"dataset:{file_id}", 3600, df_json)
    st.success(f"✅ Archivo `{file_id}` guardado temporalmente en Redis.")
    
    st.divider()
    
    # 3. Recuperamos y exploramos los datos
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Exploración de Datos (desde Redis)")
        
        # Recuperamos desde Redis para demostrar el flujo
        cached_data = r.get(f"dataset:{file_id}")
        if cached_data:
            cached_df = pd.read_json(cached_data, orient='records')
            
            st.write("Vista previa de los datos:")
            st.dataframe(cached_df.head())
            
            st.write("Información de las columnas:")
            # Preparamos un string resumen para Gemini
            buffer = []
            buffer.append(f"Número de filas: {len(cached_df)}")
            buffer.append(f"Número de columnas: {len(cached_df.columns)}")
            buffer.append("\nTipos de datos por columna:")
            for col in cached_df.columns:
                 buffer.append(f"- {col}: {cached_df[col].dtype}")
            buffer.append("\nMuestra de las primeras 3 filas (en formato JSON):")
            buffer.append(cached_df.head(3).to_json(orient='records'))
            
            dataset_metadata = "\n".join(buffer)
            
            with st.expander("Ver Metadata extraída"):
                st.text(dataset_metadata)
    
    with col2:
        st.subheader("✨ Resumen Ejecutivo por Gemini")
        if not api_key or api_key == "tu_api_key_aqui":
            st.error("Configura tu API KEY en el .env para usar esta función.")
        else:
            with st.spinner("Gemini está analizando la estructura..."):
                analysis_result = analyze_with_gemini(dataset_metadata)
                st.markdown(analysis_result)

