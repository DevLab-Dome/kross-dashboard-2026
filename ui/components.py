import streamlit as st
import pandas as pd
from typing import Dict, Optional


def format_currency(value: float, decimals: int = 2) -> str:
    """
    Formatta un valore numerico come valuta in stile italiano (€ 1.234,56).
    
    Args:
        value: Valore numerico da formattare
        decimals: Numero di decimali (default: 2)
    
    Returns:
        Stringa formattata (es: "€ 1.234,56")
    """
    if pd.isna(value) or value is None:
        return "€ 0,00"
    
    # Formatta con separatore delle migliaia (.) e decimale (,)
    formatted = f"{value:,.{decimals}f}"
    
    # Sostituisci separatori: inglese → italiano
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    
    return f"€ {formatted}"


def format_pct(value: float, decimals: int = 2, include_sign: bool = False) -> str:
    """
    Formatta un valore numerico come percentuale in stile italiano (75,50%).
    
    Args:
        value: Valore numerico (es: 75.5 per 75.5%)
        decimals: Numero di decimali (default: 2)
        include_sign: Se True, include il segno + per valori positivi
    
    Returns:
        Stringa formattata (es: "75,50%" o "+5,20%")
    """
    if pd.isna(value) or value is None:
        return "0,00%"
    
    # Formatta con decimale italiano
    formatted = f"{value:.{decimals}f}".replace(".", ",")
    
    # Aggiungi segno + se richiesto e valore positivo
    if include_sign and value > 0:
        formatted = f"+{formatted}"
    
    return f"{formatted}%"


def format_number(value: float, decimals: int = 0) -> str:
    """
    Formatta un numero generico in stile italiano con separatore delle migliaia.
    
    Args:
        value: Valore numerico
        decimals: Numero di decimali (default: 0)
    
    Returns:
        Stringa formattata (es: "1.234")
    """
    if pd.isna(value) or value is None:
        return "0"
    
    formatted = f"{value:,.{decimals}f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    
    return formatted


def _format_delta_value(delta_abs: float, delta_pct: float, metric_type: str) -> str:
    """
    Formatta il valore delta per st.metric.
    
    Args:
        delta_abs: Delta assoluto
        delta_pct: Delta percentuale
        metric_type: Tipo di metrica ('currency', 'pct', 'number')
    
    Returns:
        Stringa formattata per il delta
    """
    if metric_type == 'currency':
        return f"{format_currency(abs(delta_abs))} ({format_pct(delta_pct, decimals=1, include_sign=True)})"
    elif metric_type == 'pct':
        # Per occupancy: mostra punti percentuali (pp)
        return f"{format_pct(abs(delta_abs), decimals=1)} pp"
    elif metric_type == 'number':
        return f"{format_number(abs(delta_abs))} ({format_pct(delta_pct, decimals=1, include_sign=True)})"
    else:
        return f"{delta_abs:.2f}"


