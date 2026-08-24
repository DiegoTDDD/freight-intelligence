import requests
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date

spark = SparkSession.builder.appName("Ingestao_Base_Monetaria").master("local[*]").getOrCreate()
print("==================================================")
print("Spark: Conectando ao Banco Central (Série 1788 - Base Monetária)...")

url_m2 = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1788/dados?formato=json"
response = requests.get(url_m2)
pdf = pd.DataFrame(response.json())

df_raw = spark.createDataFrame(pdf)
df_silver = df_raw.withColumn("data", to_date(col("data"), "dd/MM/yyyy")) \
                  .withColumn("valor", col("valor").cast("double")) \
                  .withColumnRenamed("valor", "base_monetaria_milhoes")

print("Pipeline Executado. Amostra da Impressão de Moeda (Milhões R$):")
df_silver.orderBy(col("data").desc()).show(10)

df_silver.write.mode("overwrite").parquet("/home/jovyan/work/base_monetaria_historico.parquet")
print("Arquivo salvo com sucesso na Camada Bronze!")
print("==================================================")
