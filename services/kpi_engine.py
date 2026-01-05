import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _calculate_metrics(df: pd.DataFrame, total_rooms: Optional[int] = None) -> Dict:
    """
    Calcola le metriche aggregate da un DataFrame filtrato.
    
    Args:
        df: DataFrame filtrato per il periodo desiderato
        total_rooms: Numero totale di camere disponibili (opzionale)
    
    Returns:
        Dict con le metriche calcolate
    """
    if df.empty:
        return {
            'revenue': 0.0,
            'rooms_sold': 0,
            'adr': 0.0,
            'occupancy_pct': 0.0,
            'revpar': 0.0,
            'days_count': 0
        }
    
    total_revenue = df['revenue'].sum()
    total_rooms_sold = df['rooms_sold'].sum()
    days_count = len(df)
    
    # ADR = Revenue Totale / Camere Vendute Totali (più accurato della media delle medie)
    adr = total_revenue / total_rooms_sold if total_rooms_sold > 0 else 0.0
    
    # Calcola occupancy % e revpar
    if 'rooms' in df.columns and df['rooms'].notna().any():
        # Usa il numero di camere disponibili dal DataFrame
        total_rooms_available = df['rooms'].sum()
        occupancy_pct = (total_rooms_sold / total_rooms_available * 100) if total_rooms_available > 0 else 0.0
        revpar = total_revenue / total_rooms_available if total_rooms_available > 0 else 0.0
    elif total_rooms is not None:
        # Usa il numero di camere fornito esternamente
        total_rooms_available = total_rooms * days_count
        occupancy_pct = (total_rooms_sold / total_rooms_available * 100) if total_rooms_available > 0 else 0.0
        revpar = total_revenue / total_rooms_available if total_rooms_available > 0 else 0.0
    else:
        # Fallback: usa la media delle occupancy % giornaliere
        occupancy_pct = df['occupancy_pct'].mean() * 100 if not df['occupancy_pct'].isna().all() else 0.0
        # RevPAR = ADR * Occupancy %
        revpar = adr * (occupancy_pct / 100) if occupancy_pct > 0 else 0.0
    
    return {
        'revenue': round(total_revenue, 2),
        'rooms_sold': int(total_rooms_sold),
        'adr': round(adr, 2),
        'occupancy_pct': round(occupancy_pct, 2),
        'revpar': round(revpar, 2),
        'days_count': days_count
    }


def _calculate_delta(current: Dict, previous: Dict) -> Dict:
    """
    Calcola le differenze (delta) tra anno corrente e anno precedente.
    
    Returns:
        Dict con delta assoluti e percentuali
    """
    delta = {}
    
    for key in ['revenue', 'rooms_sold', 'adr', 'occupancy_pct', 'revpar']:
        current_value = current.get(key, 0)
        previous_value = previous.get(key, 0)
        
        # Delta assoluto
        delta[f'{key}_abs'] = round(current_value - previous_value, 2)
        
        # Delta percentuale
        if previous_value != 0:
            delta[f'{key}_pct'] = round(((current_value - previous_value) / previous_value) * 100, 2)
        else:
            delta[f'{key}_pct'] = 0.0 if current_value == 0 else 100.0
    
    return delta


def get_yearly_kpi(df: pd.DataFrame, year: int, total_rooms: Optional[int] = None) -> Dict:
    """
    Calcola i KPI annuali per l'anno richiesto e confronta con l'anno precedente.
    
    Args:
        df: DataFrame completo con tutti i dati
        year: Anno da analizzare (es: 2024)
        total_rooms: Numero totale di camere (opzionale, se non presente nel DF)
    
    Returns:
        Dict strutturato con 'current', 'previous' e 'delta'
    """
    logger.info(f"Calcolo KPI annuali per {year}")
    
    # Estrai anno dalla colonna date
    df = df.copy()
    df['year'] = df['date'].dt.year
    
    # Filtra anno corrente e anno precedente
    df_current = df[df['year'] == year].copy()
    df_previous = df[df['year'] == (year - 1)].copy()
    
    # Calcola metriche
    current_metrics = _calculate_metrics(df_current, total_rooms)
    previous_metrics = _calculate_metrics(df_previous, total_rooms)
    
    # Calcola delta
    delta = _calculate_delta(current_metrics, previous_metrics)
    
    result = {
        'year': year,
        'current': current_metrics,
        'previous': previous_metrics,
        'delta': delta
    }
    
    logger.info(f"✓ KPI annuali calcolati: {current_metrics['days_count']} giorni nell'anno corrente")
    
    return result


