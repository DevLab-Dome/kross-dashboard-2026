import streamlit as st
import pandas as pd
import boto3
import io
from botocore.exceptions import NoCredentialsError

st.set_page_config(page_title="Carica Dati", layout="centered")

st.title("☁️ Caricamento Dati su Cloud")

# 1. Recupero Credenziali (Robustezza Assoluta)
# Cerca la sezione [digitalocean] come configurata su Streamlit Cloud
try:
    if "digitalocean" in st.secrets:
        secrets = st.secrets["digitalocean"]
    else:
        # Fallback: prova a vedere se sono nella root (senza [digitalocean])
        secrets = st.secrets

    # Mappatura esplicita delle chiavi
    DO_ACCESS_KEY = secrets.get("access_key")
    DO_SECRET_KEY = secrets.get("secret_key")
    DO_REGION = secrets.get("region", "sfo3")
    DO_ENDPOINT = secrets.get("endpoint", "https://sfo3.digitaloceanspaces.com")
    DO_BUCKET = secrets.get("bucket_name", "ihosp-kross-archive")

    if not DO_ACCESS_KEY or not DO_SECRET_KEY:
        raise ValueError("Chiavi non trovate")

except Exception as e:
    st.error("❌ Errore Configurazione Secrets.")
    st.info("Assicurati di aver incollato le chiavi nella sezione 'Secrets' su Streamlit Cloud.")
    st.stop()

# 2. Connessione a DigitalOcean (Boto3)
def get_s3_client():
    session = boto3.session.Session()
    return session.client('s3',
                          region_name=DO_REGION,
                          endpoint_url=DO_ENDPOINT,
                          aws_access_key_id=DO_ACCESS_KEY,
                          aws_secret_access_key=DO_SECRET_KEY)

# 3. Interfaccia di Upload
uploaded_file = st.file_uploader("Seleziona il file Excel (Forecast)", type=["xlsx", "xls"])

if uploaded_file:
    # Mostra anteprima
    st.write(f"📄 File selezionato: **{uploaded_file.name}**")
    
    # Determina anno e cartella
    current_year = 2026 # Default o logica dinamica
    if "2025" in uploaded_file.name: current_year = 2025
    if "2024" in uploaded_file.name: current_year = 2024
    
    # Selezione cartella destinazione
    st.subheader("Destinazione")
    col1, col2 = st.columns(2)
    with col1:
        folder_type = st.radio("Tipo Dati:", ["Forecast", "History_Baseline"])
    with col2:
        # Estrae struttura dal nome file o chiede
        structure_map = {
            "Lavagnini": "Lavagnini", 
            "Terrazza": "La_Terrazza", 
            "Pitti": "Pitti_Palace"
        }
        # Tentativo auto-selezione
        default_idx = 0
        for i, key in enumerate(structure_map.keys()):
            if key.lower() in uploaded_file.name.lower():
                default_idx = i
                break
        
        selected_struct_key = st.selectbox("Struttura:", list(structure_map.keys()), index=default_idx)
        folder_struct = structure_map[selected_struct_key]

    # Pulsante Upload
    if st.button("🚀 Carica su Cloud"):
        s3 = get_s3_client()
        
        # Costruzione percorso: CartellaTipo/CartellaStruttura/Anno/NomeFile
        file_path = f"{folder_type}/{folder_struct}/{current_year}/{uploaded_file.name}"
        
        with st.spinner("Caricamento in corso..."):
            try:
                # Carica il file
                s3.upload_fileobj(uploaded_file, DO_BUCKET, file_path, ExtraArgs={'ACL': 'public-read'})
                st.success(f"✅ Caricato con successo in: {file_path}")
                
                # AGGIORNAMENTO INDEX.JSON (Cruciale per far funzionare la Dashboard)
                # 1. Scarica index attuale
                index_path = f"{folder_type}/{folder_struct}/{current_year}/index.json"
                try:
                    obj = s3.get_object(Bucket=DO_BUCKET, Key=index_path)
                    import json
                    file_list = json.loads(obj['Body'].read().decode('utf-8'))
                except:
                    file_list = [] # Se non esiste, lo creiamo vuoto
                
                # 2. Aggiungi nuovo file se non c'è
                if uploaded_file.name not in file_list:
                    file_list.append(uploaded_file.name)
                
                # 3. Ricarica index aggiornato
                s3.put_object(
                    Bucket=DO_BUCKET,
                    Key=index_path,
                    Body=json.dumps(file_list),
                    ACL='public-read',
                    ContentType='application/json'
                )
                st.info("🔄 Indice Cloud aggiornato correttamente.")
                
            except Exception as e:
                st.error(f"Errore durante l'upload: {str(e)}")