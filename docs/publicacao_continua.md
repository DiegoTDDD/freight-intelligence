# Publicação contínua do painel

O serviço atual foi criado a partir da URL pública do repositório. Segundo a
[documentação do Render](https://render.com/docs/deploys), essa modalidade não
recebe a implantação automática nativa de um provedor Git conectado.

A integração usa o [deploy hook oficial](https://render.com/docs/deploy-hooks):

1. O proprietário autoriza guardar a URL privada como segredo do repositório
   `DiegoTDDD/freight-intelligence`, com o nome `RENDER_DEPLOY_HOOK_URL`.
2. O GitHub executa testes Windows/Linux, contêineres da API e a imagem do painel.
3. Somente em um envio à `main`, após
   os três jobs necessários passarem, a etapa de implantação envia um POST ao Render.
4. A consulta inclui o SHA completo já testado. Não publica outra revisão que tenha
   sido enviada enquanto os testes estavam em andamento.
5. O Render devolve o identificador da implantação; o processo acompanha a publicação
   e confere o site. Receber um identificador não equivale a provar que o serviço
   terminou de iniciar.

O código valida HTTPS, domínio e identificador do serviço específico. A URL privada
nunca é gravada em código, documentação ou logs. Falhas de transporte não incluem
a URL na mensagem e não provocam tentativas automáticas ambíguas. A etapa não é
executada em pull requests, incluindo forks, e tem permissão GitHub apenas de leitura.
As implantações são serializadas. A publicação nativa do Render fica desligada para
não disparar uma segunda implantação ou antecipar o resultado dos testes.
A branch de preparação deixou de publicar após a integração: alterações futuras
precisam chegar à main. Pull requests continuam executando as verificações.

## Escopo da autorização

O segredo permite iniciar atualizações deste serviço; não é necessário fornecer uma
chave administrativa completa da conta Render. Colaboradores com permissão para
alterar workflows podem usar os segredos do repositório, conforme as regras do GitHub.
O proprietário confirmou essa autorização persistente em 12/11/2026. O segredo
foi salvo no repositório. A execução 43316211342 confirmou o deploy automático da
revisão be9def7; o Render registrou a implantação como Live e com origem Deploy Hook.

## Recuperação

Se a publicação falhar, inspecione o CI e a lista de implantações antes de repetir:
um problema de rede pode ocorrer depois de o provedor já ter aceitado a solicitação.
Uma implantação manual da revisão verificada continua disponível no painel Render.
Não há execução automática do pipeline volumoso nem contratação de recursos pagos.
