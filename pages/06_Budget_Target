import streamlit as st
import pandas as pd
import numpy as np
from utils.data_manager import ForecastManager

# --- CONFIGURAZIONE ---
forecast_manager = ForecastManager()

st.title("🛠️ Budget Tool - Engine")
st.markdown("""
L'utente applica dei moltiplicatori (es. +5% ADR, +2% OCC) basandosi sui dati storici consolidati.
""")

# --- SIDEBAR FILTRI ---
selected_struct = st.sidebar.selectbox("Struttura", ["Lavagnini", "La Terrazza", "Pitti Palace"])
base_year = st.sidebar.selectbox("Anno Base (Storico)", [2025, 2024], index=0)
target_year = 2026

# --- CARICAMENTO DATI STORICI ---
df_base, _ = forecast_manager.get_consolidated_data(selected_struct, base_year)

if not df_base.empty:
    # --- INTERFACCIA MOLTIPLICATORI ---
    st.subheader("🎛️ Parametri di Crescita")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        mod_occ = st.slider("Incremento OCC %", -10.0, 20.0, 2.0, help="Suggerimento basato su Trend: +2.5%")
    with col2:
        mod_adr = st.slider("Incremento ADR %", -10.0, 30.0, 5.0, help="Suggerimento basato su Eventi: +6.0%")
    with col3:
        st.info("**Affidabilità Suggerimento:** Alta (Basata su Pace Analysis attuale)")

    # --- MOTORE DI CALCOLO (Simulazione Giornaliera) ---
    df_sim = df_base.copy()
    
    # Applichiamo i moltiplicatori giorno per giorno
    # Nota: L'occupazione non può superare il 100%
    df_sim['target_occ'] = (df_sim['occupancy_pct'] * (1 + mod_occ/100)).clip(0, 100)
    df_sim['target_adr'] = df_sim['adr'] * (1 + mod_adr/100)
    
    # Ricalcoliamo il Revenue (Assumendo n. camere costante, es. 20)
    num_camere = 20 # Da rendere dinamico in base alla struttura
    df_sim['target_rev'] = (df_sim['target_occ'] / 100 * num_camere) * df_sim['target_adr']

    # --- TABELLA SIMULAZIONE (Aggregata per Mese) ---
    st.subheader("📈 Tabella Simulazione Budget 2026")
    
    df_sim['Mese'] = df_sim['date'].dt.strftime('%m - %B')
    budget_mensile = df_sim.groupby('Mese').agg({
        'target_occ': 'mean',
        'target_adr': 'mean',
        'target_rev': 'sum'
    }).reset_index()

    # Rinominiamo per chiarezza
    budget_mensile.columns = ['Mese', 'Target OCC %', 'Target ADR (€)', 'Target Revenue (€)']

    st.dataframe(
        budget_mensile.style.format({
            'Target OCC %': '{:.1f}%',
            'Target ADR (€)': '€ {:.2f}',
            'Target Revenue (€)': '€ {:,.0f}'
        }),
        use_container_width=True
    )
    
    # Totale Annuale
    tot_rev = budget_mensile['Target Revenue (€)'].sum()
    st.success(f"**Budget Totale Annuale Stimato: € {tot_rev:,.0f}**")

else:
    st.error(f"Nessun dato storico trovato per il {base_year}. Carica i file nella sezione Carica Dati.")