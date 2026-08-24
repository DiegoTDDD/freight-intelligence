import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

scripts_pipeline = [
    "powerbi_models/ingestao_bitcoin.py",
    # Adicione outros scripts de carga aqui conforme a evolução do pipeline
]

def run_pipeline():
    logging.info("Iniciando orquestração da plataforma de dados...")
    for script in scripts_pipeline:
        logging.info(f"Executando pipeline: {script}")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Erro ao executar {script}:\n{result.stderr}")
            sys.exit(1)
        else:
            logging.info(f"Sucesso na execução de {script}:\n{result.stdout}")
    logging.info("Pipeline executado com sucesso de ponta a ponta.")

if __name__ == "__main__":
    run_pipeline()