def render_kpi_strip(kpi_data: Dict, title: Optional[str] = None):
    """
    Renderizza una striscia orizzontale di KPI usando st.metric.
    
    Args:
        kpi_data: Dizionario con struttura:
            {
                'current': {'revenue': ..., 'occupancy_pct': ..., 'rooms_sold': ..., 'adr': ..., 'revpar': ...},
                'previous': {...},
                'delta': {'revenue_abs': ..., 'revenue_pct': ..., 'occupancy_pct_abs': ..., ...}
            }
        title: Titolo opzionale da mostrare sopra la striscia
    """
    if title:
        st.subheader(title)
    
    # Estrai dati
    current = kpi_data.get('current', {})
    delta = kpi_data.get('delta', {})
    
    # Crea 5 colonne per i KPI principali
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # 1. Revenue
    with col1:
        revenue = current.get('revenue', 0)
        revenue_delta_abs = delta.get('revenue_abs', 0)
        revenue_delta_pct = delta.get('revenue_pct', 0)
        
        st.metric(
            label="💰 Revenue",
            value=format_currency(revenue),
            delta=_format_delta_value(revenue_delta_abs, revenue_delta_pct, 'currency'),
            delta_color="normal"
        )
    
    # 2. Occupancy %
    with col2:
        occupancy = current.get('occupancy_pct', 0)
        occupancy_delta_abs = delta.get('occupancy_pct_abs', 0)
        
        st.metric(
            label="📊 Occupancy",
            value=format_pct(occupancy),
            delta=_format_delta_value(occupancy_delta_abs, 0, 'pct'),
            delta_color="normal"
        )
    
    # 3. Rooms Sold (Notti)
    with col3:
        rooms_sold = current.get('rooms_sold', 0)
        rooms_delta_abs = delta.get('rooms_sold_abs', 0)
        rooms_delta_pct = delta.get('rooms_sold_pct', 0)
        
        st.metric(
            label="🛏️ Notti Vendute",
            value=format_number(rooms_sold),
            delta=_format_delta_value(rooms_delta_abs, rooms_delta_pct, 'number'),
            delta_color="normal"
        )
    
    # 4. ADR
    with col4:
        adr = current.get('adr', 0)
        adr_delta_abs = delta.get('adr_abs', 0)
        adr_delta_pct = delta.get('adr_pct', 0)
        
        st.metric(
            label="💵 ADR",
            value=format_currency(adr),
            delta=_format_delta_value(adr_delta_abs, adr_delta_pct, 'currency'),
            delta_color="normal"
        )
    
    # 5. RevPAR
    with col5:
        revpar = current.get('revpar', 0)
        revpar_delta_abs = delta.get('revpar_abs', 0)
        revpar_delta_pct = delta.get('revpar_pct', 0)
        
        st.metric(
            label="📈 RevPAR",
            value=format_currency(revpar),
            delta=_format_delta_value(revpar_delta_abs, revpar_delta_pct, 'currency'),
            delta_color="normal"
        )


def render_day_grid(daily_df: pd.DataFrame, height: int = 400):
    """
    Renderizza una griglia giornaliera usando st.dataframe con formattazione personalizzata.
    
    Args:
        daily_df: DataFrame con colonne: date, day, day_name, revenue, rooms_sold, adr, occupancy_pct, revpar
        height: Altezza del dataframe in pixel (default: 400)
    """
    if daily_df.empty:
        st.warning("⚠️ Nessun dato disponibile per il periodo selezionato.")
        return
    
    # Prepara il DataFrame per la visualizzazione
    display_df = daily_df.copy()
    
    # Formatta la colonna date come stringa leggibile
    if 'date' in display_df.columns:
        display_df['Data'] = display_df['date'].dt.strftime('%d/%m/%Y')
    
    # Rinomina colonne per la visualizzazione
    column_labels = {
        'day': 'Giorno',
        'day_name': 'GG',
        'revenue': 'Revenue',
        'rooms_sold': 'Notti',
        'adr': 'ADR',
        'occupancy_pct': 'Occ %',
        'revpar': 'RevPAR'
    }
    
    # Seleziona e rinomina colonne disponibili
    display_columns = []
    for orig_col, new_label in column_labels.items():
        if orig_col in display_df.columns:
            display_columns.append(orig_col)
    
    # Aggiungi 'Data' se è stata creata
    if 'Data' in display_df.columns:
        display_columns.insert(0, 'Data')
    
    # Crea il DataFrame di visualizzazione
    display_df = display_df[display_columns].copy()
    
    # Rinomina le colonne
    display_df = display_df.rename(columns=column_labels)
    display_df = display_df.rename(columns={'Data': 'Data'})
    
    # Configura le colonne con formattazione
    column_config = {}
    
    if 'Data' in display_df.columns:
        column_config['Data'] = st.column_config.TextColumn(
            'Data',
            width='medium',
            help='Data del giorno'
        )
    
    if 'Giorno' in display_df.columns:
        column_config['Giorno'] = st.column_config.NumberColumn(
            'Giorno',
            width='small',
            help='Giorno del mese'
        )
    
    if 'GG' in display_df.columns:
        column_config['GG'] = st.column_config.TextColumn(
            'GG',
            width='small',
            help='Giorno della settimana'
        )
    
    if 'Revenue' in display_df.columns:
        column_config['Revenue'] = st.column_config.NumberColumn(
            'Revenue',
            format='€ %.2f',
            width='medium',
            help='Revenue giornaliero'
        )
    
    if 'Notti' in display_df.columns:
        column_config['Notti'] = st.column_config.NumberColumn(
            'Notti',
            format='%d',
            width='small',
            help='Camere vendute'
        )
    
    if 'ADR' in display_df.columns:
        column_config['ADR'] = st.column_config.NumberColumn(
            'ADR',
            format='€ %.2f',
            width='medium',
            help='Average Daily Rate'
        )
    
    if 'Occ %' in display_df.columns:
        column_config['Occ %'] = st.column_config.NumberColumn(
            'Occ %',
            format='%.2f%%',
            width='small',
            help='Percentuale di occupazione'
        )
    
    if 'RevPAR' in display_df.columns:
        column_config['RevPAR'] = st.column_config.NumberColumn(
            'RevPAR',
            format='€ %.2f',
            width='medium',
            help='Revenue Per Available Room'
        )
    
    # Mostra il dataframe
    st.dataframe(
        display_df,
        column_config=column_config,
        use_container_width=True,
        height=height,
        hide_index=True
    )