def get_monthly_kpi(df: pd.DataFrame, year: int, month: int, total_rooms: Optional[int] = None) -> Dict:
    """
    Calcola i KPI mensili per il mese richiesto e confronta con lo stesso mese dell'anno precedente.
    
    Args:
        df: DataFrame completo con tutti i dati
        year: Anno da analizzare (es: 2024)
        month: Mese da analizzare (1-12)
        total_rooms: Numero totale di camere (opzionale)
    
    Returns:
        Dict strutturato con 'current', 'previous' e 'delta'
    """
    logger.info(f"Calcolo KPI mensili per {year}-{month:02d}")
    
    # Estrai anno e mese dalla colonna date
    df = df.copy()
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # Filtra mese corrente e stesso mese anno precedente
    df_current = df[(df['year'] == year) & (df['month'] == month)].copy()
    df_previous = df[(df['year'] == (year - 1)) & (df['month'] == month)].copy()
    
    # Calcola metriche
    current_metrics = _calculate_metrics(df_current, total_rooms)
    previous_metrics = _calculate_metrics(df_previous, total_rooms)
    
    # Calcola delta
    delta = _calculate_delta(current_metrics, previous_metrics)
    
    # Aggiungi informazioni sul periodo
    month_name = pd.Timestamp(year=year, month=month, day=1).strftime('%B')
    
    result = {
        'year': year,
        'month': month,
        'month_name': month_name,
        'current': current_metrics,
        'previous': previous_metrics,
        'delta': delta
    }
    
    logger.info(f"✓ KPI mensili calcolati: {current_metrics['days_count']} giorni in {month_name} {year}")
    
    return result


