# Estado atual — 2026-11-12

A demonstração pública está disponível em:
https://loginexus-dashboard-preview.onrender.com/

Código publicado: `d3f32a1a01c7fc7a1df26d74bb84f9e62a9cb0f2`, branch
`codex/loginexus-preview-20261112`. PR de revisão ainda em rascunho:
https://github.com/DiegoTDDD/freight-intelligence/pull/1
Não houve merge em main.

## Entregue

- Pipeline Windows com resumos compatíveis com cp1252, plano sem execução,
  reutilização por dependências e escrita temporária Bronze/Silver.
- Indicadores, extrapolações de cenário, avaliação temporal e rastreabilidade.
- Otimização de transporte e rotas sobre rede explicitamente fornecida.
- Dashboard com análises e simulações de sessão; API com permissões individuais.
- Imagens fixadas, verificações de contêiner e demonstração pública com snapshot
  de 18 arquivos (aproximadamente 8,6 MB), sem dados brutos/Silver ou credenciais.
- Cópia independente de código/dados e instruções de recuperação.

## Validação

A revisão publicada passou nos 276 testes leves locais e Ruff. O GitHub Actions
aprovou Windows, Ubuntu e contêiner na execução 43259989577:
https://github.com/DiegoTDDD/freight-intelligence/actions/runs/43259989577
O pipeline completo de aproximadamente 100 milhões de linhas não foi executado.

Após essa publicação, foi adicionada uma ferramenta reproduzível de
backup (`scripts/package_recovery.py`) e corrigido o guia de recuperação para
selecionar o snapshot explicitamente. Seus cinco testes passaram; Ruff passou.
O CI agora gera o ZIP verificado e o preserva como artefato por 30 dias. Essas
mudanças posteriores integram a revisão do PR; o site continua na versão d3f32a1.
Veja [recuperação](recovery.md).

O CI também constrói separadamente a imagem do painel hospedado e verifica suas
59 dependências, os 18 arquivos do snapshot e as três áreas analíticas. O teste
executa em contêiner sem rede, com aplicação somente leitura e limite de 512 MB.
Essa verificação passou na imagem local antes de ser enviada ao GitHub.

## Limites e próximos passos reais

A hospedagem gratuita pode suspender por inatividade e depende dos limites e
políticas do provedor; não há garantia de permanência. O backup permite reconstruir
em outro destino, mas depende de acesso às bibliotecas/imagens para instalação.

Rotas operacionais exigem rede viária verificada, restrições e custos reais.
Previsões mais fortes exigem observações históricas verificadas e cobertura temporal
adequada. O recorte FAF de cinco pontos inclui estimativas, não medições diretas.
Não inventar fontes, usuários, economias reais ou requisitos para preencher etapas.

Não executar o pipeline pesado nem contratar recursos pagos sem autorização.
O PR permanece em rascunho; não fazer merge sem autorização.
O histórico em development_handoff.md registra estados anteriores; este documento
prevalece para o estado atual.
