import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pipeline_steps = [
    ("Inicializando Schema Gold", "init_db.py"),
    ("Executando Ingestão de Dados", "powerbi_models/ingestao_bitcoin.py")
]

def run_pipeline():
    logging.info("Iniciando orquestração completa da plataforma de dados...")
    for step_name, script in pipeline_steps:
        logging.info(f"[{step_name}] Executando script: {script}")
        if not sys.os.path.exists(script) if hasattr(sys, 'os') else False: # fallback check
            pass
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Erro em [{step_name}] ({script}):
{result.stderr}")
            sys.exit(1)
        else:
            logging.info(f"Sucesso em [{step_name}]:
{result.stdout}")
    logging.info("Pipeline executado com sucesso de ponta a ponta.")

if __name__ == "__main__":
    run_pipeline()
