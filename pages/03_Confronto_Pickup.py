import streamlit as st
import pandas as pd
import boto3
import io
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Confronto Pickup", layout="wide")

# --- 1. SETUP E CREDENZIALI ---
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
except:
    st.error("❌ Credenziali mancanti.")
    st.stop()

def get_s3_client():
    session = boto3.session.Session()
    return session.client('s3', region_name=DO_REGION, endpoint_url=DO_ENDPOINT,
                          aws_access_key_id=DO_ACCESS_KEY, aws_secret_access_key=DO_SECRET_KEY)

def load_data_from_s3(bucket, key):
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_excel(io.BytesIO(obj['Body'].read()))

# --- 2. INTERFACCIA SELEZIONE ---
st.title("📈 Analisi Pickup & Variazioni")
st.markdown("Confronta due forecast per vedere **dove** e **come** sono cambiate le prenotazioni.")

# Sidebar per filtri globali
st.sidebar.header("Filtri")
structure_map = {
    "Lavagnini My Place": "Lavagnini", 
    "La Terrazza di Jenny": "La_Terrazza", 
    "B&B Pitti Palace": "Pitti_Palace"
}
selected_label = st.sidebar.selectbox("Struttura", list(structure_map.keys()))
folder_struct = structure_map[selected_label]
selected_year = st.sidebar.number_input("Anno", min_value=2023, max_value=2030, value=2026)

# Recupero lista file
s3 = get_s3_client()
prefix = f"Forecast/{folder_struct}/{selected_year}/"
files = []
try:
    response = s3.list_objects_v2(Bucket=DO_BUCKET, Prefix=prefix)
    if 'Contents' in response:
        # Ordina per data (dal più recente)
        sorted_files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
        files = [obj['Key'].split('/')[-1] for obj in sorted_files if obj['Key'].endswith('.xlsx')]
except:
    pass

if len(files) < 2:
    st.warning("⚠️ Servono almeno 2 file forecast caricati per fare un confronto.")
    st.stop()

# Selezione File A e B
col1, col2 = st.columns(2)
with col1:
    file_a = st.selectbox("Forecast A (Più Recente)", files, index=0)
with col2:
    file_b = st.selectbox("Forecast B (Precedente)", files, index=1 if len(files) > 1 else 0)

