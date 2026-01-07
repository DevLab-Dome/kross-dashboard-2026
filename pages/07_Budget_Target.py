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

# --- 3. CSS MINIMO (SOLO TITOLI) ---
st.markdown("""
<style>
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

# --- 4. FUNZIONE: KPI CARD (IDENTICA A OVERVIEW) ---
def render_kpi_card(label, value_str, delta_num, format_type, container):
    """
    Renderizza una KPI card con STILI INLINE e SEGNO DELTA SEMPRE ESPLICITO
    
    Args:
        label: Titolo del KPI (es. "Revenue")
        value_str: Valore formattato da mostrare (es. "€ 10,000")
        delta_num: Valore numerico del delta per determinare il colore
        format_type: Tipo di formattazione ("currency", "number", "percent")
        container: Colonna Streamlit dove renderizzare
    """
    # Determina colore delta
    if delta_num >= 0:
        delta_color = "#28a745"
    else:
        delta_color = "#dc3545"
    
    # Formatta delta in base al tipo - SEMPRE CON SEGNO ESPLICITO
    if format_type == "currency":
        if delta_num >= 0:
            delta_formatted = f"+€ {abs(delta_num):,.0f}"
        else:
            delta_formatted = f"-€ {abs(delta_num):,.0f}"
    elif format_type == "percent":
        if delta_num >= 0:
            delta_formatted = f"+{delta_num:.2f}%"
        else:
            delta_formatted = f"{delta_num:.2f}%"
    else:  # number
        if delta_num >= 0:
            delta_formatted = f"+{int(delta_num)}"
        else:
            delta_formatted = f"{int(delta_num)}"
    
    # COSTRUISCI HTML
    html_content = f"""
    <div style="text-align: center; padding: 18px 12px; border-radius: 12px; background-color: #f8f9fa; border: 1px solid #e9ecef; min-height: 150px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
        <p style="color: #6c757d; font-size: 0.9rem; text-transform: uppercase; font-weight: 600; margin: 0 0 10px 0; letter-spacing: 0.8px; text-align: center;">
            {label}
        </p>
        <p style="color: #212529; font-size: 2.6rem; font-weight: 500; margin: 0; line-height: 1.1; text-align: center;">
            {value_str}
        </p>
        <p style="color: {delta_color}; font-size: 1.1rem; font-weight: 700; margin: 10px 0 0 0; text-align: center;">
            {delta_formatted}
        </p>
    </div>
    """
    
    # RENDERIZZA CON unsafe_allow_html=True
    with container:
        st.markdown(html_content, unsafe_allow_html=True)

# --- 5. INTERFACCIA TITOLO ---
st.markdown("<div class='centered-title'>🎯 Budget Target - Controllo di Gestione</div>", unsafe_allow_html=True)
st.markdown("<div class='centered-subtitle'>Confronto tra Budget Ufficiale e Performance Reale (OTB)</div>", unsafe_allow_html=True)

# --- 6. SIDEBAR FILTRI ---
st.sidebar.header("Configurazione")
strutture_options = ["Lavagnini", "La Terrazza", "Pitti Palace"]
selected_struct = st.sidebar.selectbox("Struttura", strutture_options, index=0)
target_year = st.sidebar.selectbox("Anno", [2025, 2026], index=1)

st.divider()

# --- 7. FUNZIONE NORMALIZZAZIONE COLONNE (UNIVERSALE) ---
def normalize_dataframe(df):
    """
    Normalizza i nomi delle colonne e garantisce che esistano tutte le colonne necessarie
    """
    # Converti tutti i nomi colonne in minuscolo
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # Mappatura nomi colonne (da vari formati possibili a standard)
    mappa_nomi = {
        'data': 'date',
        'occupate %': 'occupancy_pct',
        'occupancy %': 'occupancy_pct',
        'occ %': 'occupancy_pct',
        'totale revenue': 'revenue',
        'ricavo': 'revenue',
        'rev': 'revenue',
        'adr': 'adr',
        'occupate': 'rooms_sold',
        'sold': 'rooms_sold',
        'notti': 'rooms_sold',
        'unità': 'rooms',
        'unita': 'rooms',
        'capacity': 'rooms',
        'capacità': 'rooms'
    }
    df.rename(columns=mappa_nomi, inplace=True)
    
    # Converti date
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
    
    # Normalizza numeri
    for col in ['revenue', 'rooms_sold', 'adr', 'occupancy_pct', 'rooms']:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace('€', '', regex=False)\
                               .str.replace('.', '', regex=False)\
                               .str.replace(',', '.', regex=False)\
                               .str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Fix occupancy se in formato decimale
    if 'occupancy_pct' in df.columns and df['occupancy_pct'].max() <= 1.0 and df['occupancy_pct'].max() > 0:
        df['occupancy_pct'] = df['occupancy_pct'] * 100
    
    # Calcola rooms se mancante (stima basata su struttura)
    if 'rooms' not in df.columns or df['rooms'].sum() == 0:
        n_camere = 5 if "Pitti" not in selected_struct else 10
        df['rooms'] = n_camere
    
    # Calcola rooms_sold se mancante (da occupancy e capacity)
    if 'rooms_sold' not in df.columns or df['rooms_sold'].sum() == 0:
        if 'occupancy_pct' in df.columns and 'rooms' in df.columns:
            df['rooms_sold'] = (df['occupancy_pct'] / 100 * df['rooms']).round()
    
    return df

# --- 8. CARICAMENTO BUDGET UFFICIALE ---
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
        df = normalize_dataframe(df)
        
        return df, True
        
    except Exception as e:
        return pd.DataFrame(), False


# --- 9. CARICAMENTO OTB ---
def load_otb_forecast(struttura, anno):
    """
    Carica i forecast OTB dal percorso: Forecast/{Struttura}/{Anno}/
    """
    try:
        folder_struct = struttura.replace(" ", "_")
        prefix = f"Forecast/{folder_struct}/{anno}/"
        
        response = forecast_manager.s3.list_objects_v2(
            Bucket=forecast_manager.bucket, 
            Prefix=prefix
        )
        
        if 'Contents' not in response:
            return pd.DataFrame(), False
        
        forecast_files = [
            obj['Key'] for obj in response['Contents'] 
            if obj['Key'].lower().endswith(('.csv', '.xlsx'))
        ]
        
        if not forecast_files:
            return pd.DataFrame(), False
        
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
            
            df = normalize_dataframe(df)
            all_dfs.append(df)
        
        if all_dfs:
            consolidated = pd.concat(all_dfs).drop_duplicates(subset=['date'])
            return consolidated, True
        
        return pd.DataFrame(), False
        
    except Exception as e:
        return pd.DataFrame(), False


# --- 10. CARICAMENTO DATI ---
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

# --- 11. CALCOLO KPI ANNUALI (Budget vs OTB) ---
def calc_kpi_from_df(df):
    """Calcola KPI da un DataFrame"""
    if df.empty:
        return 0, 0, 0, 0, 0
    
    rev = df['revenue'].sum()
    sold = df['rooms_sold'].sum() if 'rooms_sold' in df.columns else 0
    cap = df['rooms'].sum() if 'rooms' in df.columns else len(df) * 5
    
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
delta_occ = otb_occ - budget_occ
delta_adr = otb_adr - budget_adr
delta_revpar = otb_revpar - budget_revpar

# --- 12. KPI HEADER - NUOVE CARD CUSTOM (ORDINE: Revenue | Notti | Occ % | ADR | RevPAR) ---
st.markdown("<h3 class='centered-section-title'>📊 Panoramica Annuale: OTB vs Budget</h3>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)

render_kpi_card("Revenue", f"€ {otb_rev:,.0f}", delta_rev, "currency", k1)
render_kpi_card("Notti", f"{int(otb_sold)}", delta_sold, "number", k2)
render_kpi_card("Occ %", f"{otb_occ:.2f}%", delta_occ, "percent", k3)
render_kpi_card("ADR", f"€ {otb_adr:.2f}", delta_adr, "currency", k4)
render_kpi_card("RevPAR", f"€ {otb_revpar:.2f}", delta_revpar, "currency", k5)

st.divider()

# --- 13. CONFRONTO MENSILE ---
st.subheader("📅 Confronto Mensile: Budget vs OTB")

# Aggrega per mese - BUDGET (con controlli robustezza)
df_budget['month'] = df_budget['date'].dt.month
df_budget['month_name'] = df_budget['date'].dt.strftime('%B')

# Verifica colonne disponibili
budget_agg_cols = {'revenue': 'sum'}
if 'rooms_sold' in df_budget.columns:
    budget_agg_cols['rooms_sold'] = 'sum'
if 'rooms' in df_budget.columns:
    budget_agg_cols['rooms'] = 'sum'

budget_monthly = df_budget.groupby(['month', 'month_name']).agg(budget_agg_cols).reset_index()

# Calcola ADR e Occ
if 'rooms_sold' in budget_monthly.columns:
    budget_monthly['adr_budget'] = budget_monthly['revenue'] / budget_monthly['rooms_sold']
else:
    budget_monthly['adr_budget'] = 0

if 'rooms' in budget_monthly.columns and 'rooms_sold' in budget_monthly.columns:
    budget_monthly['occ_budget'] = (budget_monthly['rooms_sold'] / budget_monthly['rooms'] * 100)
else:
    budget_monthly['occ_budget'] = 0

budget_monthly = budget_monthly[['month', 'month_name', 'revenue', 'adr_budget', 'occ_budget']]
budget_monthly.columns = ['month', 'month_name', 'budget', 'adr_budget', 'occ_budget']

# Aggrega per mese - OTB
df_otb['month'] = df_otb['date'].dt.month
df_otb['month_name'] = df_otb['date'].dt.strftime('%B')

otb_agg_cols = {'revenue': 'sum'}
if 'rooms_sold' in df_otb.columns:
    otb_agg_cols['rooms_sold'] = 'sum'
if 'rooms' in df_otb.columns:
    otb_agg_cols['rooms'] = 'sum'

otb_monthly = df_otb.groupby(['month', 'month_name']).agg(otb_agg_cols).reset_index()

# Calcola ADR e Occ
if 'rooms_sold' in otb_monthly.columns:
    otb_monthly['adr_otb'] = otb_monthly['revenue'] / otb_monthly['rooms_sold']
else:
    otb_monthly['adr_otb'] = 0

if 'rooms' in otb_monthly.columns and 'rooms_sold' in otb_monthly.columns:
    otb_monthly['occ_otb'] = (otb_monthly['rooms_sold'] / otb_monthly['rooms'] * 100)
else:
    otb_monthly['occ_otb'] = 0

otb_monthly = otb_monthly[['month', 'month_name', 'revenue', 'adr_otb', 'occ_otb']]
otb_monthly.columns = ['month', 'month_name', 'otb', 'adr_otb', 'occ_otb']

# Crea DataFrame con tutti i 12 mesi
all_months = pd.DataFrame({
    'month': range(1, 13),
    'month_name': [datetime(2000, m, 1).strftime('%B') for m in range(1, 13)]
})

# Merge
comparison = all_months.merge(budget_monthly, on=['month', 'month_name'], how='left')
comparison = comparison.merge(otb_monthly, on=['month', 'month_name'], how='left')
comparison = comparison.fillna(0)

# Calcola Delta
comparison['delta_rev'] = comparison['otb'] - comparison['budget']
comparison['delta_adr'] = comparison['adr_otb'] - comparison['adr_budget']
comparison['delta_occ'] = comparison['occ_otb'] - comparison['occ_budget']
comparison['copertura_pct'] = (comparison['otb'] / comparison['budget'] * 100).replace([np.inf, -np.inf], 0).fillna(0)

# --- 14. GRAFICO PLOTLY (Budget vs OTB) ---
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

# --- 15. TABELLA DETTAGLIO (CON DELTA ADR E OCC %) ---
st.subheader("📋 Dettaglio Mensile")

detail_table = comparison[['month_name', 'budget', 'otb', 'delta_rev', 'delta_adr', 'delta_occ', 'copertura_pct']].copy()
detail_table.columns = ['Mese', 'Target Budget (€)', 'OTB Reale (€)', 'Delta Rev (€)', 'Delta ADR', 'Delta Occ %', '% Copertura']

def color_delta(val):
    color = '#28a745' if val >= 0 else '#dc3545'
    return f'color: {color}; font-weight: bold;'

def color_copertura(val):
    if val >= 100:
        return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif val >= 90:
        return 'background-color: #fff3cd; color: #856404;'
    else:
        return 'background-color: #f8d7da; color: #721c24;'

dynamic_height = 38 + (12 * 35)

styled_table = detail_table.style\
    .format({
        'Target Budget (€)': '€ {:,.0f}',
        'OTB Reale (€)': '€ {:,.0f}',
        'Delta Rev (€)': '{:+,.0f} €',
        'Delta ADR': '{:+.2f} €',
        'Delta Occ %': '{:+.2f} pp',
        '% Copertura': '{:.1f}%'
    })\
    .map(color_delta, subset=['Delta Rev (€)'])\
    .map(color_delta, subset=['Delta ADR'])\
    .map(color_delta, subset=['Delta Occ %'])\
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
        'Delta Rev (€)': st.column_config.NumberColumn('Delta Rev', format='%+.0f €'),
        'Delta ADR': st.column_config.NumberColumn('Delta ADR', format='%+.2f €'),
        'Delta Occ %': st.column_config.NumberColumn('Delta Occ %', format='%+.2f pp'),
        '% Copertura': st.column_config.NumberColumn('% Copertura', format='%.1f%%')
    }
)

st.caption("🟢 **Verde**: Superato il budget | 🟡 **Giallo**: Raggiunto 90-99% | 🔴 **Rosso**: Sotto il 90%")

st.divider()

# --- 16. ANALISI AVANZATA ---
with st.expander("📊 Analisi Avanzata"):
    col_a1, col_a2 = st.columns(2)
    
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

st.caption("Budget Target v1.0 | Confronto automatico tra Budget Ufficiale e Forecast OTB")