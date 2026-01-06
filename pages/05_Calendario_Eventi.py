import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import ssl
import holidays # <--- AGGIUNTO
from services import forecast_manager

# --- FIX CERTIFICATI SSL ---
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="Calendario Eventi", layout="wide", initial_sidebar_state="collapsed")

st.title("📅 Strategia Eventi & Confronto Storico")

# --- CARICAMENTO EVENTI (DRIVE + FESTIVITÀ) ---
@st.cache_data(ttl=300)
def load_events_enhanced():
    # 1. Generiamo festività italiane automatiche
    it_holidays = holidays.Italy(years=[2025, 2026])
    festivita_list = []
    for date, name in it_holidays.items():
        festivita_list.append({
            'data': pd.to_datetime(date), 
            'evento': name, 
            'tipo': 'Festività', 
            'importanza': 5
        })
    df_feste = pd.DataFrame(festivita_list)

    # 2. Carichiamo eventi da Drive
    try:
        if "URL_EVENTI" not in st.secrets: 
            return df_feste
        url = st.secrets["URL_EVENTI"]
        df_drive = pd.read_csv(url)
        df_drive.columns = df_drive.columns.str.strip().str.lower()
        
        if 'data' in df_drive.columns:
            df_drive['data'] = pd.to_datetime(df_drive['data'], dayfirst=True, errors='coerce')
            df_drive['importanza'] = pd.to_numeric(df_drive['importanza'], errors='coerce').fillna(1)
            df_drive = df_drive.dropna(subset=['data'])
            # Uniamo i due calendari (Feste + Drive)
            return pd.concat([df_feste, df_drive], ignore_index=True)
        else:
            return df_feste
    except:
        return df_feste

df_eventi = load_events_enhanced()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔧 Filtri")
    strutture = ["Lavagnini My Place", "La Terrazza di Jenny", "B&B Pitti Palace"]
    selected_struct = st.selectbox("Struttura", strutture)
    current_year = 2026
    selected_month_idx = st.selectbox("Mese di Analisi", range(1, 13), index=datetime.datetime.now().month - 1, format_func=lambda x: datetime.date(2026, x, 1).strftime('%B'))

# --- CARICAMENTO DATI (Corrente 2026 e Storico 2025) ---
df_forecast_2026, _ = forecast_manager.get_consolidated_data(selected_struct, 2026)
df_forecast_2025, _ = forecast_manager.get_consolidated_data(selected_struct, 2025)

if df_forecast_2026.empty:
    st.warning("Dati 2026 non disponibili.")
    st.stop()

# Creiamo il DataFrame principale unendo lo storico
if not df_forecast_2025.empty:
    # Allineiamo le date del 2025 su quelle del 2026 per il confronto diretto
    df_ly = df_forecast_2025[['date', 'occupancy_pct']].copy()
    df_ly['date_match'] = df_ly['date'] + pd.offsets.DateOffset(years=1)
    df_ly = df_ly.rename(columns={'occupancy_pct': 'occ_ly'})
    
    # Uniamo i dati
    df_forecast = pd.merge(
        df_forecast_2026, 
        df_ly[['date_match', 'occ_ly']], 
        left_on='date', 
        right_on='date_match', 
        how='left'
    )
else:
    df_forecast = df_forecast_2026.copy()
    df_forecast['occ_ly'] = None

# --- 1. GRAFICO ANNUALE CON CONFRONTO STORICO ---
st.subheader(f"📊 Occupazione Annuale & Calendario Eventi {current_year}")

# Aggreghiamo l'occupazione media mensile per 2026 e 2025
df_year = df_forecast.groupby(df_forecast['date'].dt.month).agg({
    'occupancy_pct': 'mean',
    'occ_ly': 'mean' # Aggiungiamo la media dell'anno scorso
}).reset_index()

# [Il codice per conteggio_eventi rimane lo stesso di prima...]
if not df_eventi.empty:
    eventi_per_mese = df_eventi[df_eventi['data'].dt.year == current_year].copy()
    eventi_per_mese['mese'] = eventi_per_mese['data'].dt.month
    conteggio_eventi = eventi_per_mese.groupby('mese').agg({
        'evento': lambda x: "<br>".join([str(e) for e in list(set(x)) if pd.notna(e)][:3])
    }).reset_index()
    df_year = pd.merge(df_year, conteggio_eventi, left_on='date', right_on='mese', how='left').fillna("")
else:
    df_year['evento'] = ""

fig_year = go.Figure()

# Barre Occupazione 2026
fig_year.add_trace(go.Bar(
    x=df_year['date'].apply(lambda x: datetime.date(2026, x, 1).strftime('%B')),
    y=df_year['occupancy_pct'],
    marker_color='#1f77b4', name="Occupazione 2026",
    hovertemplate="Mese: %{x}<br>Occ 2026: %{y:.1f}%"
))