if st.button("🚀 Avvia Confronto", use_container_width=True):
    with st.spinner("Analisi differenziale in corso..."):
        # Caricamento
        path_a = f"{prefix}{file_a}"
        path_b = f"{prefix}{file_b}"
        
        try:
            df_a = load_data_from_s3(DO_BUCKET, path_a)
            df_b = load_data_from_s3(DO_BUCKET, path_b)
            
            # Standardizzazione Colonne (Gestisce varianti di nomi)
            def standardize(df):
                df.columns = [c.strip().lower() for c in df.columns]
                # Mappatura colonne essenziali
                rename_map = {
                    'data': 'Date', 'date': 'Date',
                    'revenue': 'Revenue', 'produzione': 'Revenue',
                    'camere': 'Rooms', 'rooms': 'Rooms', 'notti': 'Rooms'
                }
                df = df.rename(columns=rename_map)
                # Assicurarsi che Date sia datetime
                df['Date'] = pd.to_datetime(df['Date'])
                return df[['Date', 'Revenue', 'Rooms']].groupby('Date').sum().reset_index()

            df_a_clean = standardize(df_a)
            df_b_clean = standardize(df_b)

            # --- MERGE DEI DATI ---
            # Uniamo i due dataframe sulla data
            merged = pd.merge(df_a_clean, df_b_clean, on='Date', how='outer', suffixes=('_A', '_B')).fillna(0)

            # Calcolo Delta
            merged['Delta_Rev'] = merged['Revenue_A'] - merged['Revenue_B']
            merged['Delta_Rooms'] = merged['Rooms_A'] - merged['Rooms_B']
            
            # Calcolo Totali Macro
            tot_pickup_rev = merged['Delta_Rev'].sum()
            tot_pickup_rooms = merged['Delta_Rooms'].sum()

            # --- 3. KPI MACRO ---
            st.divider()
            k1, k2, k3 = st.columns(3)
            k1.metric("Totale Pickup Revenue", f"€ {tot_pickup_rev:,.0f}", delta_color="normal")
            k2.metric("Totale Pickup Camere", f"{tot_pickup_rooms:.0f}", delta_color="normal")
            
            # Logica colore ADR: Se positivo verde, se negativo rosso
            k3.info("💡 I Delta sono calcolati come: (File A - File B)")

            # --- 4. TOP & FLOP (NUOVA SEZIONE) ---
            st.subheader("🏆 Top & Flop Dates")
            st.markdown("Le giornate che hanno subito le variazioni più drastiche.")
            
            tf1, tf2 = st.columns(2)
            
            with tf1:
                st.markdown("### 🟢 Top 3 Guadagni")
                # Prende i 3 valori più alti di Delta Revenue
                top_gainers = merged.nlargest(3, 'Delta_Rev')
                for _, row in top_gainers.iterrows():
                    if row['Delta_Rev'] > 0:
                        st.success(f"**{row['Date'].strftime('%d/%m/%Y')}**: +€ {row['Delta_Rev']:,.0f} ({row['Delta_Rooms']:.0f} camere)")
                    else:
                        st.write("Nessun guadagno rilevante.")

            with tf2:
                st.markdown("### 🔴 Top 3 Perdite")
                # Prende i 3 valori più bassi (negativi)
                top_losers = merged.nsmallest(3, 'Delta_Rev')
                for _, row in top_losers.iterrows():
                    if row['Delta_Rev'] < 0:
                        st.error(f"**{row['Date'].strftime('%d/%m/%Y')}**: -€ {abs(row['Delta_Rev']):,.0f} ({row['Delta_Rooms']:.0f} camere)")
                    else:
                        st.write("Nessuna perdita rilevante.")

            # --- 5. HEATMAP PICKUP (NUOVA SEZIONE) ---
            st.divider()
            st.subheader("🔥 Heatmap Temporale del Pickup")
            st.markdown("Visualizza l'andamento delle variazioni nel tempo. **Verde** = Crescita, **Rosso** = Calo.")

            # Grafico a barre colorato in base al Delta Revenue
            # Usiamo una scala di colori divergente (Rosso -> Bianco -> Verde)
            fig_heat = px.bar(
                merged, 
                x='Date', 
                y='Delta_Rev',
                color='Delta_Rev',
                title="Variazione Netta Revenue per Giorno",
                color_continuous_scale=['#FF4B4B', '#FFFFFF', '#00C853'], # Rosso Streamlit, Bianco, Verde brillante
                range_color=[-1000, 1000], # Range fisso per normalizzare i colori (aggiustabile)
                labels={'Delta_Rev': 'Pickup Revenue (€)', 'Date': 'Data'}
            )
            
            # Pulizia grafica
            fig_heat.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="",
                yaxis_title="Variazione €",
                height=400
            )
            # Aggiunge una linea dello zero per riferimento
            fig_heat.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

            st.plotly_chart(fig_heat, use_container_width=True)

            # --- 6. TABELLA DETTAGLIO ---
            with st.expander("🔎 Vedi Dati Dettagliati (Tabella)"):
                # Formattazione per lettura umana
                display_df = merged[['Date', 'Revenue_A', 'Revenue_B', 'Delta_Rev', 'Rooms_A', 'Rooms_B', 'Delta_Rooms']].copy()
                display_df['Date'] = display_df['Date'].dt.date
                st.dataframe(display_df.style.format({
                    'Revenue_A': '€ {:.0f}', 'Revenue_B': '€ {:.0f}', 'Delta_Rev': '€ {:.0f}',
                    'Rooms_A': '{:.1f}', 'Rooms_B': '{:.1f}', 'Delta_Rooms': '{:.1f}'
                }), use_container_width=True)

        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")
            st.info("Verifica che i file Excel abbiano le colonne 'Data', 'Revenue' e 'Camere' (o simili).")
