import streamlit as st
import pandas as pd
import requests
import io
import time
import re
import datetime  # <--- Importante per il fix

# CONFIGURAZIONE
BASE_URL = "https://ihosp-kross-archive.sfo3.cdn.digitaloceanspaces.com"

STRUCTURE_MAP = {
    "La Terrazza di Jenny": "La_Terrazza",
    "Lavagnini My Place": "Lavagnini",
    "B&B Pitti Palace": "Pitti_Palace"
}

def clean_italian_number(value):
    """Gestisce 1.234,56 e formati misti."""
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    if isinstance(value, str):
        val = value.replace("€", "").replace("%", "").strip()
        val = val.replace(".", "") # Via le migliaia
        val = val.replace(",", ".") # Virgola -> Punto
        try:
            return float(val)
        except:
            return 0.0
    return 0.0

def parse_italian_date_string(date_val):
    """Traduce date italiane in oggetti datetime."""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    
    # --- FIX ERRORE PANDAS ---
    # Controlliamo se è già un timestamp o una data python standard
    if isinstance(date_val, (pd.Timestamp, datetime.datetime, datetime.date)):
        return pd.to_datetime(date_val)
        
    s = str(date_val).lower().strip()
    
    # Tenta prima il parsing standard
    try:
        return pd.to_datetime(s, dayfirst=True)
    except:
        pass

    # Traduzione manuale
    traduzioni = [
        ('gennaio', '01'), ('febbraio', '02'), ('marzo', '03'), ('aprile', '04'),
        ('maggio', '05'), ('giugno', '06'), ('luglio', '07'), ('agosto', '08'),
        ('settembre', '09'), ('ottobre', '10'), ('novembre', '11'), ('dicembre', '12'),
        ('gen', '01'), ('feb', '02'), ('mar', '03'), ('apr', '04'),
        ('mag', '05'), ('giu', '06'), ('lug', '07'), ('ago', '08'),
        ('set', '09'), ('ott', '10'), ('nov', '11'), ('dic', '12')
    ]
    
    for nome, numero in traduzioni:
        if nome in s:
            s = s.replace(nome, numero)
            break 
            
    try:
        return pd.to_datetime(s, dayfirst=True)
    except:
        return pd.NaT

def normalize_df(df, filename=""):
    """Normalizza nomi colonne e tipi dati."""
    
    # Rimuove spazi dai nomi colonne
    df.columns = df.columns.str.strip()
    
    col_map = {
        'Data': 'date', 'Totale revenue': 'revenue', 'Occupate': 'rooms_sold',
        'Occupate %': 'occupancy_pct', 'ADR': 'adr', 'RevPar': 'revpar',
        'Unità': 'rooms', 'Bloccate': 'blocked'
    }
    
    # Tentativo di recupero colonna Data se scritta diversamente
    if 'Data' not in df.columns:
        for c in df.columns:
            if c.lower() == 'data':
                df = df.rename(columns={c: 'Data'})
                break

    df = df.rename(columns=col_map)
    
    if 'date' in df.columns:
        df['date'] = df['date'].apply(parse_italian_date_string)
        df = df.dropna(subset=['date'])
    
    cols = ['revenue', 'rooms_sold', 'occupancy_pct', 'adr', 'revpar', 'rooms']
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(clean_italian_number)
            
    return df

@st.cache_data(ttl=3600)
def load_data(structure_label, year):
    file_name = STRUCTURE_MAP.get(structure_label)
    if not file_name: return pd.DataFrame()
    
    # BASELINE
    url = f"{BASE_URL}/History_Baseline/baseline_{year}_{file_name}.xlsx"
    try:
        r = requests.get(url)
        r.raise_for_status()
        df = pd.read_excel(io.BytesIO(r.content), engine='openpyxl')
        df = normalize_df(df, filename=f"Baseline {year}")
        if not df.empty:
            df.set_index('date', inplace=True)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore caricamento Baseline {structure_label}: {e}")
        return pd.DataFrame()

    # FORECAST
    try:
        ts = int(time.time())
        idx_url = f"{BASE_URL}/Forecast/{file_name}/{year}/index.json?ts={ts}"
        r_idx = requests.get(idx_url)
        
        if r_idx.status_code == 200:
            for f_file in sorted(r_idx.json()):
                f_url = f"{BASE_URL}/Forecast/{file_name}/{year}/{f_file}"
                try:
                    rf = requests.get(f_url)
                    dff = pd.read_excel(io.BytesIO(rf.content), engine='openpyxl')
                    dff = normalize_df(dff, filename=f_file)
                    
                    if not dff.empty:
                        dff.set_index('date', inplace=True)
                        df.update(dff)
                        df = dff.combine_first(df)
                except: continue
    except: 
        pass 
    
    if df.empty: return pd.DataFrame()
    
    # Ordina per data e resetta indice
    df = df.sort_index()
    return df.reset_index()

def load_all_structures(year):
    dfs = []
    for s in STRUCTURE_MAP:
        d = load_data(s, year)
        if not d.empty: dfs.append(d)
    if not dfs: return pd.DataFrame()
    
    agg = pd.concat(dfs).groupby('date').sum(numeric_only=True).reset_index()
    agg['adr'] = agg.apply(lambda x: x['revenue']/x['rooms_sold'] if x['rooms_sold'] else 0, axis=1)
    agg['occupancy_pct'] = agg.apply(lambda x: x['rooms_sold']/x['rooms']*100 if x['rooms'] else 0, axis=1)
    agg['revpar'] = agg.apply(lambda x: x['revenue']/x['rooms'] if x['rooms'] else 0, axis=1)
    return agg
