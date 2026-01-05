import streamlit as st
import boto3
import json
import pandas as pd
import io

st.set_page_config(page_title="Gestione Dati", layout="wide")

try:
    DO_REGION = st.secrets["digitalocean"]["region"]
    DO_ENDPOINT = st.secrets["digitalocean"]["endpoint"]
    DO_KEY = st.secrets["digitalocean"]["key"]
    DO_SECRET = st.secrets["digitalocean"]["secret"]
    DO_BUCKET = st.secrets["digitalocean"]["bucket"]
except:
    st.error("Configurazione secrets mancante.")
    st.stop()

STRUCTURE_MAP = {
    "La Terrazza di Jenny": "La_Terrazza",
    "Lavagnini My Place": "Lavagnini",     
    "B&B Pitti Palace": "Pitti_Palace"
}

def get_s3_client():
    return boto3.client('s3', region_name=DO_REGION, endpoint_url=DO_ENDPOINT,
                        aws_access_key_id=DO_KEY, aws_secret_access_key=DO_SECRET)

st.title("📂 Gestione Dati")

# TAB SYSTEM
tab1, tab2 = st.tabs(["⬆️ Caricamento Manuale", "🔄 Sincronizzazione Cloud"])

# --- TAB 1: CARICAMENTO STANDARD ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        struct_label = st.selectbox("Seleziona Struttura", list(STRUCTURE_MAP.keys()))
    with col2:
        year = st.selectbox("Seleziona Anno di Riferimento", [2022, 2023, 2024, 2025, 2026], index=4)

    folder_name = STRUCTURE_MAP[struct_label]
    s3 = get_s3_client()

    st.divider()
    tipo_upload = st.radio("Destinazione:", 
                          ["Forecast Corrente (Dati vivi 2026)", 
                           "Storico Consolidato (Baseline 2022-2025)"], 
                          index=0)

    if "Forecast" in tipo_upload:
        target_folder = f"Forecast/{folder_name}/{year}"
    else:
        target_folder = f"History_Baseline/{folder_name}/{year}"

    st.info(f"Caricamento in: **{target_folder}**")
    uploaded_file = st.file_uploader("Seleziona file Excel", type=['xlsx'])

    if uploaded_file and st.button("🚀 Carica File", type="primary"):
        try:
            full_key = f"{target_folder}/{uploaded_file.name}"
            s3.put_object(Bucket=DO_BUCKET, Key=full_key, Body=uploaded_file.getvalue(), ACL='public-read')
            
            # Aggiorna indice locale
            response = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=target_folder)
            files = [obj['Key'].split('/')[-1] for obj in response.get('Contents', []) if obj['Key'].endswith('.xlsx')]
            files.sort(reverse=True)
            s3.put_object(Bucket=DO_BUCKET, Key=f"{target_folder}/index.json", Body=json.dumps(files), ACL='public-read')
            
            st.success("✅ Fatto!")
        except Exception as e:
            st.error(f"Errore: {e}")

# --- TAB 2: SINCRONIZZAZIONE (PER UPLOAD MANUALE SU DO) ---
with tab2:
    st.header("🛠 Strumenti per Upload Manuale da DigitalOcean")
    st.markdown("""
    Se hai caricato i file direttamente dal sito di DigitalOcean o via FTP, usa questo pulsante 
    per aggiornare gli indici e rendere i file visibili alla Dashboard.
    """)
    
    if st.button("🔄 Sincronizza TUTTI gli Indici (Forecast & History)", type="primary"):
        s3 = get_s3_client()
        with st.status("Scansione e indicizzazione in corso...") as status:
            
            # Cartelle da scansionare
            base_folders = ["Forecast", "History_Baseline"]
            structures = list(STRUCTURE_MAP.values())
            years = ["2022", "2023", "2024", "2025", "2026"]
            
            count = 0
            for base in base_folders:
                for struct in structures:
                    for y in years:
                        folder_path = f"{base}/{struct}/{y}"
                        try:
                            # Lista file
                            response = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=folder_path)
                            if 'Contents' in response:
                                files = [obj['Key'].split('/')[-1] for obj in response['Contents'] 
                                         if obj['Key'].endswith('.xlsx') and not obj['Key'].startswith('~$')]
                                
                                if files:
                                    files.sort(reverse=True)
                                    # Scrivi index.json
                                    s3.put_object(Bucket=DO_BUCKET, Key=f"{folder_path}/index.json", 
                                                  Body=json.dumps(files), ACL='public-read', ContentType='application/json')
                                    status.write(f"✅ Aggiornato: {folder_path} ({len(files)} file)")
                                    count += 1
                        except Exception as e:
                            pass
            
            status.update(label=f"Sincronizzazione completata! Aggiornate {count} cartelle.", state="complete", expanded=True)
            st.success("Ora la Dashboard vede i nuovi file caricati manualmente!")
