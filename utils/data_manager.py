import pandas as pd
import streamlit as st
import boto3
from io import BytesIO
from datetime import datetime

class ForecastManager:
    def __init__(self):
        # Caricamento credenziali dal tuo secrets.toml
        self.endpoint = st.secrets["endpoint"]
        self.key = st.secrets["access_key"]
        self.secret = st.secrets["secret_key"]
        self.bucket = st.secrets["bucket_name"]
        
        self.s3 = boto3.client('s3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.key,
            aws_secret_access_key=self.secret
        )

    def get_consolidated_data(self, struttura, anno):
        """Legge file Excel o CSV eliminando totali e normalizzando i nomi delle colonne"""
        folder_struct = struttura.replace(" ", "_")
        prefix = f"History_Baseline/{folder_struct}/{anno}/"
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            all_dfs = []
            
            if 'Contents' not in response:
                return pd.DataFrame(), f"Percorso non trovato: {prefix}"

            for obj in response.get('Contents', []):
                key = obj['Key']
                
                if key.lower().endswith(('.csv', '.xlsx')):
                    file_obj = self.s3.get_object(Bucket=self.bucket, Key=key)
                    body = file_obj['Body'].read()
                    
                    if key.lower().endswith('.csv'):
                        df = pd.read_csv(BytesIO(body))
                    else:
                        df = pd.read_excel(BytesIO(body))
                    
                    # 1. Normalizzazione nomi colonne
                    df.columns = [str(c).lower().strip() for c in df.columns]
                    
                    # 2. DIZIONARIO DI TRADUZIONE ESATTO (Basato sui tuoi file Kross)
                    mappa_nomi = {
                        'data': 'date',
                        'occupate %': 'occupancy_pct', # Nome esatto nel tuo file
                        'occupancy %': 'occupancy_pct',
                        'totale revenue': 'revenue',    # Nome esatto nel tuo file
                        'ricavo': 'revenue',
                        'adr': 'adr'
                    }
                    df.rename(columns=mappa_nomi, inplace=True)
                    
                    if 'date' in df.columns:
                        # 3. PULIZIA RIGHE SPORCHE
                        df['date'] = pd.to_datetime(df['date'], errors='coerce')
                        df = df.dropna(subset=['date'])
                        
                        # 4. GARANZIA COLONNE NUMERICHE
                        for col in ['adr', 'occupancy_pct', 'revenue']:
                            if col not in df.columns:
                                df[col] = 0.0
                            
                            if df[col].dtype == object:
                                df[col] = df[col].astype(str).str.replace('€', '', regex=False)\
                                               .str.replace(',', '.', regex=False)\
                                               .str.strip()
                            
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                        # Fix: Se l'occupazione è decimale (es. 0.85), portala a 85
                        if df['occupancy_pct'].max() <= 1.0 and df['occupancy_pct'].max() > 0:
                            df['occupancy_pct'] = df['occupancy_pct'] * 100
                        
                        all_dfs.append(df)
            
            if all_dfs:
                consolidated = pd.concat(all_dfs).drop_duplicates(subset=['date'])
                return consolidated, "Success"
            
            return pd.DataFrame(), "Nessun dato valido trovato."
            
        except Exception as e:
            return pd.DataFrame(), f"Errore S3: {str(e)}"

    def save_budget(self, df, struttura, anno, tipo='test'):
        """
        Salva il budget su DigitalOcean Spaces in formato CSV.
        
        Args:
            df: DataFrame con i dati del budget
            struttura: Nome della struttura (es: "Lavagnini", "La Terrazza")
            anno: Anno del budget (es: 2026)
            tipo: 'official' o 'test' (default: 'test')
        
        Returns:
            Tuple[bool, str]: (success, percorso_file_o_messaggio_errore)
        """
        try:
            # Normalizza nome struttura
            folder_struct = struttura.replace(" ", "_")
            
            # Determina il percorso in base al tipo
            if tipo == 'official':
                # Percorso: Budgets-Official/[Struttura]-[Anno]/budget_official.csv
                folder_path = f"Budgets-Official/{folder_struct}-{anno}"
                filename = f"{folder_path}/budget_official.csv"
            else:  # tipo == 'test'
                # Percorso: Budgets-Test/[Struttura]-[Anno]/budget_test_[timestamp].csv
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                folder_path = f"Budgets-Test/{folder_struct}-{anno}"
                filename = f"{folder_path}/budget_test_{timestamp}.csv"
            
            # Converti il DataFrame in CSV
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            # Carica su S3
            self.s3.put_object(
                Bucket=self.bucket,
                Key=filename,
                Body=csv_buffer.getvalue()
            )
            
            return True, filename
            
        except Exception as e:
            return False, str(e)