def get_daily_breakdown(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """
    Restituisce il breakdown giornaliero per un mese specifico,
    pronto per essere mostrato nella UI (Striscia Giorni).
    
    Args:
        df: DataFrame completo con tutti i dati
        year: Anno da filtrare
        month: Mese da filtrare (1-12)
    
    Returns:
        DataFrame filtrato e formattato con colonne:
        - date: Data originale (datetime)
        - day: Giorno del mese (int)
        - day_name: Nome del giorno della settimana (es: "Lun", "Mar")
        - revenue: Revenue giornaliero
        - rooms_sold: Camere vendute
        - adr: ADR giornaliero
        - occupancy_pct: Occupancy % giornaliero
        - revpar: RevPAR giornaliero
    """
    logger.info(f"Creazione breakdown giornaliero per {year}-{month:02d}")
    
    # Filtra per anno e mese
    df_filtered = df.copy()
    df_filtered = df_filtered[
        (df_filtered['date'].dt.year == year) & 
        (df_filtered['date'].dt.month == month)
    ].copy()
    
    if df_filtered.empty:
        logger.warning(f"✗ Nessun dato disponibile per {year}-{month:02d}")
        return pd.DataFrame()
    
    # Ordina per data
    df_filtered = df_filtered.sort_values('date').reset_index(drop=True)
    
    # Aggiungi colonne di formattazione
    df_filtered['day'] = df_filtered['date'].dt.day
    df_filtered['day_name'] = df_filtered['date'].dt.strftime('%a')  # Mon, Tue, Wed...
    
    # Conversione nomi giorni in italiano (opzionale)
    day_translation = {
        'Mon': 'Lun',
        'Tue': 'Mar',
        'Wed': 'Mer',
        'Thu': 'Gio',
        'Fri': 'Ven',
        'Sat': 'Sab',
        'Sun': 'Dom'
    }
    df_filtered['day_name'] = df_filtered['day_name'].map(day_translation)
    
    # Converti occupancy_pct da decimale (0.85) a percentuale (85.0) se necessario
    if df_filtered['occupancy_pct'].max() <= 1:
        df_filtered['occupancy_pct'] = df_filtered['occupancy_pct'] * 100
    
    # Arrotonda i valori per la visualizzazione
    df_filtered['revenue'] = df_filtered['revenue'].round(2)
    df_filtered['adr'] = df_filtered['adr'].round(2)
    df_filtered['occupancy_pct'] = df_filtered['occupancy_pct'].round(2)
    df_filtered['revpar'] = df_filtered['revpar'].round(2)
    
    # Seleziona e riordina le colonne
    output_columns = [
        'date', 'day', 'day_name', 
        'revenue', 'rooms_sold', 'adr', 'occupancy_pct', 'revpar'
    ]
    
    # Aggiungi colonne opzionali se presenti
    if 'rooms' in df_filtered.columns:
        output_columns.append('rooms')
    if 'blocked' in df_filtered.columns:
        output_columns.append('blocked')
    
    df_result = df_filtered[output_columns].copy()
    
    logger.info(f"✓ Breakdown giornaliero creato: {len(df_result)} giorni")
    
    return df_result


def get_comparison_table(df: pd.DataFrame, year: int, metric: str = 'revenue') -> pd.DataFrame:
    """
    Crea una tabella di confronto mese per mese tra anno corrente e anno precedente.
    
    Args:
        df: DataFrame completo
        year: Anno da analizzare
        metric: Metrica da confrontare ('revenue', 'rooms_sold', 'adr', 'occupancy_pct', 'revpar')
    
    Returns:
        DataFrame con colonne: month, month_name, current_year, previous_year, delta_abs, delta_pct
    """
    logger.info(f"Creazione tabella comparativa per metrica '{metric}'")
    
    df = df.copy()
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    results = []
    
    for month in range(1, 13):
        monthly_current = get_monthly_kpi(df, year, month)
        
        results.append({
            'month': month,
            'month_name': monthly_current['month_name'],
            'current_year': monthly_current['current'].get(metric, 0),
            'previous_year': monthly_current['previous'].get(metric, 0),
            'delta_abs': monthly_current['delta'].get(f'{metric}_abs', 0),
            'delta_pct': monthly_current['delta'].get(f'{metric}_pct', 0)
        })
    
    comparison_df = pd.DataFrame(results)
    
    logger.info(f"✓ Tabella comparativa creata per {year}")
    
    return comparison_df


def get_ytd_kpi(df: pd.DataFrame, year: int, end_date: Optional[pd.Timestamp] = None, 
                total_rooms: Optional[int] = None) -> Dict:
    """
    Calcola i KPI Year-To-Date (dall'inizio dell'anno fino a una data specifica).
    
    Args:
        df: DataFrame completo
        year: Anno da analizzare
        end_date: Data finale (default: oggi o ultima data disponibile)
        total_rooms: Numero totale di camere (opzionale)
    
    Returns:
        Dict con KPI YTD corrente vs YTD anno precedente
    """
    logger.info(f"Calcolo KPI YTD per {year}")
    
    df = df.copy()
    
    # Determina la data finale
    if end_date is None:
        end_date = df[df['date'].dt.year == year]['date'].max()
    
    # Crea la stessa data nell'anno precedente
    end_date_previous = end_date.replace(year=year - 1)
    
    # Filtra YTD per anno corrente e precedente
    df_current_ytd = df[
        (df['date'].dt.year == year) & 
        (df['date'] <= end_date)
    ].copy()
    
    df_previous_ytd = df[
        (df['date'].dt.year == (year - 1)) & 
        (df['date'] <= end_date_previous)
    ].copy()
    
    # Calcola metriche
    current_metrics = _calculate_metrics(df_current_ytd, total_rooms)
    previous_metrics = _calculate_metrics(df_previous_ytd, total_rooms)
    
    # Calcola delta
    delta = _calculate_delta(current_metrics, previous_metrics)
    
    result = {
        'year': year,
        'ytd_end_date': end_date.strftime('%Y-%m-%d'),
        'current': current_metrics,
        'previous': previous_metrics,
        'delta': delta
    }
    
    logger.info(f"✓ KPI YTD calcolati fino al {end_date.strftime('%Y-%m-%d')}")
    
    return result


def get_weekday_performance(df: pd.DataFrame, year: int, month: Optional[int] = None) -> pd.DataFrame:
    """
    Analizza la performance per giorno della settimana.
    
    Args:
        df: DataFrame completo
        year: Anno da analizzare
        month: Mese specifico (opzionale, se None analizza tutto l'anno)
    
    Returns:
        DataFrame con metriche aggregate per giorno della settimana
    """
    logger.info(f"Analisi performance per giorno della settimana - {year}")
    
    df = df.copy()
    df_filtered = df[df['date'].dt.year == year].copy()
    
    if month is not None:
        df_filtered = df_filtered[df_filtered['date'].dt.month == month].copy()
    
    if df_filtered.empty:
        return pd.DataFrame()
    
    # Aggiungi giorno della settimana
    df_filtered['weekday'] = df_filtered['date'].dt.day_name()
    df_filtered['weekday_num'] = df_filtered['date'].dt.dayofweek
    
    # Raggruppa per giorno della settimana
    weekday_stats = df_filtered.groupby(['weekday_num', 'weekday']).agg({
        'revenue': 'sum',
        'rooms_sold': 'sum',
        'adr': 'mean',
        'occupancy_pct': 'mean',
        'revpar': 'mean'
    }).reset_index()
    
    # Ordina per numero del giorno (0=Lunedì, 6=Domenica)
    weekday_stats = weekday_stats.sort_values('weekday_num').reset_index(drop=True)
    
    # Arrotonda
    weekday_stats['revenue'] = weekday_stats['revenue'].round(2)
    weekday_stats['adr'] = weekday_stats['adr'].round(2)
    weekday_stats['occupancy_pct'] = weekday_stats['occupancy_pct'].round(2)
    weekday_stats['revpar'] = weekday_stats['revpar'].round(2)
    
    logger.info(f"✓ Analisi weekday completata")
    
    return weekday_stats[['weekday', 'revenue', 'rooms_sold', 'adr', 'occupancy_pct', 'revpar']]