def render_comparison_chart(comparison_df: pd.DataFrame, metric: str = 'revenue', 
                           title: Optional[str] = None):
    """
    Renderizza un grafico di confronto mese per mese tra anno corrente e precedente.
    
    Args:
        comparison_df: DataFrame con colonne month_name, current_year, previous_year
        metric: Nome della metrica da visualizzare
        title: Titolo del grafico
    """
    if comparison_df.empty:
        st.warning("⚠️ Nessun dato disponibile per il confronto.")
        return
    
    if title:
        st.subheader(title)
    
    # Prepara i dati per il grafico
    chart_data = comparison_df[['month_name', 'current_year', 'previous_year']].copy()
    chart_data = chart_data.rename(columns={
        'month_name': 'Mese',
        'current_year': 'Anno Corrente',
        'previous_year': 'Anno Precedente'
    })
    
    # Mostra il grafico a barre
    st.bar_chart(
        chart_data,
        x='Mese',
        y=['Anno Corrente', 'Anno Precedente'],
        use_container_width=True
    )


def render_info_box(title: str, content: str, icon: str = "ℹ️"):
    """
    Renderizza un box informativo stilizzato.
    
    Args:
        title: Titolo del box
        content: Contenuto testuale
        icon: Emoji icona (default: ℹ️)
    """
    st.info(f"{icon} **{title}**\n\n{content}")


def render_success_box(message: str, icon: str = "✅"):
    """
    Renderizza un box di successo.
    """
    st.success(f"{icon} {message}")


def render_warning_box(message: str, icon: str = "⚠️"):
    """
    Renderizza un box di warning.
    """
    st.warning(f"{icon} {message}")


def render_error_box(message: str, icon: str = "❌"):
    """
    Renderizza un box di errore.
    """
    st.error(f"{icon} {message}")


def render_metadata_info(metadata: Dict):
    """
    Renderizza informazioni sui metadati del caricamento dati.
    
    Args:
        metadata: Dict con informazioni su baseline_rows, num_forecasts, files_applied, etc.
    """
    with st.expander("📊 Informazioni sul Caricamento Dati"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Righe Baseline", format_number(metadata.get('baseline_rows', 0)))
        
        with col2:
            st.metric("Forecast Applicati", metadata.get('num_forecasts', 0))
        
        with col3:
            st.metric("Righe Totali", format_number(metadata.get('final_rows', 0)))
        
        if metadata.get('files_applied'):
            st.write("**File Forecast Applicati:**")
            for filename in metadata['files_applied']:
                st.text(f"  • {filename}")


def render_loading_spinner(message: str = "Caricamento in corso..."):
    """
    Mostra uno spinner di caricamento.
    
    Args:
        message: Messaggio da mostrare durante il caricamento
    
    Returns:
        Context manager per st.spinner
    """
    return st.spinner(message)