import streamlit as st
import pandas as pd
import boto3
import json
import io
from datetime import datetime, date
from botocore.exceptions import NoCredentialsError

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Carica Dati", layout="wide")

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

# --- 3. INTERFACCIA DI SELEZIONE ---
st.subheader("1. Impostazioni Destinazione")

# Usiamo colonne per non sprecare spazio in larghezza
c1, c2, c3 = st.columns(3)

with c1:
    folder_type = st.radio("Tipo Cartella:", ["Forecast", "History_Baseline"])

with c2:
    structure_map = {
        "Lavagnini My Place": "Lavagnini", 
        "La Terrazza di Jenny": "La_Terrazza", 
        "B&B Pitti Palace": "Pitti_Palace"
    }
    selected_label = st.selectbox("Struttura:", list(structure_map.keys()))
    folder_struct = structure_map[selected_label]

with c3:
    selected_year = st.number_input("Anno:", min_value=2023, max_value=2030, value=2026)

st.divider()

# --- 4. DATA DI RIFERIMENTO FORECAST (SOLO PER FORECAST) ---
if folder_type == "Forecast":
    st.subheader("2. Data di Riferimento Forecast")
    st.info("📅 Indica a quale data si riferisce questo forecast (indipendentemente da quando lo stai caricando)")
    
    forecast_date = st.date_input(
        "Data di Riferimento Forecast:",
        value=date.today(),
        min_value=date(2023, 1, 1),
        max_value=date(2030, 12, 31),
        help="Questa data verrà usata per nominare il file e permettere il tracciamento storico"
    )
    
    st.divider()

# --- 5. UPLOAD FILE ---
st.subheader("3. Caricamento File")
uploaded_file = st.file_uploader("Seleziona il file Excel", type=["xlsx", "xls"])

if uploaded_file:
    # LOGICA DI RINOMINA PER FORECAST
    if folder_type == "Forecast":
        # Formato: [NomeStruttura]_Forecast_Snapshot_[YYYYMMDD].xlsx
        date_str = forecast_date.strftime("%Y%m%d")
        new_filename = f"{folder_struct}_Forecast_Snapshot_{date_str}.xlsx"
        
        st.write(f"📄 File originale: **{uploaded_file.name}**")
        st.write(f"🔄 Sarà rinominato in: **{new_filename}**")
        st.caption(f"📅 Data di riferimento: {forecast_date.strftime('%d/%m/%Y')}")
        
        target_path = f"{folder_type}/{folder_struct}/{selected_year}/{new_filename}"
        
    else:
        # Per History_Baseline mantieni il nome originale
        new_filename = uploaded_file.name
        st.write(f"📄 File pronto per l'upload: **{uploaded_file.name}**")
        target_path = f"{folder_type}/{folder_struct}/{selected_year}/{uploaded_file.name}"
    
    # Verifica se il file esiste già
    if folder_type == "Forecast":
        s3_check = get_s3_client()
        try:
            s3_check.head_object(Bucket=DO_BUCKET, Key=target_path)
            st.warning(f"⚠️ **ATTENZIONE**: Esiste già un forecast per la data {forecast_date.strftime('%d/%m/%Y')}. Il caricamento lo sovrascriverà.")
        except:
            pass  # File non esiste, tutto ok
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 Conferma e Carica su Cloud", use_container_width=True, type="primary"):
        s3 = get_s3_client()
        index_path = f"{folder_type}/{folder_struct}/{selected_year}/index.json"
        
        with st.spinner("Caricamento in corso..."):
            try:
                # A. Upload File Fisico con nome corretto
                # Reset del puntatore del file prima dell'upload
                uploaded_file.seek(0)
                
                s3.upload_fileobj(
                    uploaded_file, 
                    DO_BUCKET, 
                    target_path, 
                    ExtraArgs={'ACL': 'public-read'}
                )
                st.success(f"✅ Caricato correttamente: `{target_path}`")
                
                # B. Aggiornamento Indice JSON
                file_list = []
                try:
                    obj = s3.get_object(Bucket=DO_BUCKET, Key=index_path)
                    content = obj['Body'].read().decode('utf-8')
                    file_list = json.loads(content)
                except:
                    file_list = [] 
                
                # Usa il nuovo nome del file (non quello originale)
                if new_filename not in file_list:
                    file_list.append(new_filename)
                    # Ordina in ordine cronologico inverso (più recente prima)
                    file_list.sort(reverse=True)
                    
                    s3.put_object(
                        Bucket=DO_BUCKET,
                        Key=index_path,
                        Body=json.dumps(file_list),
                        ACL='public-read',
                        ContentType='application/json'
                    )
                    st.info("🔄 Indice Cloud aggiornato.")
                else:
                    st.info("ℹ️ File già presente nell'indice (sovrascritto).")
                
                # C. Messaggio finale per Forecast
                if folder_type == "Forecast":
                    st.success(f"✨ **Forecast tracciato con successo per la data {forecast_date.strftime('%d/%m/%Y')}**")
                    st.caption("Il sistema potrà ora confrontare questo forecast con quelli precedenti per l'analisi Pickup.")
                    
            except Exception as e:
                st.error(f"❌ Errore tecnico durante l'upload: {str(e)}")
                st.exception(e)

st.divider()

# --- 6. INFORMAZIONI AGGIUNTIVE ---
with st.expander("ℹ️ Informazioni sul Sistema di Tracciamento"):
    st.markdown("""
    ### 📋 Come funziona il tracciamento Forecast
    
    **Per i Forecast:**
    - Ogni file viene rinominato con il formato: `[Struttura]_Forecast_Snapshot_[YYYYMMDD].xlsx`
    - La data inserita identifica univocamente il forecast per quella giornata
    - Se carichi un altro forecast per la stessa data, il precedente verrà sovrascritto
    - Questo permette alla Dashboard Overview di:
        - Ordinare cronologicamente tutti i forecast
        - Confrontare automaticamente il forecast corrente con quello precedente
        - Calcolare l'evoluzione delle prenotazioni (Pickup Analysis)
    
    **Per History_Baseline:**
    - I file mantengono il nome originale
    - Non viene applicata alcuna rinomina
    - Utilizzati per dati storici consolidati
    
    ### 🔍 Esempio Pratico
    
    Se carichi un forecast oggi (07/01/2026) ma ti riferisci ai dati di ieri (06/01/2026):
    - Seleziona come "Data di Riferimento": **06/01/2026**
    - Il file sarà salvato come: `Lavagnini_Forecast_Snapshot_20260106.xlsx`
    - Nella Dashboard Overview vedrai il confronto corretto con il forecast precedente
    """)