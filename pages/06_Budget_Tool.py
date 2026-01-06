import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from datetime import datetime

# --- 1. CONFIGURAZIONE PAGINA (Layout Wide obbligatorio) ---
st.set_page_config(page_title="Budget Tool", layout="wide")

# --- 2. FIX PERCORSI ---
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from utils.data_manager import ForecastManager
    forecast_manager = ForecastManager()
except Exception as e:
    st.error(f"⚠️ Errore di connessione: {e}")
    st.stop()

# --- 3. INTERFACCIA TITOLO ---
st.title("🛠️ Budget Tool")
st.markdown("Confronta i dati storici del 2025 con i nuovi obiettivi per il **Budget 2026**.")

# --- 4. SIDEBAR FILTRI ---
st.sidebar.header("Configurazione")
selected_struct = st.sidebar.selectbox("Struttura", ["Lavagnini", "La Terrazza", "Pitti Palace"])
base_year = st.sidebar.selectbox("Anno Base (Storico)", [2025, 2024], index=0)
target_year = 2026

# --- 5. CARICAMENTO DATI ---
df_base, msg = forecast_manager.get_consolidated_data(selected_struct, base_year)

if not df_base.empty:
    # --- 6. PARAMETRI DI CRESCITA TARGET (Globali) ---
    st.subheader("🎛️ Parametri di Crescita Target (Globali)")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        mod_occ = st.slider("Incremento OCC % (Default Annuale)", -15.0, 20.0, 2.0)
    with col2:
        mod_adr = st.slider("Incremento ADR % (Default Annuale)", -10.0, 40.0, 5.0)
    with col3:
        # Mapping dinamico unità per precisione calcolo
        n_camere = 5 if "Pitti" not in selected_struct else 10
        st.metric("Unità Gestite", n_camere)

    # --- 6.5. PERSONALIZZAZIONE MENSILE (Taylor-made) ---
    with st.expander("🎨 Personalizzazione Mensile Target"):
        st.markdown("**Imposta incrementi specifici per mese** (lascia a 0 per usare il valore globale)")
        
        # Lista dei mesi
        mesi = [
            '01 - January', '02 - February', '03 - March', '04 - April',
            '05 - May', '06 - June', '07 - July', '08 - August',
            '09 - September', '10 - October', '11 - November', '12 - December'
        ]
        
        monthly_occ = {}
        monthly_adr = {}
        
        # --- SEZIONE OCC ---
        st.markdown("#### 📊 Incremento OCC % per Mese")
        
        # Dividi i 12 mesi in 3 righe da 4 colonne
        for row_idx in range(3):
            cols = st.columns(4)
            for col_idx in range(4):
                mese_idx = row_idx * 4 + col_idx
                if mese_idx < len(mesi):
                    mese = mesi[mese_idx]
                    with cols[col_idx]:
                        monthly_occ[mese] = st.number_input(
                            f"{mese}",
                            min_value=-15.0,
                            max_value=20.0,
                            value=0.0,
                            step=0.5,
                            key=f"occ_{mese}",
                            help="0 = usa valore globale",
                            label_visibility="visible"
                        )
        
        st.divider()
        
        # --- SEZIONE ADR ---
        st.markdown("#### 💵 Incremento ADR % per Mese")
        
        # Dividi i 12 mesi in 3 righe da 4 colonne
        for row_idx in range(3):
            cols = st.columns(4)
            for col_idx in range(4):
                mese_idx = row_idx * 4 + col_idx
                if mese_idx < len(mesi):
                    mese = mesi[mese_idx]
                    with cols[col_idx]:
                        monthly_adr[mese] = st.number_input(
                            f"{mese}",
                            min_value=-10.0,
                            max_value=40.0,
                            value=0.0,
                            step=0.5,
                            key=f"adr_{mese}",
                            help="0 = usa valore globale",
                            label_visibility="visible"
                        )

    # --- 7. MOTORE DI CALCOLO CON LOGICA MENSILE ---
    df_sim = df_base.copy()
    df_sim['Mese'] = df_sim['date'].dt.strftime('%m - %B')
    
    # Applica incrementi personalizzati per mese
    def apply_increment(row, metric, default_value, monthly_values):
        """Applica incremento personalizzato se != 0, altrimenti usa default"""
        mese = row['Mese']
        custom_value = monthly_values.get(mese, 0.0)
        
        # Se custom_value è 0, usa il default globale
        increment = custom_value if custom_value != 0.0 else default_value
        
        if metric == 'occ':
            # Calcola il nuovo valore e clippalo tra 0 e 100 usando min/max
            new_value = row['occupancy_pct'] * (1 + increment/100)
            return min(max(new_value, 0), 100)
        elif metric == 'adr':
            return row['adr'] * (1 + increment/100)
    
    df_sim['target_occ'] = df_sim.apply(
        lambda row: apply_increment(row, 'occ', mod_occ, monthly_occ), axis=1
    )
    df_sim['target_adr'] = df_sim.apply(
        lambda row: apply_increment(row, 'adr', mod_adr, monthly_adr), axis=1
    )
    df_sim['target_rev'] = (n_camere * (df_sim['target_occ'] / 100)) * df_sim['target_adr']

    # --- 8. AGGREGAZIONE E CONFRONTO ---
    budget_mensile = df_sim.groupby('Mese').agg({
        'occupancy_pct': 'mean', # Storico
        'target_occ': 'mean',    # Target
        'adr': 'mean',           # Storico
        'target_adr': 'mean',    # Target
        'revenue': 'sum',        # Storico
        'target_rev': 'sum'      # Target
    }).reset_index()

    # Calcolo Scostamento assoluto e percentuale
    budget_mensile['Extra Rev'] = budget_mensile['target_rev'] - budget_mensile['revenue']
    budget_mensile['Growth %'] = ((budget_mensile['target_rev'] - budget_mensile['revenue']) / budget_mensile['revenue'] * 100).fillna(0)

    # Rinominiamo per una tabella pulita e leggibile
    budget_mensile.columns = [
        'Mese', 'OCC 2025 %', 'Target OCC %', 
        'ADR 2025 (€)', 'Target ADR (€)', 
        'Revenue 2025 (€)', 'Target Revenue (€)', 'Extra Rev (€)', 'Growth %'
    ]

    # --- 9. VISUALIZZAZIONE CON EVIDENZIAZIONE CONDIZIONALE ---
    st.subheader(f"📊 Analisi Comparativa Budget {target_year} vs {base_year}")
    
    # Funzione di styling condizionale per le righe
    def highlight_growth(row):
        growth = row['Growth %']
        
        if growth >= 7:
            color = '#ffcc80'  # Arancione chiaro
        elif 4 <= growth < 7:
            color = '#fff9c4'  # Giallo tenue
        else:
            color = 'white'    # Standard
        
        return ['background-color: {}'.format(color)] * len(row)
    
    # Calcola altezza dinamica: 38px per header + 35px per riga
    dynamic_height = 38 + (len(budget_mensile) * 35)
    
    styled_df = budget_mensile.style.format({
        'OCC 2025 %': '{:.1f}%', 
        'Target OCC %': '{:.1f}%',
        'ADR 2025 (€)': '€ {:.2f}', 
        'Target ADR (€)': '€ {:.2f}',
        'Revenue 2025 (€)': '€ {:,.0f}', 
        'Target Revenue (€)': '€ {:,.0f}',
        'Extra Rev (€)': '€ {:,.0f}',
        'Growth %': '{:.1f}%'
    }).apply(highlight_growth, axis=1).background_gradient(
        subset=['Extra Rev (€)'], 
        cmap='Greens'
    )
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=dynamic_height
    )
    
    # Legenda colori
    st.caption("🟡 **Giallo**: Crescita 4-6% | 🟠 **Arancione**: Crescita ≥7% | ⚪ **Bianco**: Crescita <4%")
    
    st.divider()
    
    # --- 9.5. RIEPILOGO FINANZIARIO (Grafica Simmetrica) ---
    # Titolo centrato
    st.markdown("<h2 style='text-align: center;'>💰 Riepilogo Finanziario</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Calcola i totali
    tot_2025 = budget_mensile['Revenue 2025 (€)'].sum()
    tot_2026 = budget_mensile['Target Revenue (€)'].sum()
    incremento = tot_2026 - tot_2025
    incremento_pct = (incremento / tot_2025 * 100) if tot_2025 > 0 else 0
    
    # Griglia KPI centrata (3 colonne)
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.markdown(f"""
        <div style='text-align: center;'>
            <p style='font-size: 16px; color: #666; margin-bottom: 5px;'>📊 Revenue 2025 (Storico)</p>
            <p style='font-size: 32px; font-weight: bold; color: #1f77b4; margin: 0;'>€ {tot_2025:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_m2:
        st.markdown(f"""
        <div style='text-align: center;'>
            <p style='font-size: 16px; color: #666; margin-bottom: 5px;'>🎯 Target Revenue 2026</p>
            <p style='font-size: 32px; font-weight: bold; color: #2ca02c; margin: 0;'>€ {tot_2026:,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_m3:
        st.markdown(f"""
        <div style='text-align: center;'>
            <p style='font-size: 16px; color: #666; margin-bottom: 5px;'>🚀 Incremento Totale</p>
            <p style='font-size: 32px; font-weight: bold; color: #ff7f0e; margin: 0;'>€ {incremento:,.0f}</p>
            <p style='font-size: 18px; color: #ff7f0e; margin-top: 5px;'>(+{incremento_pct:.1f}%)</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Box diamante (già centrato)
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        color: white;
        font-size: 18px;
        font-weight: bold;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    ">
        💎 OBIETTIVO BUDGET 2026: <span style="font-size: 28px;">€ {tot_2026:,.0f}</span> 
        <br>
        <span style="font-size: 16px; opacity: 0.9;">
            (Crescita di € {incremento:,.0f} rispetto al 2025 • {incremento_pct:+.1f}%)
        </span>
    </div>
    """, unsafe_allow_html=True)

    # --- 10. SALVATAGGIO CON FIX DATE (2026) ---
    st.divider()
    st.subheader("💾 Salva Budget")
    
    # Selettore tipo budget
    budget_type = st.pills(
        "Seleziona il tipo di budget da salvare:",
        options=["Budget Ufficiale", "Budget di Test"],
        selection_mode="single",
        default="Budget di Test"
    )
    
    if budget_type == "Budget Ufficiale":
        st.info("📌 Il budget ufficiale sarà utilizzato dalla sezione **07 - Budget Target** per confronti e analisi.")
    else:
        st.info("🧪 Il budget di test è utile per simulazioni e prove senza sovrascrivere il budget ufficiale.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("💾 APPROVA E SALVA BUDGET 2026", use_container_width=True, type="primary"):
        try:
            # Prepara il DataFrame per il salvataggio
            df_to_save = df_sim[['date', 'target_occ', 'target_adr', 'target_rev']].copy()
            df_to_save.columns = ['date', 'occupancy_pct', 'adr', 'revenue']
            
            # FIX CRUCIALE: Aggiungi un anno alle date (da 2025 a 2026)
            df_to_save['date'] = pd.to_datetime(df_to_save['date']) + pd.offsets.DateOffset(years=1)
            
            # Determina il tipo di budget
            tipo = 'official' if budget_type == "Budget Ufficiale" else 'test'
            
            # Chiama la funzione di salvataggio
            success, info = forecast_manager.save_budget(
                df=df_to_save,
                struttura=selected_struct,
                anno=target_year,
                tipo=tipo
            )
            
            if success:
                st.success(f"✅ {budget_type} salvato con successo!")
                st.info(f"📁 Percorso: `{info}`")
                st.balloons()
            else:
                st.error(f"❌ Errore nel salvataggio: {info}")
                    
        except Exception as e:
            st.error(f"❌ Errore critico durante il salvataggio: {str(e)}")
            st.exception(e)

else:
    st.warning("⚠️ Dati non trovati. Verifica il caricamento della Baseline.")