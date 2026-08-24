import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

codigo = """import pandas as pd
from sqlalchemy import create_engine
from powerbiclient import QuickVisualize, get_dataset_config
from powerbiclient.authentication import DeviceCodeLoginAuthentication

print("1. Autenticando na API da Microsoft...")
device_auth = DeviceCodeLoginAuthentication()

print("2. Extraindo dados da Camada Gold do PostgreSQL...")
engine = create_engine("postgresql://admin:adminpassword@localhost:5432/economics_gold")
df = pd.read_sql("SELECT * FROM vw_gold_macroeconomia ORDER BY data", engine)

print("3. Renderizando Painel Automatizado do Power BI...")
PBI_visualize = QuickVisualize(get_dataset_config(df), auth=device_auth)
PBI_visualize"""

nb['cells'] = [nbf.v4.new_code_cell(codigo)]

# Salva o notebook no repositório
caminho = os.path.abspath('../powerbi_models/Painel_Automatizado.ipynb')
with open(caminho, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print(f"Notebook gerado com sucesso em: {caminho}")
