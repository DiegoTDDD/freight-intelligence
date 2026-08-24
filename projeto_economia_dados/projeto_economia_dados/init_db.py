import os
from sqlalchemy import create_engine, text

def initialize_database():
    host = os.getenv('DB_HOST', 'localhost')
    conn_str = f'postgresql://admin:adminpassword@{host}:5432/economics_gold'
    engine = create_engine(conn_str)
    
    print('[*] Inicializando schema e tabelas analíticas na camada Gold...')
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS gold_economic_indicators (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                indicator_name VARCHAR(100) NOT NULL,
                value NUMERIC(18, 4) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS gold_bitcoin_metrics (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                close_price NUMERIC(18, 2) NOT NULL,
                volume NUMERIC(24, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))
    print('[+] Tabelas da Camada Gold inicializadas com sucesso.')

if __name__ == '__main__':
    initialize_database()
