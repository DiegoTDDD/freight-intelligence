# Rotas em vias reais

Na área **Rotas no mapa**, informe latitude/longitude da origem e do destino e
confirme o envio das coordenadas. O botão consulta o OSRM, sobre a rede real do
OpenStreetMap, e exibe o traçado, distância, tempo estimado e download GeoJSON.

O exemplo São Paulo–Campinas foi consultado em 12/11/2026: aproximadamente 93,17 km,
75,7 minutos estimados e 1.225 pontos no traçado. O exemplo pode ser carregado sem
uma nova consulta de roteamento. É uma resposta histórica salva; não confirma as
condições da via no momento da viagem.

## Perfil e limites

O serviço público oferece um **perfil de automóvel de referência**. Não certifica
rota para caminhão: altura, peso, eixos, carga perigosa, permissões locais e pedágios
não são validados. O tempo não usa trânsito ao vivo. Para cenários de veículos com
restrições explícitas, a área de rede fornecida permanece separada; nela a qualidade
das restrições depende dos dados informados.

Não há endereço inferido, rastreamento do usuário ou geolocalização automática.
As coordenadas iniciais são pontos públicos de São Paulo e Campinas. O envio só
ocorre após submissão com a confirmação marcada. As coordenadas podem ser registradas
pelo fornecedor externo. O mapa de fundo também carrega imagens de outro fornecedor.

## Serviço, atribuição e recuperação

- [Documentação OSRM](https://project-osrm.org/docs/v5.24.0/api/).
- [Política do servidor de demonstração](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server).
- [FOSSGIS: uso e privacidade](https://routing.openstreetmap.de/about.html).
- Dados © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL.

O servidor é de demonstração, para uso leve e não comercial, sem garantia de
disponibilidade. O cliente usa HTTPS, identificação da aplicação, espera mínima
de dois segundos entre chamadas por processo e cache limitado de 24 horas.
Não há consultas periódicas. Falhas não geram rotas sintéticas de substituição.

O cliente limita a resposta a 2 MiB e 50 mil pontos, rejeita coordenadas inválidas,
ajustes a vias acima de 1 km e respostas sem rota. Redirecionamentos são recusados.
O GeoJSON exportado contém perfil, origem, destino, pontos ajustados, fonte, data,
versão de dados quando fornecida e hash da resposta. Atribuição e link para corrigir
o mapa aparecem na interface. Uso comercial ou maior volume exige infraestrutura
e condições de serviço adequadas; não há contratação automática neste projeto.
