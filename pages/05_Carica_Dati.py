import streamlit as st
import pandas as pd
import boto3
import json
import io
from botocore.exceptions import NoCredentialsError

st.set_page_config(page_title="Carica Dati", layout="centered")

st.title("☁️ Caricamento Dati su Cloud")

# --- 1. RECUPERO CREDENZIALI (ROBUSTO) ---
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

# --- 2. CONNESSIONE BOTO3 ---
def get_s3_client():
    session = boto3.session.Session()
    return session.client('s3',
                          region_name=DO_REGION,
                          endpoint_url=DO_ENDPOINT,
                          aws_access_key_id=DO_ACCESS_KEY,
                          aws_secret_access_key=DO_SECRET_KEY)

# --- 3. INTERFACCIA DI SELEZIONE (PRIMA DEL FILE) ---
st.subheader("1. Impostazioni Destinazione")

c1, c2, c3 = st.columns(3)

with c1:
    # Tipo di dato
    folder_type = st.radio("Tipo Cartella:", ["Forecast", "History_Baseline"])

with c2:
    # Selezione Struttura
    structure_map = {
        "Lavagnini My Place": "Lavagnini", 
        "La Terrazza di Jenny": "La_Terrazza", 
        "B&B Pitti Palace": "Pitti_Palace"
    }
    selected_label = st.selectbox("Struttura:", list(structure_map.keys()))
    folder_struct = structure_map[selected_label]

with c3:
    # Selezione Anno (MANUALE come richiesto)
    selected_year = st.number_input("Anno:", min_value=2023, max_value=2030, value=2026)

st.divider()

# --- 4. UPLOAD FILE ---
st.subheader("2. Caricamento File")
uploaded_file = st.file_uploader("Seleziona il file Excel", type=["xlsx", "xls"])

if uploaded_file:
    st.write(f"📄 File pronto per l'upload: **{uploaded_file.name}**")
    
    # Percorso finale costruito con le selezioni fatte sopra
    target_path = f"{folder_type}/{folder_struct}/{selected_year}/{uploaded_file.name}"
    
    if st.button("🚀 Conferma e Carica su Cloud"):
        s3 = get_s3_client()
        index_path = f"{folder_type}/{folder_struct}/{selected_year}/index.json"
        
        with st.spinner("Caricamento in corso..."):
            try:
                # A. Upload File Fisico
                s3.upload_fileobj(uploaded_file, DO_BUCKET, target_path, ExtraArgs={'ACL': 'public-read'})
                st.success(f"✅ Caricato correttamente: {target_path}")
                
                # B. Aggiornamento Indice JSON
                file_list = []
                try:
                    obj = s3.get_object(Bucket=DO_BUCKET, Key=index_path)
                    content = obj['Body'].read().decode('utf-8')
                    file_list = json.loads(content)
                except:
                    file_list = [] # Se non esiste, crea lista vuota
                
                if uploaded_file.name not in file_list:
                    file_list.append(uploaded_file.name)
                    # Ordina per avere i file più recenti in alto (se hanno data nel nome)
                    file_list.sort(reverse=True)
                    
                    s3.put_object(
                        Bucket=DO_BUCKET,
                        Key=index_path,
                        Body=json.dumps(file_list),
                        ACL='public-read',
                        ContentType='application/json'
                    )
                    st.info("🔄 Indice Cloud aggiornato.")
                    
            except Exception as e:
                st.error(f"Errore tecnico durante l'upload: {str(e)}")
