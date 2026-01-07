import streamlit as st
import pandas as pd
import datetime
import boto3
import re
from io import BytesIO

# --- CONFIGURAZIONE PAGINA: SIDEBAR CHIUSA DI DEFAULT ---
st.set_page_config(
    page_title="Dashboard Overview", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# CSS MINIMO - SOLO PER PULSANTI E TITOLI
# ==============================================================================
st.markdown("""
<style>
    /* INTESTAZIONI TITOLI CENTRALI */
    .centered-header { 
        text-align: center; 
        font-weight: bold; 
        font-size: 2rem; 
        margin-bottom: 0; 
        color: var(--text-color) !important;
        white-space: nowrap; 
    }
    .centered-subtext { 
        text-align: center; 
        font-size: 0.9rem; 
        color: var(--text-color) !important;
        opacity: 0.7;
        margin-top: -5px; 
        margin-bottom: 25px; 
    }
    
    /* PULSANTI JUMBO */
    div.stButton > button { 
        width: 100%; 
        height: 75px !important;      
        font-size: 1.6rem !important; 
        font-weight: 700 !important;
        border-radius: 15px !important;
        border: 1px solid #d0d0d0 !important;
        background-color: #ffffff !important;
        color: #333 !important;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    div.stButton > button:hover {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
        background-color: #fff0f0 !important;
        transform: scale(1.02);
        box-shadow: 0 6px 8px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

# --- INIZIALIZZAZIONE S3 CLIENT ---
@st.cache_resource
def get_s3_client():
    try:
        if "digitalocean" in st.secrets:
            secrets = st.secrets["digitalocean"]
        else:
            secrets = st.secrets
        
        return boto3.client('s3',
            region_name=secrets.get("region", "sfo3"),
            endpoint_url=secrets.get("endpoint", "https://sfo3.digitaloceanspaces.com"),
            aws_access_key_id=secrets.get("access_key"),
            aws_secret_access_key=secrets.get("secret_key")
        ), secrets.get("bucket_name", "ihosp-kross-archive")
    except Exception as e:
        st.error(f"Errore connessione S3: {e}")
        return None, None

s3_client, bucket_name = get_s3_client()

# --- FUNZIONE: CERCATORE DI TREND (Forecast Precedente) ---
def get_previous_forecast_data(structure, year):
    """
    Trova e carica il forecast cronologicamente precedente a quello ATTUALMENTE VISUALIZZATO.
    """
    if not s3_client or not bucket_name:
        return pd.DataFrame()
    
    try:
        structure_map = {
            "Lavagnini My Place": "Lavagnini", 
            "La Terrazza di Jenny": "La_Terrazza", 
            "B&B Pitti Palace": "Pitti_Palace"
        }
        
        struct_normalized = structure_map.get(structure, structure.replace(" ", "_"))
        prefix = f"Forecast/{struct_normalized}/{year}/"
        
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        
        if 'Contents' not in response:
            return pd.DataFrame()
        
        files_metadata = []
        snapshot_pattern = r'_Snapshot_(\d{8})\.xlsx$'
        
        for obj in response['Contents']:
            key = obj['Key']
            if not key.lower().endswith(('.xlsx', '.xls')):
                continue
            
            match = re.search(snapshot_pattern, key)
            if match:
                date_str = match.group(1)
                try:
                    file_date = datetime.datetime.strptime(date_str, '%Y%m%d')
                    files_metadata.append({'key': key, 'date': file_date, 'source': 'filename'})
                except:
                    files_metadata.append({'key': key, 'date': obj['LastModified'].replace(tzinfo=None), 'source': 'lastmodified'})
            else:
                files_metadata.append({'key': key, 'date': obj['LastModified'].replace(tzinfo=None), 'source': 'lastmodified'})
        
        if len(files_metadata) < 2:
            return pd.DataFrame()
        
        files_metadata.sort(key=lambda x: x['date'], reverse=True)
        previous_file = files_metadata[1]
        
        file_obj = s3_client.get_object(Bucket=bucket_name, Key=previous_file['key'])
        df = pd.read_excel(BytesIO(file_obj['Body'].read()), engine='openpyxl')
        
        df.columns = [str(c).lower().strip() for c in df.columns]
        mappa_nomi = {
            'data': 'date', 'occupate %': 'occupancy_pct', 'occupancy %': 'occupancy_pct',
            'totale revenue': 'revenue', 'ricavo': 'revenue', 'adr': 'adr',
            'occupate': 'rooms_sold', 'unità': 'rooms', 'unita': 'rooms'
        }
        df.rename(columns=mappa_nomi, inplace=True)
        
        if 'date' not in df.columns or 'revenue' not in df.columns:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df[~df['date'].astype(str).str.contains('Totale|totale|TOTALE|Total', na=False, case=False)]
        
        for col in ['revenue', 'rooms_sold', 'adr']:
            if col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace('€', '', regex=False)\
                                   .str.replace('.', '', regex=False)\
                                   .str.replace(',', '.', regex=False)\
                                   .str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
        
    except Exception as e:
        return pd.DataFrame()

# --- FUNZIONE: KPI CARD - FIX UNSAFE_ALLOW_HTML ---
def render_kpi_card(label, value_str, delta_num, format_type, container):
    """
    Renderizza una KPI card con STILI INLINE e SEGNO DELTA SEMPRE ESPLICITO
    
    FIX CRITICO: Usa st.markdown con unsafe_allow_html=True
    
    Args:
        label: Titolo del KPI (es. "Revenue")
        value_str: Valore formattato da mostrare (es. "€ 10,000")
        delta_num: Valore numerico del delta per determinare il colore
        format_type: Tipo di formattazione ("currency", "number", "percent")
        container: Colonna Streamlit dove renderizzare
    """
    # Determina colore delta
    if delta_num >= 0:
        delta_color = "#28a745"
    else:
        delta_color = "#dc3545"
    
    # Formatta delta in base al tipo - SEMPRE CON SEGNO ESPLICITO
    if format_type == "currency":
        if delta_num >= 0:
            delta_formatted = f"+€ {abs(delta_num):,.0f}"
        else:
            delta_formatted = f"-€ {abs(delta_num):,.0f}"
    elif format_type == "percent":
        if delta_num >= 0:
            delta_formatted = f"+{delta_num:.2f}%"
        else:
            delta_formatted = f"{delta_num:.2f}%"
    else:  # number
        if delta_num >= 0:
            delta_formatted = f"+{int(delta_num)}"
        else:
            delta_formatted = f"{int(delta_num)}"
    
    # COSTRUISCI HTML
    html_content = f"""
    <div style="text-align: center; padding: 18px 12px; border-radius: 12px; background-color: #f8f9fa; border: 1px solid #e9ecef; min-height: 150px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
        <p style="color: #6c757d; font-size: 0.9rem; text-transform: uppercase; font-weight: 600; margin: 0 0 10px 0; letter-spacing: 0.8px; text-align: center;">
            {label}
        </p>
        <p style="color: #212529; font-size: 2.6rem; font-weight: 500; margin: 0; line-height: 1.1; text-align: center;">
            {value_str}
        </p>
        <p style="color: {delta_color}; font-size: 1.1rem; font-weight: 700; margin: 10px 0 0 0; text-align: center;">
            {delta_formatted}
        </p>
    </div>
    """
    
    # RENDERIZZA CON unsafe_allow_html=True
    with container:
        st.markdown(html_content, unsafe_allow_html=True)

# --- INIZIALIZZAZIONE STATO ---
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = datetime.datetime.now().year

if 'selected_month' not in st.session_state:
    st.session_state.selected_month = datetime.datetime.now().month

# --- NAVIGAZIONE ---
def change_year(delta):
    st.session_state.selected_year += delta

def change_month(delta):
    new_month = st.session_state.selected_month + delta
    if new_month > 12: new_month = 1
    elif new_month < 1: new_month = 12
    st.session_state.selected_month = new_month

# --- SIDEBAR (Nascosta) ---
with st.sidebar:
    st.title("🔧 Filtri")
    strutture_options = ["Lavagnini My Place", "La Terrazza di Jenny", "B&B Pitti Palace"]
    
    if 'selected_struct' not in st.session_state:
        st.session_state.selected_struct = strutture_options[0]
        
    selected_struct = st.selectbox("Seleziona Struttura", strutture_options, key='selected_struct')
    st.info("💡 Clicca la freccia in alto a sinistra (>) per chiudere questo menu.")
    st.divider()
    use_ita = True 

# Variabili
current_year = st.session_state.selected_year
past_year = current_year - 1
current_month_idx = st.session_state.selected_month
current_month_name = datetime.date(1900, current_month_idx, 1).strftime('%B')

# --- TITOLO PRINCIPALE ---
st.title(f"📊 Overview: {selected_struct} {current_year}")

# --- RECUPERO DATI ---
from services import forecast_manager

df_curr, info_curr = forecast_manager.get_consolidated_data(selected_struct, current_year, force_italian_date=use_ita)
df_past, info_past = forecast_manager.get_consolidated_data(selected_struct, past_year, force_italian_date=use_ita)
df_prev_forecast = get_previous_forecast_data(selected_struct, current_year)

if not info_curr:
    st.warning(f"⚠️ Nessun dato trovato per il {current_year}")

# --- CALCOLI KPI ---
def calc_kpi(df):
    if df.empty: return 0,0,0,0,0
    rev = df['revenue'].sum()
    sold = df['rooms_sold'].sum()
    cap = df['rooms'].sum()
    occ = (sold/cap*100) if cap>0 else 0
    adr = (rev/sold) if sold>0 else 0
    revpar = (rev/cap) if cap>0 else 0
    return rev, sold, adr, revpar, occ

cur_rev, cur_sold, cur_adr, cur_revpar, cur_occ = calc_kpi(df_curr)
past_rev, past_sold, past_adr, past_revpar, past_occ = calc_kpi(df_past)

st.divider()

# ==============================================================================
# 1. PANORAMICA ANNUALE - KPI CARDS
# ==============================================================================
c_dummy_L, c_btn_prev, c_title, c_dummy_R, c_btn_next = st.columns([1, 1, 6, 1, 1], vertical_alignment="center")

with c_btn_prev:
    if st.button("◀ Prev", key="prev_year"):
        change_year(-1)
        st.rerun()

with c_title:
    st.markdown(f"<div class='centered-header'>Panoramica Annuale {current_year}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='centered-subtext'>Anno di comparazione {past_year}</div>", unsafe_allow_html=True)

with c_btn_next:
    if st.button("Next ▶", key="next_year"):
        change_year(1)
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True) 

# ORDINE: Revenue | Notti | Occ % | ADR | RevPAR
k1, k2, k3, k4, k5 = st.columns(5)

render_kpi_card("Revenue", f"€ {cur_rev:,.0f}", cur_rev - past_rev, "currency", k1)
render_kpi_card("Notti", f"{int(cur_sold)}", cur_sold - past_sold, "number", k2)
render_kpi_card("Occ %", f"{cur_occ:.2f}%", cur_occ - past_occ, "percent", k3)
render_kpi_card("ADR", f"€ {cur_adr:.2f}", cur_adr - past_adr, "currency", k4)
render_kpi_card("RevPAR", f"€ {cur_revpar:.2f}", cur_revpar - past_revpar, "currency", k5)

st.divider()

# ==============================================================================
# 2. FOCUS MESE - KPI CARDS
# ==============================================================================
df_curr_m = df_curr[df_curr['date'].dt.month == current_month_idx] if not df_curr.empty else pd.DataFrame()
df_past_m = df_past[df_past['date'].dt.month == current_month_idx] if not df_past.empty else pd.DataFrame()

mc_dummy_L, mc_btn_prev, mc_title, mc_dummy_R, mc_btn_next = st.columns([1, 1, 6, 1, 1], vertical_alignment="center")

with mc_btn_prev:
    if st.button("◀ Prev", key="prev_month"):
        change_month(-1)
        st.rerun()

with mc_title:
    st.markdown(f"<div class='centered-header'>Focus Mese: {current_month_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='centered-subtext'>Anno di comparazione {past_year}</div>", unsafe_allow_html=True)

with mc_btn_next:
    if st.button("Next ▶", key="next_month"):
        change_month(1)
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

if not df_curr_m.empty:
    m_rev, m_sold, m_adr, m_revpar, m_occ = calc_kpi(df_curr_m)
    p_rev, p_sold, p_adr, p_revpar, p_occ = calc_kpi(df_past_m)
    
    # ORDINE: Revenue | Notti | Occ % | ADR | RevPAR
    m1, m2, m3, m4, m5 = st.columns(5)
    
    render_kpi_card("Revenue Mese", f"€ {m_rev:,.0f}", m_rev - p_rev, "currency", m1)
    render_kpi_card("Notti Mese", f"{int(m_sold)}", m_sold - p_sold, "number", m2)
    render_kpi_card("Occ %", f"{m_occ:.2f}%", m_occ - p_occ, "percent", m3)
    render_kpi_card("ADR Mese", f"€ {m_adr:.2f}", m_adr - p_adr, "currency", m4)
    render_kpi_card("RevPAR Mese", f"€ {m_revpar:.2f}", m_revpar - p_revpar, "currency", m5)
else:
    st.info(f"Nessun dato per {current_month_name} {current_year}.")

st.divider()

# ==============================================================================
# 3. GRIGLIA RIEPILOGO MESI
# ==============================================================================
st.subheader("📅 Griglia Riepilogo Mesi")

if not df_curr.empty:
    df_curr['MeseNum'] = df_curr['date'].dt.month
    df_curr['Mese'] = df_curr['date'].dt.strftime('%B')
    monthly = df_curr.groupby(['MeseNum', 'Mese']).agg({
        'revenue':'sum', 'rooms_sold':'sum', 'rooms':'sum'
    }).reset_index()
    
    monthly['ADR'] = monthly.apply(lambda x: x['revenue']/x['rooms_sold'] if x['rooms_sold']>0 else 0, axis=1)
    monthly['Occ %'] = monthly.apply(lambda x: x['rooms_sold']/x['rooms'] *100 if x['rooms']>0 else 0, axis=1)
    monthly['RevPAR'] = monthly.apply(lambda x: x['revenue']/x['rooms'] if x['rooms']>0 else 0, axis=1)

    if not df_prev_forecast.empty:
        df_prev_forecast['MeseNum'] = df_prev_forecast['date'].dt.month
        monthly_prev_fc = df_prev_forecast.groupby('MeseNum').agg({'revenue': 'sum'}).reset_index()
        monthly_prev_fc.columns = ['MeseNum', 'Trend Prev']
        monthly_prev_fc['Trend Prev'] = pd.to_numeric(monthly_prev_fc['Trend Prev'], errors='coerce').fillna(0)
        monthly = pd.merge(monthly, monthly_prev_fc[['MeseNum', 'Trend Prev']], on='MeseNum', how='left')
        monthly['Trend Prev'] = monthly['Trend Prev'].fillna(0)
    else:
        monthly['Trend Prev'] = 0

    if not df_past.empty:
        df_past['MeseNum'] = df_past['date'].dt.month
        monthly_past = df_past.groupby('MeseNum').agg({
            'revenue': 'sum', 'rooms_sold': 'sum', 'rooms': 'sum'
        }).reset_index()
        monthly_past.columns = ['MeseNum', 'Revenue LY', 'sold_ly', 'rooms_ly']
        
        monthly_past['adr_ly'] = monthly_past.apply(lambda x: x['Revenue LY'] / x['sold_ly'] if x['sold_ly'] > 0 else 0, axis=1)
        monthly_past['occ_ly'] = monthly_past.apply(lambda x: x['sold_ly'] / x['rooms_ly'] * 100 if x['rooms_ly'] > 0 else 0, axis=1)
        
        monthly = pd.merge(monthly, monthly_past[['MeseNum', 'Revenue LY', 'adr_ly', 'occ_ly']], on='MeseNum', how='left')
        monthly['Revenue LY'] = monthly['Revenue LY'].fillna(0)
        monthly['adr_ly'] = monthly['adr_ly'].fillna(0)
        monthly['occ_ly'] = monthly['occ_ly'].fillna(0)
        
        monthly['Vs Prev Year'] = monthly['revenue'] - monthly['Revenue LY']
        monthly['Delta Occ %'] = monthly['Occ %'] - monthly['occ_ly']
        monthly['Delta ADR'] = monthly['ADR'] - monthly['adr_ly']
    else:
        monthly['Revenue LY'] = 0
        monthly['Vs Prev Year'] = 0
        monthly['Delta Occ %'] = 0
        monthly['Delta ADR'] = 0

    monthly = monthly.sort_values('MeseNum')
    
    display_columns = ['Mese', 'revenue', 'Trend Prev', 'Revenue LY', 'Vs Prev Year', 'rooms_sold', 'Occ %', 'Delta Occ %', 'ADR', 'Delta ADR', 'RevPAR']
    monthly_display = monthly[display_columns].copy()
    monthly_display.columns = ['Mese', 'Revenue', 'Trend Prev', 'Revenue LY', 'Vs Prev Year', 'Rooms Sold', 'Occ %', 'Delta Occ %', 'ADR', 'Delta ADR', 'RevPAR']
    
    height_monthly = (len(monthly_display) + 1) * 35 + 3
    
    def color_delta(val):
        color = '#28a745' if val >= 0 else '#dc3545'
        return f'color: {color}; font-weight: bold;'

    col_config = {
        "Revenue": st.column_config.NumberColumn("Revenue", format="€ %.0f"),
        "Trend Prev": st.column_config.NumberColumn("Trend Prev", format="€ %.0f"),
        "Revenue LY": st.column_config.NumberColumn("Revenue LY", format="€ %.0f"),
        "Vs Prev Year": st.column_config.NumberColumn("Vs Prev Year", format="%+.0f €"),
        "Rooms Sold": st.column_config.NumberColumn("Rooms Sold", format="%.0f"),
        "Occ %": st.column_config.NumberColumn("Occ %", format="%.2f%%"),
        "Delta Occ %": st.column_config.NumberColumn("Delta Occ %", format="%+.2f pp"),
        "ADR": st.column_config.NumberColumn("ADR", format="€ %.2f"),
        "Delta ADR": st.column_config.NumberColumn("Delta ADR", format="%+.2f €"),
        "RevPAR": st.column_config.NumberColumn("RevPAR", format="€ %.2f")
    }

    styled_df = monthly_display.style\
        .background_gradient(cmap="Blues", subset=['Revenue'])\
        .map(color_delta, subset=['Vs Prev Year'])\
        .map(color_delta, subset=['Delta Occ %'])\
        .map(color_delta, subset=['Delta ADR'])\
        .format({
            "Revenue": "€ {:,.0f}", "Trend Prev": "€ {:,.0f}", "Revenue LY": "€ {:,.0f}",
            "Vs Prev Year": "{:+,.0f} €", "Rooms Sold": "{:.0f}", "Occ %": "{:.2f}%",
            "Delta Occ %": "{:+.2f} pp", "ADR": "€ {:.2f}", "Delta ADR": "{:+.2f} €", "RevPAR": "€ {:.2f}"
        })

    st.dataframe(styled_df, use_container_width=True, column_config=col_config, height=height_monthly)

st.divider()

# ==============================================================================
# 4. DETTAGLIO GIORNALIERO
# ==============================================================================
st.subheader(f"Dettaglio Giornaliero ({current_month_name})")

if not df_curr_m.empty:
    daily = df_curr_m[['date', 'revenue', 'rooms_sold', 'adr', 'revpar', 'occupancy_pct']].copy()
    daily['Data'] = daily['date'].dt.strftime('%d/%m %a')
    daily = daily.set_index('Data')
    
    height_daily = (len(daily) + 1) * 35 + 3

    st.dataframe(
        daily.style.background_gradient(cmap="Greens", subset=['revenue']),
        use_container_width=True,
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="€ %.0f"),
            "occupancy_pct": st.column_config.NumberColumn("Occ %", format="%.2f%%")
        },
        height=height_daily
    )