# Funcionalidades para discutir depois

**Arquivo histórico.** As três frentes abaixo foram implementadas e ampliadas.
Consultar [estado atual e pendências](status.md); trechos antigos sobre PR em
rascunho, pipeline não executado ou CD pendente não descrevem a entrega atual.

As três ideias foram inicialmente separadas a pedido do usuário. Depois ele aprovou
explicitamente sua implementação junto com as pendências do roteiro original.
Agora fazem parte de [plano de finalização](plano_finalizacao.md); este arquivo
preserva as três frentes e não representa mais uma lista de ideias sem aprovação.

## 1. Rotas com dados geográficos reais

Evoluir o cálculo atual sobre uma rede fornecida para uma integração geográfica
com fonte verificável. Definir região, origem dos mapas, atualização dos dados,
restrições dos veículos e custos antes da implementação. O cálculo existente
não equivale a uma rota operacional validada.

## 2. Análises de frete do Brasil

Definir indicadores e fontes brasileiras verificáveis, cobertura, unidades e
condições de uso. O conjunto FAF atual representa os Estados Unidos; não deve
ser apresentado como base brasileira.

## 3. Experiência do painel em português

Discutir tradução de navegação, filtros, mensagens, unidades e explicações dos
resultados. Definir se haverá somente português ou seleção de idioma e quais
fluxos precisam de simplificação.

## Correção: roteiro anterior recuperado

O plano completo de 12 etapas foi localizado no chat Projeto LogiNexus (5), após
a primeira busca ter ficado restrita ao chat (19). Está preservado em
[roteiro original](roteiro_original.md), com comparação ao estado atual.

As correções do erro Windows foram concluídas. Durante a continuação também foram entregues
análises, simulações, API, painel de demonstração online, verificações de imagens
e cópias de recuperação. Isso não encerra o roteiro: permanecem pendências de
validação integral, previsão com observações verificadas, CD e finalização do portfólio.

O PR segue em rascunho, sem merge em main. O site público usa a revisão d3f32a1;
melhorias posteriores de recuperação e CI estão na branch do PR. O pipeline
completo não foi reexecutado. Funcionalidades operacionais reais e requisitos
de produção ainda precisam de definição. Consultar current_status.md para os
limites e a distinção entre demonstração e uso operacional.
