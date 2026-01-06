import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sys
import os
from pathlib import Path
from io import BytesIO

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Budget Target", layout="wide")

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

# --- 3. CSS CUSTOM (Stile Overview) ---
st.markdown("""
<style>
    /* METRICHE - CONTENITORE */
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

    /* ETICHETTA */
    div[data-testid="stMetricLabel"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }
    
    div[data-testid="stMetricLabel"] * {
        text-align: center !important;
        justify-content: center !important;
        display: block !important; 
        font-size: 1.1rem !important;
        font-weight: 500 !important;
        color: var(--text-color) !important;
        opacity: 0.8;
    }
    
    /* VALORE */
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
    
    /* DELTA */
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

    /* TITOLI CENTRATI */
    .centered-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: bold;
        color: var(--text-color);
        margin-bottom: 10px;
    }
    
    .centered-subtitle {
        text-align: center;
        font-size: 1rem;
        color: var(--text-color);
        opacity: 0.7;
        margin-bottom: 30px;
    }
    
    /* TITOLO SEZIONE KPI CENTRATO */
    .centered-section-title {
        text-align: center;
        font-size: 2rem;
        font-weight: bold;
        color: var(--text-color);
        margin-bottom: 20px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. INTERFACCIA TITOLO ---
st.markdown("<div class='centered-title'>🎯 Budget Target - Controllo di Gestione</div>", unsafe_allow_html=True)
st.markdown("<div class='centered-subtitle'>Confronto tra Budget Ufficiale e Performance Reale (OTB)</div>", unsafe_allow_html=True)

# --- 5. SIDEBAR FILTRI ---
st.sidebar.header("Configurazione")
strutture_options = ["Lavagnini", "La Terrazza", "Pitti Palace"]
selected_struct = st.sidebar.selectbox("Struttura", strutture_options, index=0)
target_year = st.sidebar.selectbox("Anno", [2025, 2026], index=1)

st.divider()

# --- 6. CARICAMENTO BUDGET UFFICIALE (SILENZIOSO) ---
def load_budget_official(struttura, anno):
    """Carica il budget ufficiale da S3"""
    try:
        folder_struct = struttura.replace(" ", "_")
        key = f"Budgets-Official/{folder_struct}-{anno}/budget_official.csv"
        
        file_obj = forecast_manager.s3.get_object(
            Bucket=forecast_manager.bucket, 
            Key=key
        )
        
        df = pd.read_csv(BytesIO(file_obj['Body'].read()))
        df['date'] = pd.to_datetime(df['date'])
        
        return df, True
        
    except Exception as e:
        return pd.DataFrame(), False


# --- 7. CARICAMENTO OTB (SILENZIOSO) ---
def load_otb_forecast(struttura, anno):
    """
    Carica i forecast OTB dal percorso: Forecast/{Struttura}/{Anno}/
    """
    try:
        # Normalizza nome struttura per S3
        folder_struct = struttura.replace(" ", "_")
        prefix = f"Forecast/{folder_struct}/{anno}/"
        
        response = forecast_manager.s3.list_objects_v2(
            Bucket=forecast_manager.bucket, 
            Prefix=prefix
        )
        
        if 'Contents' not in response:
            return pd.DataFrame(), False
        
        # Trova tutti i file Excel/CSV
        forecast_files = [
            obj['Key'] for obj in response['Contents'] 
            if obj['Key'].lower().endswith(('.csv', '.xlsx'))
        ]
        
        if not forecast_files:
            return pd.DataFrame(), False
        
        # Carica tutti i file e concatenali
        all_dfs = []
        for file_key in forecast_files:
            file_obj = forecast_manager.s3.get_object(
                Bucket=forecast_manager.bucket,
                Key=file_key
            )
            body = file_obj['Body'].read()
            
            if file_key.lower().endswith('.csv'):
                df = pd.read_csv(BytesIO(body))
            else:
                df = pd.read_excel(BytesIO(body))
            
            # Normalizza colonne (come in data_manager)
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            mappa_nomi = {
                'data': 'date',
                'occupate %': 'occupancy_pct',
                'occupancy %': 'occupancy_pct',
                'totale revenue': 'revenue',
                'ricavo': 'revenue',
                'adr': 'adr',
                'occupate': 'rooms_sold',
                'unità': 'rooms',
                'unita': 'rooms'
            }
            df.rename(columns=mappa_nomi, inplace=True)
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date'])
                
                # Garanzia colonne numeriche
                for col in ['adr', 'occupancy_pct', 'revenue', 'rooms_sold']:
                    if col not in df.columns:
                        df[col] = 0.0
                    
                    if df[col].dtype == object:
                        df[col] = df[col].astype(str).str.replace('€', '', regex=False)\
                                       .str.replace(',', '.', regex=False)\
                                       .str.strip()
                    
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # Fix occupancy se in formato decimale
                if 'occupancy_pct' in df.columns and df['occupancy_pct'].max() <= 1.0 and df['occupancy_pct'].max() > 0:
                    df['occupancy_pct'] = df['occupancy_pct'] * 100
                
                if 'rooms' in df.columns:
                    df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce').fillna(0)
                
                all_dfs.append(df)
        
        if all_dfs:
            consolidated = pd.concat(all_dfs).drop_duplicates(subset=['date'])
            return consolidated, True
        
        return pd.DataFrame(), False
        
    except Exception as e:
        return pd.DataFrame(), False


# --- 8. CARICAMENTO DATI ---
df_budget, budget_exists = load_budget_official(selected_struct, target_year)
df_otb, otb_exists = load_otb_forecast(selected_struct, target_year)

if not budget_exists:
    st.warning(f"⚠️ Budget Ufficiale non trovato per {selected_struct} ({target_year})")
    st.info("💡 Vai alla pagina **06 - Budget Tool** per creare e approvare il budget ufficiale.")
    st.stop()

if not otb_exists:
    st.warning(f"⚠️ Nessun forecast disponibile per {selected_struct} ({target_year})")
    st.info("💡 Assicurati che ci siano file forecast caricati nel percorso `Forecast/{Struttura}/{Anno}/`")
    st.stop()

# --- 9. CALCOLO KPI ANNUALI (Budget vs OTB) ---
def calc_kpi_from_df(df):
    """Calcola KPI da un DataFrame"""
    if df.empty:
        return 0, 0, 0, 0, 0
    
    rev = df['revenue'].sum()
    
    # Rooms Sold
    if 'rooms_sold' in df.columns:
        sold = df['rooms_sold'].sum()
    else:
        sold = 0
    
    # Capacità totale
    if 'rooms' in df.columns and df['rooms'].sum() > 0:
        cap = df['rooms'].sum()
    else:
        # Fallback: stima in base ai giorni
        n_camere = 5 if "Pitti" not in selected_struct else 10
        cap = len(df) * n_camere
    
    # KPI calcolati
    occ = (sold / cap * 100) if cap > 0 else 0
    adr = (rev / sold) if sold > 0 else 0
    revpar = (rev / cap) if cap > 0 else 0
    
    return rev, sold, adr, revpar, occ


# Calcola KPI per Budget e OTB
budget_rev, budget_sold, budget_adr, budget_revpar, budget_occ = calc_kpi_from_df(df_budget)
otb_rev, otb_sold, otb_adr, otb_revpar, otb_occ = calc_kpi_from_df(df_otb)

# Calcola Delta
delta_rev = otb_rev - budget_rev
delta_sold = otb_sold - budget_sold
delta_adr = otb_adr - budget_adr
delta_revpar = otb_revpar - budget_revpar
delta_occ = otb_occ - budget_occ

# --- 10. KPI HEADER (5 COLONNE - STILE OVERVIEW) ---
st.markdown("<h3 class='centered-section-title'>📊 Panoramica Annuale: OTB vs Budget</h3>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Revenue", f"€ {otb_rev:,.0f}", f"{delta_rev:,.0f} €")
k2.metric("Notti", f"{int(otb_sold)}", f"{int(delta_sold)}")
k3.metric("ADR", f"€ {otb_adr:.2f}", f"{delta_adr:.2f} €")
k4.metric("RevPAR", f"€ {otb_revpar:.2f}", f"{delta_revpar:.2f} €")
k5.metric("Occ %", f"{otb_occ:.2f}%", f"{delta_occ:.2f}%")

st.divider()

# --- 11. CONFRONTO MENSILE ---
st.subheader("📅 Confronto Mensile: Budget vs OTB")

# Aggrega per mese - BUDGET
df_budget['month'] = df_budget['date'].dt.month
df_budget['month_name'] = df_budget['date'].dt.strftime('%B')
budget_monthly = df_budget.groupby(['month', 'month_name'])['revenue'].sum().reset_index()
budget_monthly.columns = ['month', 'month_name', 'budget']

# Aggrega per mese - OTB
df_otb['month'] = df_otb['date'].dt.month
df_otb['month_name'] = df_otb['date'].dt.strftime('%B')
otb_monthly = df_otb.groupby(['month', 'month_name'])['revenue'].sum().reset_index()
otb_monthly.columns = ['month', 'month_name', 'otb']

# Crea DataFrame con tutti i 12 mesi
all_months = pd.DataFrame({
    'month': range(1, 13),
    'month_name': [datetime(2000, m, 1).strftime('%B') for m in range(1, 13)]
})

# Merge con budget e otb
comparison = all_months.merge(budget_monthly, on=['month', 'month_name'], how='left')
comparison = comparison.merge(otb_monthly, on=['month', 'month_name'], how='left')
comparison = comparison.fillna(0)

# Calcola Delta e Copertura
comparison['delta'] = comparison['otb'] - comparison['budget']
comparison['copertura_pct'] = (comparison['otb'] / comparison['budget'] * 100).replace([np.inf, -np.inf], 0).fillna(0)

# --- 12. GRAFICO PLOTLY (Budget vs OTB) ---
fig = go.Figure()

fig.add_trace(go.Bar(
    name='Budget Target',
    x=comparison['month_name'],
    y=comparison['budget'],
    marker_color='#667eea',
    text=comparison['budget'].apply(lambda x: f'€ {x:,.0f}' if x > 0 else ''),
    textposition='outside'
))

fig.add_trace(go.Bar(
    name='OTB Reale',
    x=comparison['month_name'],
    y=comparison['otb'],
    marker_color='#2ca02c',
    text=comparison['otb'].apply(lambda x: f'€ {x:,.0f}' if x > 0 else ''),
    textposition='outside'
))

fig.update_layout(
    barmode='group',
    title=f"Budget vs OTB - {selected_struct} {target_year}",
    xaxis_title="Mese",
    yaxis_title="Revenue (€)",
    height=500,
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 13. TABELLA DETTAGLIO (Zero Scroll - 12 Righe Fisse) ---
st.subheader("📋 Dettaglio Mensile")

# Prepara DataFrame per visualizzazione
detail_table = comparison[['month_name', 'budget', 'otb', 'delta', 'copertura_pct']].copy()
detail_table.columns = ['Mese', 'Target Budget (€)', 'OTB Reale (€)', 'Delta (€)', '% Copertura']

# Funzione per colorare Delta
def color_delta(val):
    color = '#28a745' if val >= 0 else '#dc3545'
    return f'color: {color}; font-weight: bold;'

# Funzione per colorare Copertura
def color_copertura(val):
    if val >= 100:
        return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif val >= 90:
        return 'background-color: #fff3cd; color: #856404;'
    else:
        return 'background-color: #f8d7da; color: #721c24;'

# Calcola altezza dinamica (12 righe fisse)
dynamic_height = 38 + (12 * 35)

# Applica styling
styled_table = detail_table.style\
    .format({
        'Target Budget (€)': '€ {:,.0f}',
        'OTB Reale (€)': '€ {:,.0f}',
        'Delta (€)': '{:+,.0f} €',
        '% Copertura': '{:.1f}%'
    })\
    .map(color_delta, subset=['Delta (€)'])\
    .map(color_copertura, subset=['% Copertura'])\
    .background_gradient(cmap='Blues', subset=['Target Budget (€)'])\
    .background_gradient(cmap='Greens', subset=['OTB Reale (€)'])

st.dataframe(
    styled_table,
    use_container_width=True,
    height=dynamic_height,
    column_config={
        'Mese': st.column_config.TextColumn('Mese', width='medium'),
        'Target Budget (€)': st.column_config.NumberColumn('Target Budget', format='€ %.0f'),
        'OTB Reale (€)': st.column_config.NumberColumn('OTB Reale', format='€ %.0f'),
        'Delta (€)': st.column_config.NumberColumn('Delta', format='%+.0f €'),
        '% Copertura': st.column_config.NumberColumn('% Copertura', format='%.1f%%')
    }
)

# Legenda
st.caption("🟢 **Verde**: Superato il budget | 🟡 **Giallo**: Raggiunto 90-99% | 🔴 **Rosso**: Sotto il 90%")

st.divider()

# --- 14. ANALISI AVANZATA ---
with st.expander("📊 Analisi Avanzata"):
    col_a1, col_a2 = st.columns(2)
    
    # Filtra solo mesi con dati reali (budget > 0)
    comparison_valid = comparison[comparison['budget'] > 0]
    
    with col_a1:
        st.markdown("### 🎯 Mesi Migliori")
        if not comparison_valid.empty:
            best_months = comparison_valid.nlargest(3, 'copertura_pct')[['month_name', 'copertura_pct']]
            for idx, row in best_months.iterrows():
                st.success(f"**{row['month_name']}**: {row['copertura_pct']:.1f}% di copertura")
        else:
            st.info("Nessun dato disponibile")
    
    with col_a2:
        st.markdown("### ⚠️ Mesi da Monitorare")
        if not comparison_valid.empty:
            worst_months = comparison_valid.nsmallest(3, 'copertura_pct')[['month_name', 'copertura_pct']]
            for idx, row in worst_months.iterrows():
                if row['copertura_pct'] < 90:
                    st.error(f"**{row['month_name']}**: {row['copertura_pct']:.1f}% di copertura")
                else:
                    st.warning(f"**{row['month_name']}**: {row['copertura_pct']:.1f}% di copertura")
        else:
            st.info("Nessun dato disponibile")

st.divider()

# --- 15. FOOTER ---
st.caption("Budget Target v1.0 | Confronto automatico tra Budget Ufficiale e Forecast OTB")