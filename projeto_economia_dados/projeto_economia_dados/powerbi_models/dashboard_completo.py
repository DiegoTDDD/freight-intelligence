import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Macroeconomia & Escassez", layout="wide", initial_sidebar_state="collapsed")

# Conexão e extração de ambas as tabelas da Camada Gold
@st.cache_data
def carregar_dados():
    engine = create_engine("postgresql://admin:adminpassword@db_gold:5432/economics_gold")
    df_macro = pd.read_sql("SELECT * FROM vw_gold_macroeconomia ORDER BY data", engine)
    df_btc = pd.read_sql("SELECT * FROM vw_gold_bitcoin ORDER BY data", engine)
    
    df_macro['data'] = pd.to_datetime(df_macro['data'])
    df_btc['data'] = pd.to_datetime(df_btc['data'])
    
    # Tratamento para garantir que não haja listas ou tipos bizarros vindo do YFinance
    if isinstance(df_btc['preco_usd'].iloc[0], (list, tuple, pd.Series)):
        df_btc['preco_usd'] = df_btc['preco_usd'].apply(lambda x: x[0] if isinstance(x, (list, tuple, pd.Series)) else x)
    df_btc['preco_usd'] = pd.to_numeric(df_btc['preco_usd'], errors='coerce')
    
    return df_macro, df_btc

df_macro, df_btc = carregar_dados()

st.markdown("<h1 style='text-align: center; color: #f8f9fa;'>Painel Analítico: Moeda Fiduciária vs Dinheiro Duro (Bitcoin)</h1>", unsafe_allow_html=True)
st.markdown("---")

# KPIs Dinâmicos
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Base Monetária (M2 Atual)", value=f"R$ {df_macro['base_monetaria_milhoes'].iloc[-1]:,.0f} Mi")
with col2:
    st.metric(label="IPCA Mensal Atual", value=f"{df_macro['ipca_mensal'].iloc[-1]:.2f}%")
with col3:
    preco_atual = float(df_btc['preco_usd'].dropna().iloc[-1])
    st.metric(label="Preço Atual do Bitcoin (USD)", value=f"$ {preco_atual:,.2f}")
with col4:
    st.metric(label="Pico de Expansão (M2 YoY)", value=f"{df_macro['expansao_m2_yoy_pct'].max():.2f}%")

st.markdown("---")

# Layout de dois gráficos lado a lado
col_grafico1, col_grafico2 = st.columns(2)

with col_grafico1:
    st.markdown("### 📉 A Falência Fiduciária (M2 vs IPCA)")
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df_macro['data'], y=df_macro['expansao_m2_yoy_pct'], name='M2 YoY (%)', line=dict(color='#ff4b4b', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_macro['data'], y=df_macro['ipca_mensal'], name='IPCA (%)', line=dict(color='#00d4ff', width=2)), secondary_y=True)
    fig1.update_layout(template='plotly_dark', hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig1, use_container_width=True)

with col_grafico2:
    st.markdown("### 🚀 A Fuga para a Escassez Absoluta (BTC)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_btc['data'], y=df_btc['preco_usd'], name='Preço BTC (USD)', line=dict(color='#f7931a', width=3)))
    # Eixo Y em escala logarítmica para mostrar a adoção exponencial
    fig2.update_layout(template='plotly_dark', hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0), yaxis_type="log")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("### 🧠 A Prova Empírica (Escola Austríaca)")
st.info("""
A injeção desenfreada de liquidez (M2 - Gráfico à esquerda) causa, invariavelmente, a perda do poder de compra refletida na inflação (IPCA). 
Em contrapartida, um ativo sem Banco Central e com limite fixo e inalterável de emissão (21 milhões de unidades), como o Bitcoin (Gráfico à direita), 
atua como uma esponja de liquidez. A adoção parabólica do Bitcoin documenta matematicamente a fuga de capital do sistema fiduciário falido.
""")
