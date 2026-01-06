import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from services import forecast_manager

st.set_page_config(page_title="Pace Analysis", layout="wide", initial_sidebar_state="collapsed")

# --- TITOLO E FILTRI ---
st.title("📈 Analisi del Ritmo (Pace Analysis)")

with st.sidebar:
    st.header("🔧 Configurazione")
    strutture = ["Lavagnini My Place", "La Terrazza di Jenny", "B&B Pitti Palace"]
    selected_struct = st.selectbox("Struttura", strutture)
    current_year = datetime.datetime.now().year
    target_year = st.sidebar.number_input("Anno Target", min_value=2024, max_value=2030, value=current_year)

# --- CARICAMENTO DATI ---
with st.spinner("Recupero dati di Pace..."):
    df_pace, meta, df_raw = forecast_manager.get_pace_data(selected_struct, target_year)

if df_pace.empty:
    st.error("Non è stato possibile recuperare dati per questa struttura/anno.")
    st.stop()

# Messaggio informativo sulla qualità del confronto
if meta['is_exact_pace']:
    st.success(f"✅ Confronto esatto: Oggi ({meta['date_recent'].strftime('%d/%m/%y')}) vs Anno Scorso ({meta['date_old'].strftime('%d/%m/%y')})")
else:
    st.warning(f"⚠️ Pace Parziale: Confronto tra oggi e il primo snapshot disponibile ({meta['date_old'].strftime('%d/%m/%y')})")

# --- ELABORAZIONE MENSILE ---
df_pace['MeseNum'] = df_pace['date'].dt.month
df_pace['Mese'] = df_pace['date'].dt.strftime('%b')

monthly_pace = df_pace.groupby(['MeseNum', 'Mese']).agg({
    'revenue_curr': 'sum',
    'revenue_ly': 'sum',
    'rooms_sold_curr': 'sum',
    'rooms_sold_ly': 'sum'
}).reset_index().sort_values('MeseNum')

# Calcolo Delta
monthly_pace['Delta Rev'] = monthly_pace['revenue_curr'] - monthly_pace['revenue_ly']
monthly_pace['Delta %'] = (monthly_pace['Delta Rev'] / monthly_pace['revenue_ly'] * 100).fillna(0)

# --- SEZIONE 1: KPI TOTALI ---
tot_rev_curr = monthly_pace['revenue_curr'].sum()
tot_rev_ly = monthly_pace['revenue_ly'].sum()
delta_global = tot_rev_curr - tot_rev_ly

k1, k2, k3 = st.columns(3)
k1.metric("Fatturato OTB 2026", f"€ {tot_rev_curr:,.0f}")
k2.metric("Fatturato OTB LY", f"€ {tot_rev_ly:,.0f}", help="Situazione nello stesso momento dell'anno scorso")
k3.metric("Pace Delta", f"€ {delta_global:,.0f}", delta=f"{delta_global:,.0f}", delta_color="normal")

st.divider()

# --- SEZIONE 2: GRAFICO PACE REVENUE ---
st.subheader("📊 Confronto Fatturato Mensile: Attuale vs Anno Scorso")

fig_pace = go.Figure()

# Barre Anno Scorso (Sfondo)
fig_pace.add_trace(go.Bar(
    x=monthly_pace['Mese'],
    y=monthly_pace['revenue_ly'],
    name='Fatturato LY (Stesso momento)',
    marker_color='lightgrey',
    opacity=0.7
))

# Barre Anno Corrente
fig_pace.add_trace(go.Bar(
    x=monthly_pace['Mese'],
    y=monthly_pace['revenue_curr'],
    name='Fatturato Attuale',
    marker_color='#1f77b4'
))

fig_pace.update_layout(
    barmode='group',
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis_title="",
    yaxis_title="Euro (€)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig_pace, use_container_width=True)

# --- SEZIONE 3: TABELLA DETTAGLIO ---
st.subheader("📋 Dettaglio Numerico per Mese")

def style_delta(val):
    color = 'green' if val >= 0 else 'red'
    return f'color: {color}; font-weight: bold;'

# Calcoliamo l'altezza dinamica (35px per riga + testata)
height_table = (len(monthly_pace) + 1) * 35 + 3

st.dataframe(
    monthly_pace[['Mese', 'revenue_curr', 'revenue_ly', 'Delta Rev', 'Delta %']].style
    .format({'revenue_curr': '€ {:,.0f}', 'revenue_ly': '€ {:,.0f}', 'Delta Rev': '€ {:+,.0f}', 'Delta %': '{:+.1f}%'})
    .map(style_delta, subset=['Delta Rev', 'Delta %']),
    use_container_width=True,
    height=height_table  # <--- AGGIUNTO QUESTO PER BLOCCARE L'ALTEZZA
)

st.info("""
**Legenda Pace:**
- **Fatturato Attuale:** Quanto hai già venduto oggi per i mesi futuri.
- **Fatturato LY:** Quanto avevi venduto l'anno scorso (nello stesso giorno) per i mesi futuri di allora.
- Se il **Delta è positivo (Verde)**, stai correndo più veloce dell'anno scorso!
""")