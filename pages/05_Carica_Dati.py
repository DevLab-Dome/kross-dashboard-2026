import streamlit as st
import pandas as pd
import boto3
import json
from botocore.exceptions import NoCredentialsError

st.set_page_config(page_title="Carica Dati", layout="centered")

st.title("☁️ Caricamento Dati su Cloud")

# --- 1. RECUPERO CREDENZIALI ---
try:
    if "digitalocean" in st.secrets:
        secrets = st.secrets["digitalocean"]
    else:
        secrets = st.secrets

    DO_ACCESS_KEY = secrets.get("access_key")
    DO_SECRET_KEY = secrets.get("secret_key")
    DO_REGION = secrets.get("region", "sfo3")
    DO_ENDPOINT = secrets.get("endpoint", "https://sfo3.digitaloceanspaces.com")
    DO_BUCKET = secrets.get("bucket_name", "ihosp-kross-archive")

    if not DO_ACCESS_KEY or not DO_SECRET_KEY:
        st.error("❌ Chiavi non trovate nei Secrets.")
        st.stop()
except Exception as e:
    st.error(f"❌ Errore Secrets: {e}")
    st.stop()

def get_s3_client():
    session = boto3.session.Session()
    return session.client('s3', region_name=DO_REGION, endpoint_url=DO_ENDPOINT,
                          aws_access_key_id=DO_ACCESS_KEY, aws_secret_access_key=DO_SECRET_KEY)

# --- 2. INTERFACCIA DI SELEZIONE (PRIMA DEL FILE) ---
st.subheader("1. Impostazioni Destinazione")

col1, col2 = st.columns(2)

with col1:
    # Scelta Cartella Macro
    folder_type = st.radio("Tipo di Caricamento:", ["Forecast", "History_Baseline"], index=0)

with col2:
    # Scelta Struttura
    structure_map = {
        "Lavagnini My Place": "Lavagnini", 
        "La Terrazza di Jenny": "La_Terrazza", 
        "B&B Pitti Palace": "Pitti_Palace"
    }
    selected_label = st.selectbox("Seleziona Struttura:", list(structure_map.keys()))
    folder_struct = structure_map[selected_label]

st.divider()

# --- 3. UPLOAD FILE ---
st.subheader("2. Seleziona File Excel")
uploaded_file = st.file_uploader("Trascina qui il file forecast (es. Forecast_Lavagnini_08022026.xlsx)", type=["xlsx", "xls"])

if uploaded_file:
    # Logica Anno Automatica (dal nome file)
    current_year = 2026 # Default
    if "2025" in uploaded_file.name: current_year = 2025
    if "2024" in uploaded_file.name: current_year = 2024
    if "2023" in uploaded_file.name: current_year = 2023

    st.info(f"📅 Anno rilevato dal file: **{current_year}**")
    
    # Percorso finale
    target_path = f"{folder_type}/{folder_struct}/{current_year}/{uploaded_file.name}"
    
    if st.button("🚀 Conferma e Carica"):
        s3 = get_s3_client()
        index_path = f"{folder_type}/{folder_struct}/{current_year}/index.json"
        
        with st.spinner("Caricamento in corso..."):
            try:
                # A. Upload File
                s3.upload_fileobj(uploaded_file, DO_BUCKET, target_path, ExtraArgs={'ACL': 'public-read'})
                st.success(f"✅ File caricato correttamente in: {target_path}")
                
                # B. Aggiornamento Indice
                file_list = []
                try:
                    obj = s3.get_object(Bucket=DO_BUCKET, Key=index_path)
                    file_list = json.loads(obj['Body'].read().decode('utf-8'))
                except:
                    pass
                
                if uploaded_file.name not in file_list:
                    file_list.append(uploaded_file.name)
                    file_list.sort(reverse=True) # Ordine decrescente
                    
                    s3.put_object(
                        Bucket=DO_BUCKET,
                        Key=index_path,
                        Body=json.dumps(file_list),
                        ACL='public-read',
                        ContentType='application/json'
                    )
                    st.info("🔄 Indice Cloud aggiornato.")
                    
            except Exception as e:
                st.error(f"Errore Upload: {e}")
