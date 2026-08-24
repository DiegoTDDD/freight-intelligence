import os
import subprocess
import sys
from sqlalchemy import create_engine

def check_infrastructure():
    print('=== PLATFORM HEALTH MONITOR ===')
    
    # 1. Verifica status dos containers Docker
    print('[*] Verificando containers Docker ativos...')
    result = subprocess.run(['docker', 'ps', '--format', '{{.Names}} - {{.Status}}'], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout if result.stdout else 'Nenhum container ativo encontrado.')
    else:
        print('[!] Erro ao consultar o Docker.')

    # 2. Testa conectividade com o PostgreSQL Gold
    host = os.getenv('DB_HOST', 'localhost')
    conn_str = f'postgresql://admin:adminpassword@{host}:5432/economics_gold'
    print(f'[*] Testando conexão com o PostgreSQL em {host}...')
    try:
        engine = create_engine(conn_str)
        with engine.connect() as conn:
            print('[+] Banco de dados PostgreSQL Gold RESPONDENDO com sucesso.')
    except Exception as e:
        print(f'[-] Falha na conexão com o banco de dados: {e}')

if __name__ == '__main__':
    check_infrastructure()
