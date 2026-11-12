# Recuperar o LogiNexus

O ZIP contém uma revisão do código, os pequenos agregados públicos FAF e ANTT,
a avaliação histórica brasileira e o exemplo de rota geográfica incluídos nela.
Não inclui ambientes Python, imagem Docker completa, senhas, uploads de sessão,
dados brutos nem o Silver de aproximadamente 100 milhões de linhas.
A revisão exata está em `REVISION.txt`; os manifestos dos conjuntos registram seus hashes.

## Abrir a cópia com os dados incluídos

Extraia o ZIP e abra um terminal na pasta `LogiNexus`. Com Python 3.13 e as dependências
do projeto instaladas, no PowerShell:

```powershell
$env:LOGINEXUS_DASHBOARD_DATA_ROOT = (Resolve-Path deployment/preview_data).Path
python -m streamlit run dashboards/app.py --server.address 127.0.0.1 --server.port 8502
```

Abra http://127.0.0.1:8502/. A variável acima é necessária: o inicializador normal usa
os dados locais do projeto e não seleciona automaticamente o snapshot de demonstração.
Se essa porta estiver ocupada, escolha outra; não encerre processos desconhecidos.
Não é necessário executar o pipeline completo.

## Recuperação com Docker

Com Docker instalado, dentro da pasta `LogiNexus`:

```text
docker build -f deployment/Dockerfile.dashboard -t loginexus-dashboard:restore .
docker run --rm -p 127.0.0.1:8502:8501 loginexus-dashboard:restore
```

Abra http://127.0.0.1:8502/. Essa imagem seleciona automaticamente o snapshot incluído.
A reconstrução precisa de acesso aos registros de imagens e pacotes; este backup
de código e dados não é uma instalação inteiramente offline.

## Gerar outra cópia

Na raiz de um repositório Git com esta ferramenta já commitada:

```text
python scripts/package_recovery.py --output CAMINHO_DA_PASTA
```

Somente arquivos da revisão commitada são incluídos. Alterações locais não commitadas
ficam de fora. O comando verifica os hashes do snapshot e a integridade ZIP antes de
publicar a cópia, gera um arquivo SHA-256 e recusa sobrescrever cópias existentes.

## Hospedagem e limites

`deployment/render.dashboard.yaml` descreve a hospedagem de demonstração.
A versão atual está em https://loginexus-dashboard-preview.onrender.com/.
Outro provedor pode reconstruir a imagem; custos e publicação precisam ser revistos.
Nenhum plano gratuito ou fornecedor tem permanência garantida.

O snapshot inclui projeções FAF, não observações futuras. Simulações usam custos
fornecidos e os uploads/resultados de sessão não constituem armazenamento permanente.
