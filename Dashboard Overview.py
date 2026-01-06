import streamlit as st
import pandas as pd
import datetime
from services import forecast_manager

st.write(f"Percorso attivo: {__file__}")

# --- CONFIGURAZIONE PAGINA: SIDEBAR CHIUSA DI DEFAULT ---
st.set_page_config(
    page_title="Dashboard Overview", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# CSS ULTIMATE: DARK MODE FRIENDLY & JUMBO BUTTONS
# ==============================================================================
st.markdown("""
<style>
    /* 1. METRICHE - CONTENITORE */
    div[data-testid="stMetric"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0px !important;
        box-shadow: none !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }

    /* 2. ETICHETTA (TITOLO KPI: Revenue, ADR...) */
    div[data-testid="stMetricLabel"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }
    
    /* FIX DARK MODE: Usa var(--text-color) invece di colore fisso */
    div[data-testid="stMetricLabel"] * {
        text-align: center !important;
        justify-content: center !important;
        display: block !important; 
        font-size: 1.1rem !important;
        font-weight: 500 !important;
        color: var(--text-color) !important; /* Adatta il colore al tema (Bianco/Nero) */
        opacity: 0.8; /* Leggera trasparenza per distinguerlo dal valore */
    }
    
    /* 3. VALORE (NUMERO) */
    div[data-testid="stMetricValue"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
    }
    
    div[data-testid="stMetricValue"] > div {
        font-size: 2.8rem !important;
        font-weight: 500 !important;
        text-align: center !important;
    }
    
    /* 4. DELTA (SCOSTAMENTO) */
    div[data-testid="stMetricDelta"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        margin-top: 5px !important;
    }
    
    div[data-testid="stMetricDelta"] > div {
        font-size: 1.2rem !important;
        font-weight: 500 !important;
        justify-content: center !important;
    }
    
    div[data-testid="stMetricDelta"] svg {
        margin-right: 5px !important;
        transform: scale(1.2); 
    }

    /* INTESTAZIONI TITOLI CENTRALI */
    .centered-header { 
        text-align: center; 
        font-weight: bold; 
        font-size: 2rem; 
        margin-bottom: 0; 
        color: var(--text-color) !important; /* FIX DARK MODE: Colore adattivo */
        white-space: nowrap; 
    }
    .centered-subtext { 
        text-align: center; 
        font-size: 0.9rem; 
        color: var(--text-color) !important; /* FIX DARK MODE: Colore adattivo */
        opacity: 0.7; /* Grigio simulato tramite opacità */
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
        background-color: #ffffff !important; /* Sfondo pulsante resta bianco per contrasto */
        color: #333 !important; /* Testo pulsante scuro per leggibilità su sfondo bianco */
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
df_curr, info_curr = forecast_manager.get_consolidated_data(selected_struct, current_year, force_italian_date=use_ita)
df_past, info_past = forecast_manager.get_consolidated_data(selected_struct, past_year, force_italian_date=use_ita)

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
# 1. NAVIGAZIONE ANNO
# ==============================================================================
# Layout Asimmetrico: [1, 1, 6, 1, 1]
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

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Revenue", f"€ {cur_rev:,.0f}", f"{cur_rev - past_rev:,.0f} €")
k2.metric("Notti", f"{int(cur_sold)}", f"{int(cur_sold - past_sold)}")
k3.metric("ADR", f"€ {cur_adr:.2f}", f"{cur_adr - past_adr:.2f} €")
k4.metric("RevPAR", f"€ {cur_revpar:.2f}", f"{cur_revpar - past_revpar:.2f} €")
k5.metric("Occ %", f"{cur_occ:.2f}%", f"{cur_occ - past_occ:.2f}%")

st.divider()

# ==============================================================================
# 2. NAVIGAZIONE MESE
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
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Revenue Mese", f"€ {m_rev:,.0f}", f"{m_rev - p_rev:,.0f} €")
    m2.metric("Notti Mese", f"{int(m_sold)}", f"{int(m_sold - p_sold)}")
    m3.metric("ADR Mese", f"€ {m_adr:.2f}", f"{m_adr - p_adr:.2f} €")
    m4.metric("RevPAR Mese", f"€ {m_revpar:.2f}", f"{m_revpar - p_revpar:.2f} €")
    m5.metric("Occ %", f"{m_occ:.2f}%", f"{m_occ - p_occ:.2f}%")
else:
    st.info(f"Nessun dato per {current_month_name} {current_year}.")

st.divider()

# ==============================================================================
# 3. GRIGLIA RIEPILOGO MESI (CON REVENUE E ADR DELTA)
# ==============================================================================
st.subheader("📅 Griglia Riepilogo Mesi")

if not df_curr.empty:
    # 1. Dati Correnti
    df_curr['MeseNum'] = df_curr['date'].dt.month
    df_curr['Mese'] = df_curr['date'].dt.strftime('%B')
    monthly = df_curr.groupby(['MeseNum', 'Mese']).agg({
        'revenue':'sum', 
        'rooms_sold':'sum', 
        'rooms':'sum'
    }).reset_index()
    
    # 2. Calcolo ADR Corrente
    monthly['ADR'] = monthly.apply(lambda x: x['revenue']/x['rooms_sold'] if x['rooms_sold']>0 else 0, axis=1)

    # 3. Dati Passati
    if not df_past.empty:
        df_past['MeseNum'] = df_past['date'].dt.month
        monthly_past = df_past.groupby('MeseNum').agg({
            'revenue': 'sum',
            'rooms_sold': 'sum'
        }).reset_index()
        monthly_past.columns = ['MeseNum', 'rev_past', 'sold_past']
        
        # Calcolo ADR Storico
        monthly_past['adr_past'] = monthly_past.apply(
            lambda x: x['rev_past'] / x['sold_past'] if x['sold_past'] > 0 else 0, axis=1
        )
        
        # Merge
        monthly = pd.merge(monthly, monthly_past[['MeseNum', 'rev_past', 'adr_past']], on='MeseNum', how='left')
        monthly['rev_past'] = monthly['rev_past'].fillna(0)
        monthly['adr_past'] = monthly['adr_past'].fillna(0)
        
        # CALCOLO DELTA
        monthly['Delta €'] = monthly['revenue'] - monthly['rev_past']
        monthly['Delta ADR'] = monthly['ADR'] - monthly['adr_past']
    else:
        monthly['Delta €'] = 0
        monthly['Delta ADR'] = 0

    # 4. Altri KPI
    monthly['RevPAR'] = monthly.apply(lambda x: x['revenue']/x['rooms'] if x['rooms']>0 else 0, axis=1)
    monthly['Occ'] = monthly.apply(lambda x: x['rooms_sold']/x['rooms']*100 if x['rooms']>0 else 0, axis=1)
    
    monthly = monthly.sort_values('MeseNum')
    height_monthly = (len(monthly) + 1) * 35 + 3
    
    def color_delta(val):
        color = '#28a745' if val >= 0 else '#dc3545'
        return f'color: {color}; font-weight: bold;'

    # Configurazione Colonne
    col_config = {
        "revenue": st.column_config.NumberColumn("Revenue", format="€ %.0f"),
        "Delta €": st.column_config.NumberColumn("Vs Prev Year", format="%.0f €"),
        "ADR": st.column_config.NumberColumn("ADR", format="€ %.2f"),
        "Delta ADR": st.column_config.NumberColumn("Delta ADR", format="%.2f €"),
        "Occ": st.column_config.NumberColumn("Occ %", format="%.2f%%")
    }

    # Stile
    styled_df = monthly[['Mese', 'revenue', 'Delta €', 'rooms_sold', 'ADR', 'Delta ADR', 'RevPAR', 'Occ']].style\
        .background_gradient(cmap="Blues", subset=['revenue'])\
        .map(color_delta, subset=['Delta €'])\
        .map(color_delta, subset=['Delta ADR'])\
        .format({
            "revenue": "€ {:,.0f}", 
            "Delta €": "{:,.0f} €", 
            "ADR": "€ {:.2f}", 
            "Delta ADR": "{:+.2f} €", 
            "RevPAR": "€ {:.2f}", 
            "Occ": "{:.2f}%"
        })

    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config=col_config,
        height=height_monthly
    )

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