# LINEA Confronto 2025 (LY)
if 'occ_ly' in df_year.columns and not df_year['occ_ly'].isnull().all():
    fig_year.add_trace(go.Scatter(
        x=df_year['date'].apply(lambda x: datetime.date(2026, x, 1).strftime('%B')),
        y=df_year['occ_ly'],
        mode='lines+markers',
        name='Occ 2025 (LY)',
        line=dict(color='rgba(150, 150, 150, 0.6)', width=2),
        marker=dict(size=8, symbol='circle', color='rgba(100, 100, 100, 0.8)'),
        hovertemplate="Mese: %{x}<br>Occ LY: %{y:.1f}%"
    ))

# Bandierine Eventi (rimangono come prima)
if not df_eventi.empty:
    fig_year.add_trace(go.Scatter(
        x=df_year['date'].apply(lambda x: datetime.date(2026, x, 1).strftime('%B')),
        y=df_year['occupancy_pct'] + 7,
        mode="text",
        text=df_year['evento'].apply(lambda x: "🚩" if x != "" else ""),
        hovertext=df_year['evento'],
        name="Eventi",
        textposition="top center"
    ))

fig_year.update_layout(
    height=350, 
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis=dict(ticksuffix=" %", range=[0, 115]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_year, use_container_width=True)

st.divider()

# --- 2. GRAFICO MENSILE CON CONFRONTO ---
df_month = df_forecast[df_forecast['date'].dt.month == selected_month_idx].copy()
df_month = pd.merge(df_month, df_eventi, left_on='date', right_on='data', how='left')

st.subheader(f"📍 Focus Mensile: {datetime.date(2026, selected_month_idx, 1).strftime('%B')}")

fig_month = go.Figure()
fig_month.add_trace(go.Scatter(
    x=df_month['date'], y=df_month['occupancy_pct'],
    mode='lines+markers', name='Occupazione 2026',
    line=dict(color='#1f77b4', width=4)
))

# --- AGGIUNTA LINEA CONFRONTO ANNO SCORSO ---
if 'occ_ly' in df_month.columns and not df_month['occ_ly'].isnull().all():
    fig_month.add_trace(go.Scatter(
        x=df_month['date'], 
        y=df_month['occ_ly'],
        mode='lines', 
        name='Occ % 2025 (LY)',
        line=dict(color='rgba(150, 150, 150, 0.4)', width=2, dash='dot'),
        hovertemplate="Occ LY: %{y:.1f}%"
    ))

for imp in range(1, 6):
    subset = df_month[df_month['importanza'] == imp]
    if not subset.empty:
        fig_month.add_trace(go.Scatter(
            x=subset['date'], y=subset['occupancy_pct'],
            mode='markers+text',
            text=subset['evento'] if imp >= 4 else "",
            textposition="top center",
            marker=dict(size=12+(imp*2), color='red' if imp>=4 else 'orange', symbol='diamond'),
            name=f'Livello {imp}'
        ))

fig_month.update_layout(height=450, yaxis=dict(ticksuffix=" %", range=[0, 110]), hovermode="x unified")
st.plotly_chart(fig_month, use_container_width=True)

# --- 3. TABELLA DETTAGLIO ---
st.subheader("📋 Dettaglio Analitico")

def highlight_event_rows(row):
    if pd.notna(row['evento']) and str(row['evento']).strip() != "":
        return ['background-color: rgba(255, 165, 0, 0.15)'] * len(row)
    return [''] * len(row)

df_display = df_month.copy()
df_display['Giorno'] = df_display['date'].dt.strftime('%d/%m (%a)')
# --- FIX RILEVANZA (Gestione sicura di NaN e decimali) ---
def safe_stars(val):
    try:
        # Trasforma prima in float per gestire i decimali, poi in int
        if pd.isna(val): return ""
        n = int(float(val))
        return "⭐" * n
    except:
        return ""

df_display['Rilevanza'] = df_display['importanza'].apply(safe_stars)

final_cols = ['Giorno', 'occupancy_pct', 'adr', 'revenue', 'evento', 'tipo', 'Rilevanza']
h_table = (len(df_display) + 1) * 35 + 10

st.dataframe(
    df_display[final_cols].style
    .apply(highlight_event_rows, axis=1)
    .background_gradient(subset=['occupancy_pct'], cmap='Blues')
    .format({'adr': '€ {:.2f}', 'revenue': '€ {:,.0f}', 'occupancy_pct': '{:.1f}%'}),
    use_container_width=True,
    height=h_table
)