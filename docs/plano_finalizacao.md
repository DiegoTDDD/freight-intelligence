# Plano consolidado de finalização

Escopo aprovado pelo usuário: concluir as 12 etapas do roteiro original e incluir
rotas reais, análises brasileiras e experiência em português antes de finalizar.
A autorização inclui a validação completa dos dados locais; nenhum recurso pago
foi autorizado. O histórico original permanece em roteiro_original.md.

| Entrega | Critério | Estado nesta revisão |
| --- | --- | --- |
| Pipeline | Execução completa e teste dos dados reais | Concluído; log preservado e testes aprovados |
| Previsões | Histórico verificável, validação e teste reservados | Concluído com ANTT 2006–2025; limites descritos em brasil.md |
| Otimização | Oferta/demanda, capacidade e custos explícitos | Implementado e testado |
| API | Endpoints e permissões documentados | Implementado e testado |
| Docker | Imagens reproduzíveis e verificações reais | Concluído; imagem ampliada aprovada localmente e no GitHub |
| CD | Publicar somente depois de CI aprovado | Deploy hook autorizado e salvo; primeira prova automática pendente |
| Portfólio | Guia de uso, arquitetura, resultados e limitações | Documentado e versão be0280d publicada; conferência final em andamento |
| Brasil | Fonte oficial, unidades, filtros e downloads | Implementado com ANTT ferroviário |
| Rotas reais | Traçado geográfico, fonte e exportação | Implementado com OSRM/OSM, perfil de automóvel de referência |
| Português | Navegação, controles e explicações em português | Implementado, com seleção de inglês |

## Evidência local

Em 12/11/2026 o pipeline completo terminou com sucesso, incluindo Bronze, Silver
e todas as saídas Gold. A execução usou dois threads do Polars e escrita em staging
para Bronze/Silver. Os dados reais têm 2.503.352 linhas Bronze e 97.630.728 Silver.
Depois foi corrigida a dimensão modal Gold: `dms_mode` representa o trecho doméstico;
`fr_inmode` representa a entrada internacional e não deve ser usado em seu lugar.
As saídas Gold afetadas foram recalculadas e os resultados dependentes revalidados.

Suíte completa local: **320 testes aprovados**, incluindo os testes dos dados reais.
Ruff aprovado. O único aviso remanescente é uma descontinuação do TestClient upstream.
Não significa falha da aplicação.

A revisão `499a252` também passou nas quatro verificações remotas: Windows,
Ubuntu, API/contêineres e imagem do painel. Execução do envio:
https://github.com/DiegoTDDD/freight-intelligence/actions/runs/43301679357
O mapa e a área brasileira foram conferidos visualmente no navegador.

## Limite da conclusão

Concluir este escopo entrega uma demonstração de portfólio reproduzível, publicada
e com resultados auditáveis. Não certifica roteamento operacional de caminhões,
cobertura de todos os modais brasileiros, precisão futura ou hospedagem gratuita
eterna. Esses limites fazem parte dos resultados, não são funcionalidades fictícias.
