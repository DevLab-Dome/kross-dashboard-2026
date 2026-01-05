import streamlit as st
import pandas as pd
import altair as alt
import datetime
from services import forecast_manager

# Configurazione Pagina
st.set_page_config(page_title="Analisi Dettaglio", layout="wide", initial_sidebar_state="collapsed")

# --- CSS BASE ---
st.markdown("""
<style>
    .centered-header { text-align: center; font-weight: bold; margin-bottom: 20px; }
    div[data-testid="stMetric"] { background-color: transparent; border: none; box-shadow: none; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔧 Filtri")
    strutture_options = ["Lavagnini My Place", "La Terrazza di Jenny", "B&B Pitti Palace"]
    
    if 'selected_struct' not in st.session_state:
        st.session_state.selected_struct = strutture_options[0]
    
    selected_struct = st.selectbox("Seleziona Struttura", strutture_options, key='struct_detail')
    st.session_state.selected_struct = selected_struct
    
    if 'selected_year' not in st.session_state:
        st.session_state.selected_year = datetime.datetime.now().year
    
    selected_year = st.sidebar.number_input("Anno Analisi", min_value=2020, max_value=2030, value=st.session_state.selected_year)
    past_year = selected_year - 1
    
    st.info("💡 Usa questa pagina per analizzare trend, comportamenti settimanali e anomalie.")
    st.divider()
    use_ita = True

st.session_state.selected_year = selected_year

# --- CARICAMENTO DATI ---
st.title(f"📈 Analisi Dettaglio: {selected_struct} {selected_year}")

# Carichiamo entrambi gli anni
df, info = forecast_manager.get_consolidated_data(selected_struct, selected_year, force_italian_date=use_ita)
df_past, info_past = forecast_manager.get_consolidated_data(selected_struct, past_year, force_italian_date=use_ita)

if df.empty:
    st.error(f"Nessun dato trovato per {selected_struct} nel {selected_year}.")
    st.stop()

# Colonne ausiliarie
df['GiornoSettimana'] = df['date'].dt.day_name()
df['GiornoIdx'] = df['date'].dt.dayofweek
giorni_it = {
    'Monday': 'Lunedì', 'Tuesday': 'Martedì', 'Wednesday': 'Mercoledì', 
    'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato', 'Sunday': 'Domenica'
}
df['GiornoLabel'] = df['GiornoSettimana'].map(giorni_it)

# --- SEZIONE 1: TREND ANNUALE ---
st.header("1️⃣ Trend Revenue & ADR")
st.caption("Barre Blu = Revenue | Linea Rossa = ADR")

mesi_disponibili = df['date'].dt.strftime('%B').unique()
opzioni_mesi = ["Tutto l'anno"] + list(mesi_disponibili)
filtro_mese = st.selectbox("🔎 Filtra Periodo:", opzioni_mesi)

df_chart = df.copy()
if filtro_mese != "Tutto l'anno":
    df_chart = df[df['date'].dt.strftime('%B') == filtro_mese]

base = alt.Chart(df_chart).encode(x=alt.X('date:T', axis=alt.Axis(format='%d/%m', title='Data')))
bar = base.mark_bar(color='#4c78a8', opacity=0.8).encode(
    y=alt.Y('revenue:Q', axis=alt.Axis(title='Revenue (€)', titleColor='#4c78a8')),
    tooltip=['date', 'revenue', 'rooms_sold', 'adr']
)
line = base.mark_line(color='#d62728', strokeWidth=3).encode(
    y=alt.Y('adr:Q', axis=alt.Axis(title='ADR (€)', titleColor='#d62728')),
    tooltip=['date', 'adr']
)
chart = alt.layer(bar, line).resolve_scale(y='independent').properties(height=350).interactive()
st.altair_chart(chart, use_container_width=True)

st.divider()

# --- SEZIONE 2: DAY OF WEEK ---
st.header("2️⃣ Performance Settimanale")
st.caption("Confronto medio per giorno della settimana.")

dow_stats = df.groupby(['GiornoIdx', 'GiornoLabel']).agg({
    'revenue': 'mean', 'adr': 'mean', 'occupancy_pct': 'mean'
}).reset_index().sort_values('GiornoIdx')

c1, c2 = st.columns(2)
with c1:
    st.subheader("ADR Medio")
    chart_adr = alt.Chart(dow_stats).mark_bar(color='#d62728').encode(
        x=alt.X('GiornoLabel:N', sort=list(giorni_it.values()), title=None),
        y=alt.Y('adr:Q', title='€'),
        tooltip=['GiornoLabel', alt.Tooltip('adr', format='.2f')]
    ).properties(height=250)
    st.altair_chart(chart_adr, use_container_width=True)

with c2:
    st.subheader("Occupazione Media")
    chart_occ = alt.Chart(dow_stats).mark_bar(color='#2ca02c').encode(
        x=alt.X('GiornoLabel:N', sort=list(giorni_it.values()), title=None),
        y=alt.Y('occupancy_pct:Q', title='%'),
        tooltip=['GiornoLabel', alt.Tooltip('occupancy_pct', format='.1f')]
    ).properties(height=250)
    st.altair_chart(chart_occ, use_container_width=True)

st.divider()

# --- SEZIONE 3: RADAR ANOMALIE (NUOVA VERSIONE VISUALE) ---
st.header("3️⃣ Gap Analysis: Dove perdo e dove guadagno?")
st.caption(f"Confronto giorno per giorno rispetto al {past_year}. Le barre rosse indicano giorni dove stai incassando meno dell'anno scorso.")

if not df_past.empty:
    # 1. Merge Dati
    df['key_date'] = df['date'].dt.strftime('%m-%d')
    df_past['key_date'] = df_past['date'].dt.strftime('%m-%d')
    
    df_merge = pd.merge(
        df[['date', 'key_date', 'revenue', 'adr']],
        df_past[['key_date', 'revenue', 'adr']],
        on='key_date',
        suffixes=('', '_past'),
        how='inner'
    )
    
    # 2. Calcolo Differenza
    df_merge['Delta_Rev'] = df_merge['revenue'] - df_merge['revenue_past']
    
    # Colore per il grafico: Verde se positivo, Rosso se negativo
    df_merge['Colore'] = df_merge['Delta_Rev'].apply(lambda x: '#2ca02c' if x >= 0 else '#d62728')

    # Filtro grafico in base alla selezione del mese (se attivo)
    df_merge_chart = df_merge.copy()
    if filtro_mese != "Tutto l'anno":
        df_merge_chart = df_merge[df_merge['date'].dt.strftime('%B') == filtro_mese]

    # 3. GRAFICO GAP (BAR CHART DIVERGENTE)
    gap_chart = alt.Chart(df_merge_chart).mark_bar().encode(
        x=alt.X('date:T', axis=alt.Axis(format='%d/%m', title='Data')),
        y=alt.Y('Delta_Rev:Q', title='Differenza Revenue (€)'),
        color=alt.Color('Colore:N', scale=None, legend=None),
        tooltip=[
            alt.Tooltip('date', title='Data', format='%d/%m/%Y'),
            alt.Tooltip('revenue', title=f'Rev {selected_year}', format=',.0f'),
            alt.Tooltip('revenue_past', title=f'Rev {past_year}', format=',.0f'),
            alt.Tooltip('Delta_Rev', title='Differenza', format='+.0f')
        ]
    ).properties(height=300).interactive()
    
    st.altair_chart(gap_chart, use_container_width=True)

    # 4. TABELLA DEI "WORST 10" (I GIORNI PEGGIORI)
    st.subheader("⚠️ Top 10 Giorni Critici (Perdite Maggiori)")
    
    # Filtriamo solo i giorni negativi e li ordiniamo
    worst_days = df_merge[df_merge['Delta_Rev'] < 0].sort_values('Delta_Rev', ascending=True).head(10)
    
    if not worst_days.empty:
        worst_days_show = worst_days[['date', 'revenue', 'revenue_past', 'Delta_Rev', 'adr', 'adr_past']].copy()
        worst_days_show['date'] = worst_days_show['date'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(
            worst_days_show.style.format({
                'revenue': '€ {:,.0f}', 'revenue_past': '€ {:,.0f}', 'Delta_Rev': '€ {:,.0f}',
                'adr': '€ {:.2f}', 'adr_past': '€ {:.2f}'
            }).background_gradient(cmap='Reds_r', subset=['Delta_Rev']), # Rosso scuro per le perdite alte
            use_container_width=True,
            column_config={
                "date": "Data",
                "revenue": f"Rev {selected_year}",
                "revenue_past": f"Rev {past_year}",
                "Delta_Rev": "Perdita €",
                "adr": f"ADR {selected_year}",
                "adr_past": f"ADR {past_year}"
            }
        )
    else:
        st.success(f"Incredibile! Non c'è un solo giorno in cui stai perdendo rispetto al {past_year} nel periodo analizzato.")

else:
    st.warning("Dati storici non sufficienti per calcolare il Gap Analysis.")
