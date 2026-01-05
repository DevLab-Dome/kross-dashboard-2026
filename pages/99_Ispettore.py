import streamlit as st
import boto3
import requests
import pandas as pd
import io

st.set_page_config(page_title="Ispettore Cloud", layout="wide")

# CONFIGURAZIONE
try:
    DO_REGION = st.secrets["digitalocean"]["region"]
    DO_ENDPOINT = st.secrets["digitalocean"]["endpoint"]
    DO_KEY = st.secrets["digitalocean"]["key"]
    DO_SECRET = st.secrets["digitalocean"]["secret"]
    DO_BUCKET = st.secrets["digitalocean"]["bucket"]
except:
    st.error("Mancano i secrets per DigitalOcean.")
    st.stop()

BASE_URL = "https://ihosp-kross-archive.sfo3.digitaloceanspaces.com"

STRUCTURE_MAP = {
    "La Terrazza di Jenny": "La_Terrazza",
    "Lavagnini My Place": "Lavagnini",     
    "B&B Pitti Palace": "Pitti_Palace"
}

def get_s3_client():
    return boto3.client('s3', region_name=DO_REGION, endpoint_url=DO_ENDPOINT,
                        aws_access_key_id=DO_KEY, aws_secret_access_key=DO_SECRET)

st.title("🕵️‍♂️ Ispettore Cloud: Diagnostica File")
st.markdown("Questa pagina verifica perché la Dashboard non vede i file che hai caricato.")

col1, col2, col3 = st.columns(3)
struttura = col1.selectbox("Struttura", list(STRUCTURE_MAP.keys()))
anno = col2.selectbox("Anno", [2024, 2025, 2026], index=1)
cartella_target = col3.selectbox("Cartella Target", ["Forecast", "History_Baseline"], index=1)

folder_name = STRUCTURE_MAP[struttura]
full_path = f"{cartella_target}/{folder_name}/{anno}"

st.divider()

st.subheader(f"1. Analisi Cartella: `{full_path}`")

s3 = get_s3_client()

# VERIFICA 1: BOTO3 (Accesso con Chiavi - Vede anche file privati/nascosti)
st.write("**🔍 Controllo 1: Accesso Amministratore (Boto3)**")
try:
    resp = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=full_path)
    if 'Contents' in resp:
        files = [obj['Key'] for obj in resp['Contents']]
        st.success(f"✅ Trovati {len(files)} oggetti fisici nel Cloud.")
        for f in files:
            st.code(f)
    else:
        st.error("❌ La cartella è VUOTA fisicamente su DigitalOcean.")
        st.stop()
except Exception as e:
    st.error(f"Errore connessione Boto3: {e}")

st.divider()

# VERIFICA 2: FILE INDEX.JSON (Necessario per la Dashboard)
st.write("**🔍 Controllo 2: Esistenza Indice (index.json)**")
index_key = f"{full_path}/index.json"
try:
    s3.head_object(Bucket=DO_BUCKET, Key=index_key)
    st.success("✅ File `index.json` presente.")
except:
    st.error("❌ File `index.json` MANCANTE. La Dashboard è cieca senza questo file.")
    st.info("💡 SOLUZIONE: Vai su 'Carica Dati' -> Tab 'Sincronizzazione' -> Premi 'Sincronizza TUTTI'.")

st.divider()

# VERIFICA 3: ACCESSO PUBBLICO (Requests - Come fa la Dashboard)
st.write("**🔍 Controllo 3: Accesso Pubblico (HTTP)**")
public_url = f"{BASE_URL}/{full_path}/index.json"
st.write(f"Test connessione a: `{public_url}`")

resp_pub = requests.get(public_url)
if resp_pub.status_code == 200:
    st.success("✅ L'indice è PUBBLICO e leggibile dalla Dashboard.")
    st.json(resp_pub.json())
elif resp_pub.status_code == 403:
    st.error("⛔ ERRORE 403 (Forbidden): Il file esiste ma è PRIVATO.")
    st.markdown("""
    **SOLUZIONE:** 1. Vai su DigitalOcean Spaces.
    2. Seleziona i file.
    3. Clicca su "Actions" -> "Permission" -> **"Public"**.
    4. Oppure ricaricali dalla pagina 'Carica Dati' che li rende pubblici in automatico.
    """)
elif resp_pub.status_code == 404:
    st.error("❌ ERRORE 404 (Not Found): L'URL pubblico non trova il file.")

st.divider()
st.subheader("🛠 Azioni Rapide")
if st.button("☢️ FORZA CREAZIONE INDICE ORA"):
    try:
        # Legge file reali
        resp = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=full_path)
        real_files = [obj['Key'].split('/')[-1] for obj in resp.get('Contents', []) 
                      if obj['Key'].endswith('.xlsx') and not obj['Key'].startswith('~$')]
        real_files.sort(reverse=True)
        
        # Scrive index
        import json
        s3.put_object(Bucket=DO_BUCKET, Key=index_key, 
                      Body=json.dumps(real_files), ACL='public-read', ContentType='application/json')
        st.success(f"✅ Indice rigenerato con {len(real_files)} file!")
        st.rerun()
    except Exception as e:
        st.error(str(e))
