import os
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine

def ingest_bitcoin_data():
    print("[*] Baixando dados históricos do Bitcoin (BTC-USD)...")
    
    # Baixa os dados do Bitcoin
    btc = yf.download("BTC-USD", start="2020-01-01", progress=False)
    
    if btc.empty:
        raise ValueError("Nenhum dado retornado pelo yfinance para BTC-USD.")

    # Reseta o índice para transformar 'Date' em coluna regular
    btc = btc.reset_index()

    # Trata colunas MultiIndex caso o yfinance retorne tuplas
    if isinstance(btc.columns, pd.MultiIndex):
        btc.columns = [col[0] if col[0] != '' else col[1] for col in btc.columns]

    # Renomeia e seleciona apenas as colunas essenciais
    # Dependendo da versão, a coluna pode vir como 'Close' ou 'Adj Close'
    close_col = 'Close' if 'Close' in btc.columns else btc.columns[1]
    
    df_clean = pd.DataFrame({
        'date': pd.to_datetime(btc['Date']).dt.date,
        'close_price': btc[close_col],
        'volume': btc['Volume'] if 'Volume' in btc.columns else 0
    })

    # Remove valores nulos
    df_clean = df_clean.dropna(subset=['close_price'])

    # Configura conexão com o banco Gold no Docker
    db_host = os.getenv("DB_HOST", "localhost")
    conn_str = f"postgresql://admin:adminpassword@{db_host}:5432/economics_gold"
    engine = create_engine(conn_str)

    print(f"[*] Inserindo {len(df_clean)} registros na tabela gold_bitcoin_metrics...")
    df_clean.to_sql('gold_bitcoin_metrics', engine, if_exists='replace', index=False)
    print("[+] Ingestão do Bitcoin concluída com sucesso.")

if __name__ == "__main__":
    ingest_bitcoin_data()
