import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

print("1. Baixando dados históricos do Bitcoin...")
btc = yf.download('BTC-USD', start='2014-01-01', end='2026-08-01', interval='1mo', progress=False)
btc = btc.reset_index()
btc = btc[['Date', 'Close']]
btc.columns = ['data', 'preco_usd']

print("2. Conectando ao PostgreSQL (Camada Gold)...")
engine = create_engine("postgresql://admin:adminpassword@localhost:5432/economics_gold")

print("3. Injetando dados de escassez...")
btc.to_sql('vw_gold_bitcoin', engine, if_exists='replace', index=False)

print("Sucesso! Tabela 'vw_gold_bitcoin' criada e populada no banco de dados.")
