import streamlit as st
import pandas as pd
import requests
import io
import datetime
import time
import re

BASE_URL = "https://ihosp-kross-archive.sfo3.digitaloceanspaces.com"

STRUCTURE_MAP = {
    "La Terrazza di Jenny": "La_Terrazza",
    "Lavagnini My Place": "Lavagnini",      
    "B&B Pitti Palace": "Pitti_Palace",
    "LAVAGNINI_MY_PLACE": "Lavagnini",
    "LA_TERRAZZA_DI_JENNY": "La_Terrazza",
    "B_B_PITTI_PALACE": "Pitti_Palace"
}

CURRENT_SYSTEM_YEAR = datetime.datetime.now().year

# --- FUNZIONI DI UTILITÀ BASE ---
def clean_italian_number(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    s = str(value).replace("€", "").replace("%", "").strip()
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def parse_date_strict_italian(date_val):
    s = str(date_val).strip()
    if not s or s.lower() == 'nan' or 'totale' in s.lower(): return pd.NaT
    if isinstance(date_val, (pd.Timestamp, datetime.datetime)): return pd.to_datetime(date_val)
    
    # Tentativi formati standard
    for fmt in ['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d']:
        try: return pd.to_datetime(s, format=fmt)
        except: pass
            
    # Tentativo generico
    try: return pd.to_datetime(s, dayfirst=True)
    except: return pd.NaT

def normalize_forecast_df(df):
    df.columns = df.columns.str.strip()
    col_map = {
        'Data': 'date', 'Totale revenue': 'revenue', 'Occupate': 'rooms_sold',
        'Occupate %': 'occupancy_pct', 'ADR': 'adr', 'RevPar': 'revpar', 'Unità': 'rooms'
    }
    df = df.rename(columns=col_map)
    if 'date' in df.columns:
        df['date'] = df['date'].apply(parse_date_strict_italian)
        df = df.dropna(subset=['date'])
    cols = ['revenue', 'rooms_sold', 'occupancy_pct', 'adr', 'revpar', 'rooms']
    for c in cols:
        if c in df.columns: df[c] = df[c].apply(clean_italian_number)
    return df

def load_excel_from_url(url):
    try:
        resp = requests.get(url)
        if resp.status_code != 200: return pd.DataFrame()
        df = pd.read_excel(io.BytesIO(resp.content), engine='openpyxl', dtype=object)
        return normalize_forecast_df(df)
    except: return pd.DataFrame()

# --- MOTORE PER OVERVIEW E DETTAGLIO ---
@st.cache_data(ttl=60)
def get_consolidated_data(structure_label, year, force_italian_date=True):
    folder_name = STRUCTURE_MAP.get(structure_label)
    if not folder_name: return pd.DataFrame(), None
    ts = int(time.time())
    
    # Logica cartelle
    if year == CURRENT_SYSTEM_YEAR:
        base_folder = "Forecast"
        source_label = "Live Forecast"
    else:
        base_folder = "History_Baseline"
        source_label = "History Archive"
        
    try:
        url_idx = f"{BASE_URL}/{base_folder}/{folder_name}/{year}/index.json?ts={ts}"
        resp = requests.get(url_idx)
        if resp.status_code == 200:
            files = resp.json()
            if files:
                # Ordina file per nome decrescente (presumendo che contengano date)
                files.sort(reverse=True)
                chosen_file = files[0]
                url_file = f"{BASE_URL}/{base_folder}/{folder_name}/{year}/{chosen_file}?ts={ts}"
                df = load_excel_from_url(url_file)
                if not df.empty:
                    df = df[df['date'].dt.year == year]
                    return df, {'source': source_label, 'file': chosen_file}
    except: pass
    return pd.DataFrame(), None

# ==============================================================================
# FUNZIONI SPECIFICHE PER PICKUP (PARSING DATE DDMMYYYY)
# ==============================================================================

def get_available_snapshots(structure_label, year):
    """
    Recupera i file e parsa la data dal nome file formato: Nome_Forecast_DDMMYYYY_DDMMYYYY.xlsx
    La prima data è quella di 'scatto' (Snapshot Date).
    """
    folder_name = STRUCTURE_MAP.get(structure_label)
    if not folder_name: return pd.DataFrame()
    ts = int(time.time())
    
    if year == CURRENT_SYSTEM_YEAR: base_folder = "Forecast"
    else: base_folder = "History_Baseline"

    try:
        url_idx = f"{BASE_URL}/{base_folder}/{folder_name}/{year}/index.json?ts={ts}"
        resp = requests.get(url_idx)
        
        if resp.status_code == 200:
            files = resp.json()
            snapshot_list = []
            
            for f in files:
                # Regex per cercare pattern DDMMYYYY (8 cifre consecutive)
                # Esempio: Terrazza_Forecast_08022025_... -> Trova 08022025
                match = re.findall(r'(\d{8})', f)
                
                snap_date = None
                if match and len(match) >= 1:
                    try:
                        # Prendiamo la prima data trovata come data di snapshot
                        date_str = match[0]
                        snap_date = datetime.datetime.strptime(date_str, "%d%m%Y").date()
                    except: pass
                
                # Se il regex fallisce, proviamo a vedere se è una data ISO
                if not snap_date:
                     match_iso = re.search(r'(\d{4}-\d{2}-\d{2})', f)
                     if match_iso:
                         try: snap_date = datetime.datetime.strptime(match_iso.group(1), "%Y-%m-%d").date()
                         except: pass

                if snap_date:
                    snapshot_list.append({
                        'date': snap_date,
                        'filename': f,
                        'label': snap_date.strftime('%d/%m/%Y')
                    })
            
            df_snaps = pd.DataFrame(snapshot_list)
            if not df_snaps.empty:
                df_snaps = df_snaps.sort_values('date', ascending=False)
            return df_snaps
            
    except: pass
    return pd.DataFrame()

def get_pickup_data(structure_label, year, file_recent, file_old):
    """
    Scarica due file, li unisce e calcola i delta per tutti i KPI.
    """
    folder_name = STRUCTURE_MAP.get(structure_label)
    ts = int(time.time())
    
    if year == CURRENT_SYSTEM_YEAR: base_folder = "Forecast"
    else: base_folder = "History_Baseline"
        
    url_recent = f"{BASE_URL}/{base_folder}/{folder_name}/{year}/{file_recent}?ts={ts}"
    url_old = f"{BASE_URL}/{base_folder}/{folder_name}/{year}/{file_old}?ts={ts}"
    
    df_curr = load_excel_from_url(url_recent)
    df_prev = load_excel_from_url(url_old)
    
    if df_curr.empty or df_prev.empty: return pd.DataFrame()
        
    # Merge
    # Aggiungiamo anche RevPAR e Occupancy al merge
    kpi_cols = ['date', 'revenue', 'rooms_sold', 'adr', 'revpar', 'occupancy_pct', 'rooms']
    
    # Intersezione delle colonne disponibili
    cols_curr = [c for c in kpi_cols if c in df_curr.columns]
    cols_prev = [c for c in kpi_cols if c in df_prev.columns]
    
    df_merge = pd.merge(
        df_curr[cols_curr],
        df_prev[cols_prev],
        on='date',
        suffixes=('_curr', '_prev'),
        how='inner'
    )
    
    # Calcolo Delta
    df_merge['pickup_revenue'] = df_merge['revenue_curr'] - df_merge['revenue_prev'].fillna(0)
    df_merge['pickup_rooms'] = df_merge['rooms_sold_curr'] - df_merge['rooms_sold_prev'].fillna(0)
    df_merge['pickup_adr'] = df_merge['adr_curr'] - df_merge['adr_prev'].fillna(0)
    df_merge['pickup_revpar'] = df_merge['revpar_curr'] - df_merge['revpar_prev'].fillna(0)
    # Delta Occupazione (Punti percentuali)
    if 'occupancy_pct_curr' in df_merge.columns:
        df_merge['pickup_occ'] = df_merge['occupancy_pct_curr'] - df_merge['occupancy_pct_prev'].fillna(0)
    else:
        df_merge['pickup_occ'] = 0.0
    
    return df_merge
