import streamlit as st
import pandas as pd
import datetime
import altair as alt
import plotly.express as px  # AGGIUNTO PER HEATMAP
from services import forecast_manager

st.set_page_config(page_title="Confronto Pickup", layout="wide", initial_sidebar_state="collapsed")

# --- CSS STILE ---
st.markdown("""
<style>
    .centered-header { text-align: center; font-weight: bold; }
    /* Stile per le metriche */
    div[data-testid="stMetric"] { 
        background-color: transparent; 
        border: 1px solid #e6e6e6; 
        padding: 15px; 
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* Miglioramento visuale delle Pills */
    div[data-testid="stPills"] {
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔧 Filtri Pickup")
    strutture_options = ["Lavagnini My Place", "La Terrazza di Jenny", "B&B Pitti Palace"]
    if 'selected_struct' not in st.session_state: st.session_state.selected_struct = strutture_options[0]
    selected_struct = st.selectbox("Struttura", strutture_options, key='struct_pickup')
    if 'selected_year' not in st.session_state: st.session_state.selected_year = datetime.datetime.now().year
    selected_year = st.sidebar.number_input("Anno", min_value=2024, max_value=2030, value=st.session_state.selected_year)
    st.divider()

st.title(f"🚀 Analisi Pickup: {selected_struct} {selected_year}")

# --- 1. CARICAMENTO LISTA FILE ---
df_snaps = forecast_manager.get_available_snapshots(selected_struct, selected_year)

if df_snaps.empty:
    st.warning(f"⚠️ Nessuno storico trovato. Assicurati che i file su Cloud abbiano la data nel nome (es. 08022025).")
    st.stop()

# --- 2. GESTIONE SELEZIONE (PILLS + MANUALE) ---
latest_snap = df_snaps.iloc[0]
latest_date = latest_snap['date']
file_recent = latest_snap['filename']

col_preset, col_manual = st.columns([2, 3])

with col_preset:
    st.write("**Periodo di Analisi:**")
    period_map = {"1 Giorno": 1, "3 Giorni": 3, "7 Giorni": 7, "30 Giorni": 30}
    
    selected_period = st.pills(
        "Seleziona intervallo",
        options=list(period_map.keys()),
        default="1 Giorno",
        selection_mode="single",
        label_visibility="collapsed"
    )
    
    days_back = period_map[selected_period]

target_date = latest_date - datetime.timedelta(days=days_back)
past_candidates = df_snaps[df_snaps['date'] <= target_date]

if not past_candidates.empty:
    file_old_auto = past_candidates.iloc[0]['filename']
else:
    file_old_auto = df_snaps.iloc[-1]['filename']

with col_manual:
    st.write(f"**Dettaglio File:** (Auto: -{days_back}gg)")
    c_rec, c_old = st.columns(2)
    
    file_map = dict(zip(df_snaps['filename'], df_snaps['label']))
    idx_old_auto = df_snaps[df_snaps['filename'] == file_old_auto].index[0]
    
    sel_rec = c_rec.selectbox("Oggi", df_snaps['filename'], format_func=lambda x: file_map[x], index=0)
    sel_old = c_old.selectbox("Passato", df_snaps['filename'], format_func=lambda x: file_map[x], index=int(idx_old_auto))

if sel_rec == sel_old:
    st.warning("Stai confrontando lo stesso file. Il Pickup sarà zero.")
    st.stop()

# --- 3. CALCOLO DATI ---
with st.spinner(f"Calcolo Pickup..."):
    df_pickup = forecast_manager.get_pickup_data(selected_struct, selected_year, sel_rec, sel_old)

if df_pickup.empty:
    st.error("Errore dati.")
    st.stop()

# --- 4. LIVELLO 1: KPI ANNUALI ---
st.subheader("1️⃣ Variazioni Totali (Intero Anno)")

tot_rev_pickup = df_pickup['pickup_revenue'].sum()
tot_rooms_pickup = df_pickup['pickup_rooms'].sum()

tot_rev_curr = df_pickup['revenue_curr'].sum()
tot_rooms_curr = df_pickup['rooms_sold_curr'].sum()
global_adr_curr = tot_rev_curr / tot_rooms_curr if tot_rooms_curr > 0 else 0

tot_rev_prev = df_pickup['revenue_prev'].sum()
tot_rooms_prev = df_pickup['rooms_sold_prev'].sum()
global_adr_prev = tot_rev_prev / tot_rooms_prev if tot_rooms_prev > 0 else 0

delta_adr_global = global_adr_curr - global_adr_prev

tot_capacity = df_pickup['rooms_curr'].sum() if 'rooms_curr' in df_pickup.columns else 1 
global_revpar_curr = tot_rev_curr / tot_capacity
global_revpar_prev = tot_rev_prev / tot_capacity
delta_revpar_global = global_revpar_curr - global_revpar_prev

k1, k2, k3, k4 = st.columns(4)
k1.metric("Pickup Revenue", f"€ {tot_rev_pickup:+,.0f}")
k2.metric("Pickup Notti", f"{tot_rooms_pickup:+,.0f}")
k3.metric("Var. ADR Globale", f"€ {delta_adr_global:+.2f}")
k4.metric("Var. RevPAR", f"€ {delta_revpar_global:+.2f}")

st.divider()

# --- 5. LIVELLO 2: GRIGLIA MENSILE ---
st.subheader("2️⃣ Dettaglio Mensile")

df_pickup['MeseNum'] = df_pickup['date'].dt.month
df_pickup['Mese'] = df_pickup['date'].dt.strftime('%B')

monthly = df_pickup.groupby(['MeseNum', 'Mese']).agg({
    'revenue_curr': 'sum',
    'revenue_prev': 'sum',
    'rooms_sold_curr': 'sum',
    'rooms_sold_prev': 'sum',
    'pickup_revenue': 'sum', 
    'pickup_rooms': 'sum'    
}).reset_index().sort_values('MeseNum')

monthly['adr_curr'] = monthly['revenue_curr'] / monthly['rooms_sold_curr']
monthly['adr_prev'] = monthly['revenue_prev'] / monthly['rooms_sold_prev']
monthly['delta_adr'] = monthly['adr_curr'] - monthly['adr_prev']
monthly['delta_adr'] = monthly['delta_adr'].fillna(0) 

def color_delta(val):
    if val == 0: return 'color: inherit; opacity: 0.4'
    color = '#28a745' if val > 0 else '#dc3545'
    return f'color: {color}; font-weight: bold;'

st.dataframe(
    monthly[['Mese', 'pickup_revenue', 'pickup_rooms', 'delta_adr', 'revenue_curr']].style
    .map(color_delta, subset=['pickup_revenue', 'pickup_rooms', 'delta_adr'])
    .format({
        'pickup_revenue': '€ {:+,.0f}',
        'pickup_rooms': '{:+,.0f}',
        'delta_adr': '€ {:+.2f}',
        'revenue_curr': '€ {:,.0f}'
    }),
    use_container_width=True,
    column_config={
        "pickup_revenue": "Var. Revenue",
        "pickup_rooms": "Var. Notti",
        "delta_adr": "Var. ADR",
        "revenue_curr": "Totale Attuale"
    },
    height=(len(monthly) + 1) * 35 + 3
)

st.divider()

# --- [NUOVO] LIVELLO 3: TOP & FLOP ---
st.subheader("3️⃣ Top & Flop Dates")
tf1, tf2 = st.columns(2)

with tf1:
    st.markdown("##### 🟢 Migliori Pickup")
    top_gainers = df_pickup.nlargest(3, 'pickup_revenue')
    for _, row in top_gainers.iterrows():
        if row['pickup_revenue'] > 0:
            st.success(f"**{row['date'].strftime('%d/%m')}**: +€ {row['pickup_revenue']:,.0f} ({row['pickup_rooms']:.0f} camere)")
        else:
            st.write("-")

with tf2:
    st.markdown("##### 🔴 Peggiori Cali")
    top_losers = df_pickup.nsmallest(3, 'pickup_revenue')
    for _, row in top_losers.iterrows():
        if row['pickup_revenue'] < 0:
            st.error(f"**{row['date'].strftime('%d/%m')}**: -€ {abs(row['pickup_revenue']):,.0f} ({row['pickup_rooms']:.0f} camere)")
        else:
            st.write("-")

st.divider()

# --- [NUOVO] LIVELLO 4: HEATMAP VISUALE ---
st.subheader("4️⃣ Heatmap Temporale (Revenue)")
st.markdown("Intensità del pickup nel tempo: **Verde** = Crescita, **Rosso** = Cancellazioni.")

# Grafico Plotly
fig_heat = px.bar(
    df_pickup, 
    x='date', 
    y='pickup_revenue',
    color='pickup_revenue',
    color_continuous_scale=['#FF4B4B', '#FFFFFF', '#00C853'], # Rosso - Bianco - Verde
    labels={'pickup_revenue': 'Pickup €', 'date': 'Data'}
)
fig_heat.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis_title="",
    yaxis_title="Variazione €",
    height=350,
    showlegend=False
)
# Linea dello zero
fig_heat.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.3)
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# --- 5. LIVELLO 5 (ex 3): DETTAGLIO GIORNALIERO ---
st.subheader("5️⃣ Dettaglio Giornaliero (Solo Variazioni)")

daily_movers = df_pickup[
    (df_pickup['pickup_revenue'].abs() > 0) | (df_pickup['pickup_rooms'].abs() > 0)
].copy()

if daily_movers.empty:
    st.info("Nessuna variazione giornaliera rilevata nel periodo selezionato.")
else:
    daily_movers['date_str'] = daily_movers['date'].dt.strftime('%d/%m %a')
    daily_movers = daily_movers.set_index('date_str')
    
    dynamic_height = (len(daily_movers) + 1) * 35 + 3
    
    st.dataframe(
        daily_movers[['pickup_revenue', 'pickup_rooms', 'pickup_adr', 'revenue_curr']].style
        .map(color_delta, subset=['pickup_revenue', 'pickup_rooms'])
        .map(color_delta, subset=['pickup_adr'])
        .background_gradient(cmap='Blues', subset=['revenue_curr'])
        .format({
            'pickup_revenue': '€ {:+,.0f}',
            'pickup_rooms': '{:+,.0f}',
            'pickup_adr': '€ {:+.2f}', 
            'revenue_curr': '€ {:,.0f}'
        }),
        use_container_width=True,
        column_config={
            "pickup_revenue": "Var. Rev",
            "pickup_rooms": "Var. Notti",
            "pickup_adr": "Var. ADR", 
            "revenue_curr": "Totale Attuale"
        },
        height=dynamic_height
    )
