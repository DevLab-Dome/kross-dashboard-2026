import streamlit as st
import pandas as pd
import boto3
import json
from botocore.exceptions import NoCredentialsError

st.set_page_config(page_title="Ispettore Cloud", layout="wide")

st.title("🕵️‍♂️ Ispettore File Cloud")
st.markdown("Visualizza e gestisci i file salvati su DigitalOcean Spaces.")

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

# --- 2. CONNESSIONE ---
def get_s3_client():
    session = boto3.session.Session()
    return session.client('s3',
                          region_name=DO_REGION,
                          endpoint_url=DO_ENDPOINT,
                          aws_access_key_id=DO_ACCESS_KEY,
                          aws_secret_access_key=DO_SECRET_KEY)

# --- 3. SELEZIONE ---
col1, col2, col3 = st.columns(3)

with col1:
    folder_type = st.selectbox("Tipo Cartella", ["Forecast", "History_Baseline"])

with col2:
    structure_map = {
        "Lavagnini My Place": "Lavagnini", 
        "La Terrazza di Jenny": "La_Terrazza", 
        "B&B Pitti Palace": "Pitti_Palace"
    }
    selected_label = st.selectbox("Struttura", list(structure_map.keys()))
    folder_struct = structure_map[selected_label]

with col3:
    # Opzione per selezionare l'anno
    selected_year = st.selectbox("Anno", [2024, 2025, 2026, 2027], index=2)

# --- 4. LISTA FILE ---
s3 = get_s3_client()
prefix = f"{folder_type}/{folder_struct}/{selected_year}/"

if st.button("🔄 Aggiorna Lista"):
    st.rerun()

st.divider()
st.subheader(f"📂 File in: `{prefix}`")

try:
    response = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=prefix)
    
    if 'Contents' in response:
        files = response['Contents']
        
        # Creiamo una tabella carina
        data = []
        for obj in files:
            file_name = obj['Key'].split('/')[-1] # Prende solo il nome finale
            if file_name and file_name != "index.json": # Ignoriamo index e cartelle vuote
                # Convertiamo dimensione in KB
                size_kb = round(obj['Size'] / 1024, 1)
                last_mod = obj['LastModified'].strftime("%d/%m/%Y %H:%M")
                data.append({"Nome File": file_name, "Data Caricamento": last_mod, "Dimensione (KB)": size_kb, "Full Key": obj['Key']})
        
        if data:
            df = pd.DataFrame(data)
            # Mostra tabella
            st.dataframe(df[["Nome File", "Data Caricamento", "Dimensione (KB)"]], use_container_width=True)
            
            # --- ZONA PERICOLO: ELIMINAZIONE ---
            st.write("---")
            st.warning("⚠️ Area Gestione (Attenzione: le cancellazioni sono definitive)")
            
            file_to_delete = st.selectbox("Seleziona un file da eliminare:", df["Nome File"].tolist())
            
            if st.button(f"🗑️ ELIMINA {file_to_delete}"):
                full_key_to_del = df[df["Nome File"] == file_to_delete].iloc[0]["Full Key"]
                s3.delete_object(Bucket=DO_BUCKET, Key=full_key_to_del)
                st.success(f"File {file_to_delete} eliminato.")
                
                # Rigenera index.json dopo cancellazione
                current_files = [f for f in df["Nome File"].tolist() if f != file_to_delete]
                index_key = f"{prefix}index.json"
                s3.put_object(
                    Bucket=DO_BUCKET, 
                    Key=index_key, 
                    Body=json.dumps(current_files), 
                    ACL='public-read',
                    ContentType='application/json'
                )
                st.rerun() # Ricarica pagina
                
        else:
            st.info("Nessun file Excel trovato in questa cartella.")
    else:
        st.info("Cartella vuota o non esistente.")

except Exception as e:
    st.error(f"Errore di connessione: {e}")
