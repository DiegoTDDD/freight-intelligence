from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("Carga_Postgres").getOrCreate()

print("==================================================")
print("Lendo dados da Camada Bronze (Parquet)...")
df_ipca = spark.read.parquet("/home/jovyan/work/ipca_historico.parquet")
df_m2 = spark.read.parquet("/home/jovyan/work/base_monetaria_historico.parquet")

# Credenciais e URL do nosso banco de dados PostgreSQL que está rodando no Docker
jdbc_url = "jdbc:postgresql://postgres_gold_layer:5432/economics_gold"
properties = {
    "user": "admin",
    "password": "adminpassword",
    "driver": "org.postgresql.Driver"
}

print("Escrevendo tabela 'ipca' no PostgreSQL...")
df_ipca.write.jdbc(url=jdbc_url, table="ipca", mode="overwrite", properties=properties)

print("Escrevendo tabela 'base_monetaria' no PostgreSQL...")
df_m2.write.jdbc(url=jdbc_url, table="base_monetaria", mode="overwrite", properties=properties)

print("Carga finalizada! Dados prontos para modelagem relacional.")
print("==================================================")
