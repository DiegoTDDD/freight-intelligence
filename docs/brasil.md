# Frete ferroviário brasileiro e previsão histórica

A área **Frete no Brasil** apresenta dados reais declarados no SIADE/ANTT para as
ferrovias federais concedidas, de 2006 a 2025. Não representa o transporte rodoviário,
o conjunto de todos os modais nem uma contagem de remessas únicas. Uma mesma carga
pode aparecer em fluxos sucessivos ou em mais de uma concessionária.

## Fonte e preparação

- [Catálogo oficial SIADE/ANTT](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409).
- [Dicionário oficial](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409/resource/5eb3b609-29c8-4108-a5ac-0d55950a0064/download/producao_origem_destino_dicionario_dados.pdf).
- Fonte: Agência Nacional de Transportes Terrestres. Licença declarada no catálogo:
  Creative Commons Atribuição. Acesso: 12/11/2026.

Foram aceitos 20 arquivos anuais com os 12 meses presentes. O arquivo de 2026 foi
excluído por representar um ano em andamento. A presença dos meses não comprova
que todas as declarações de cada concessionária sejam completas ou definitivas.

O parser reconhece o separador `;`, textos UTF-8/Windows-1252 e números brasileiros:
`1.234,5` corresponde a 1234,5. Valores negativos, formatos ambíguos, meses inválidos
e ano incompatível são rejeitados. Arquivos brutos permanecem fora do Git.

**TU** significa toneladas úteis; **TKU**, toneladas-quilômetro úteis. Essas unidades
não são intercambiáveis com milhares de toneladas/milhões de toneladas-milha do FAF.
Os agregados separados preservam ano, mês, mercadoria, ferrovia e estados dos fluxos.
`deployment/brazil_data/provenance.json` registra URLs, hashes, tamanhos e quantidades
de registros das fontes e dos arquivos derivados.

Para preparar outra cópia sem substituir a existente:

```text
python scripts/prepare_brazil_rail.py --output NOVA_PASTA --raw NOVA_PASTA_BRUTA
```

## Avaliação dos modelos

Comparação entre persistência, tendência linear e crescimento composto. O treinamento
começa com 2006–2013 e a validação expande o histórico até o último alvo de 2022.
A seleção usa somente o MAE de validação. **2023–2025** são previstos a partir de uma
única origem e ficam reservados para o teste final; seus erros não mudam a seleção.

| Indicador | Modelo escolhido na validação | WAPE no teste 2023–2025 |
| --- | --- | --- |
| TU | Crescimento composto | 4,75% |
| TKU | Crescimento composto | 1,61% |

No teste de TU, a tendência linear apresentou erro menor, de aproximadamente 1,96%.
Ela não foi promovida com base nesse resultado: fazê-lo reutilizaria o teste para
escolher o modelo. O painel disponibiliza os escores de todos os modelos, MAE, RMSE,
WAPE e as previsões para auditoria.

Após calcular o teste, o modelo já escolhido é reajustado com todo o histórico para
gerar estimativas pontuais de 2026–2028. Essas estimativas não são observações, não
têm intervalo de previsão e não garantem precisão futura. Mudanças de cobertura,
revisões administrativas e quebras estruturais limitam a interpretação.

O ZIP baixável contém a série anual exata, o manifesto de origem, a configuração
de avaliação, previsões, escores e estimativas futuras. A interface lê resultados
salvos e verifica seus hashes; abrir a página não baixa novamente os arquivos brutos.
