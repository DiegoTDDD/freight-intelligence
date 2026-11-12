# Estado atual — 12/11/2026

O escopo ativo inclui as 12 etapas do [roteiro recuperado](roteiro_original.md),
rotas reais, dados brasileiros e experiência em português, conforme autorização
posterior do usuário. A declaração anterior de que o roteiro já havia terminado
estava incorreta. Ver [plano de finalização](plano_finalizacao.md).

## Implementação validada

- Pipeline completo executado com sucesso: Bronze 2.503.352 linhas, Silver
  97.630.728 linhas, todas as saídas Gold. Correção adicional do modal doméstico:
  `dms_mode`, conforme dicionário oficial, em lugar de `fr_inmode`.
- Baselines FAF, validação temporal e três modelos comparados com histórico
  administrativo ANTT/SIADE de 2006–2025. Validação até 2022 e teste reservado
  2023–2025. WAPE do modelo escolhido: 4,75% TU e 1,61% TKU.
- Análises ferroviárias brasileiras anuais/mensais, mercadorias, estados e
  concessionárias, com fontes, unidades, hashes e downloads.
- Rota geográfica real via OSRM/OSM, mapa e GeoJSON, confirmação de envio de
  coordenadas e exemplo público São Paulo–Campinas. Perfil de automóvel de
  referência; não certifica restrições ou operação de caminhões.
- Painel abre em português, permite inglês e preserva esquemas dos arquivos.
- Otimização, API autenticada, imagens fixadas e backups reproduzíveis mantidos.

Suíte completa local: **320 testes aprovados**, incluindo dados reais. Ruff aprovado.
Imagem ampliada do painel passou no teste de 512 MiB, sem rede e somente leitura,
incluindo a área brasileira, exemplo de rota salvo e troca de idioma.
Aviso remanescente: descontinuação upstream do Starlette TestClient.

CI remoto da revisão `499a252`: quatro verificações aprovadas (Windows, Ubuntu,
API/contêineres e imagem do painel), execução 43301679357. As imagens de referência
do painel estão em docs/images; fontes e limitações permanecem documentadas.

## Publicação

Site: https://loginexus-dashboard-preview.onrender.com/
Branch: `codex/loginexus-preview-20261112`.
PR: https://github.com/DiegoTDDD/freight-intelligence/pull/1

A versão ampliada está sendo preparada para publicação. Configuração de CI inclui
push na branch vinculada; o Blueprint pede implantação somente após checks aprovados.
A ativação na hospedagem, a execução remota e a conferência pública ainda precisam
ser observadas antes de declarar o CD e a publicação final concluídos. Não houve
merge em main. Os registros históricos de development_handoff.md podem descrever
estados antigos; este documento prevalece para o estado consolidado.

## Limites

Dados brasileiros cobrem ferrovias federais concedidas e fluxos declarados, não
cargas únicas ou todos os modais. Modelos fornecem estimativas, sem garantia de
precisão futura. Hospedagem gratuita e serviços públicos externos têm limitações
sem garantia de permanência. Código, dados derivados e recuperação são portáveis.
Nenhum recurso pago foi contratado.
