# Especificação do pedido de histórico RNAL — Lisboa

**Versão de 2026-10-04. Anexo a pedidos em preparação; não constitui uma resposta do fornecedor nem dados observados.**

Projeto: [Lisbon Spatial Dynamics](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics). Pretende-se comparar a evolução da habitação com a pressão do alojamento local nas freguesias de Lisboa. Os indicadores são descritivos, com população dos Censos 2021 como denominador fixo.

## Âmbito e datas

| Elemento | Pedido |
| --- | --- |
| Território | Município de Lisboa, código `1106`, 24 freguesias |
| Período | 2019 T4 a 2025 T4, inclusive |
| Referência preferida | Situação administrativa no final do último dia de cada trimestre, com indicação da convenção horária e de inclusão/exclusão dos eventos desse dia |
| Dimensão | 25 datas × 24 freguesias = 600 observações solicitadas |
| Geografia de comparação | Identificadores e limites CAOP2025; se o histórico usar outra versão, preservar a geografia original e documentar a correspondência |
| Formato | CSV UTF-8, XLSX ou formato aberto já disponível, acompanhado de dicionário e metadados |

A [grelha CSV](rnal-history-scope.csv) enumera as datas e os códigos/nomes das freguesias. Usa `quarter` no formato `YYYYQn`, `reference_date` no formato `AAAA-MM-DD`, `municipality_code`, `freguesia_id` e `freguesia_name`. São chaves solicitadas, sem valores de stock ou capacidade. O ficheiro foi construído a partir da [referência de freguesias preservada no projeto](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/33336c0091e3978d7f2fc358ae4555195015f6b5/results/source-audit/2026-10-01/census_context.csv).

As datas são 31 de dezembro de 2019 e, em cada ano de 2020 a 2025, 31 de março, 30 de junho, 30 de setembro e 31 de dezembro. A data de extração do ficheiro deve ser indicada separadamente da data a que os valores se referem.

Se apenas existirem ficheiros mensais ou anuais, solicita-se a identificação dos períodos efetivamente disponíveis. Uma observação de novembro não será tratada como 31 de dezembro, nem a data de registo de um estabelecimento será tratada como data de observação do arquivo.

## Agregados preferidos

Os nomes seguintes são sugestões para facilitar a leitura, não uma exigência de alteração do formato existente. Solicita-se o significado e a unidade dos campos equivalentes. Cada linha deve identificar a data de referência, o código e o nome da freguesia e a versão geográfica.

| Campo proposto | Conteúdo e unidade |
| --- | --- |
| `registered_stock` | Número inteiro de registos RNAL distintos incluídos no stock administrativo nessa data, sem ponderação por capacidade; identificar os estados incluídos e excluídos |
| `users_capacity_known` | Soma dos valores conhecidos de `NrUtentes`, ou campo equivalente, dos registos incluídos; lugares de capacidade registada, não hóspedes observados |
| `users_capacity_missing_records` | Número de registos incluídos sem capacidade de utentes conhecida |
| `users_capacity_zero_records` | Número de registos incluídos com capacidade de utentes explicitamente igual a zero |
| `beds_capacity_known` | Se disponível, soma da capacidade de camas dos mesmos registos, em camas, separada de `NrUtentes` |
| `beds_capacity_missing_records` | Se disponível, número de registos incluídos sem capacidade de camas conhecida |
| `registrations_in_quarter` | Se disponível, novas inscrições durante o trimestre, com definição da data usada e da unidade: eventos ou registos distintos |
| `cessations_in_quarter` | Se disponível, cessações durante o trimestre, com definição da data de efeito e da unidade |
| `cancellations_in_quarter` / `reinstatements_in_quarter` | Se disponíveis, cancelamentos e reposições de estado, separados ou com indicação explícita da sobreposição com outras categorias |
| `coverage_status` | Indicação de observação completa, parcial, indisponível ou suprimida, acompanhada de motivo quando conhecido |

Solicita-se que valores desconhecidos ou suprimidos permaneçam identificados como tal. Zero deve significar zero observado; uma soma de capacidade conhecida deve indicar quantos registos não têm capacidade disponível. Se não existir qualquer valor conhecido, indicar essa situação explicitamente. Solicita-se também a identificação de eventuais registos sem freguesia atribuída, fora da correspondência geográfica ou excluídos por outras razões, para reconciliar o total municipal com a soma das freguesias sem forçar a sua distribuição.

As capacidades devem corresponder à data de referência. Se apenas existir a capacidade atual, solicita-se a indicação dessa limitação. O stock administrativo não será interpretado como número de negócios em funcionamento, ocupação turística ou anúncios em plataformas. Os totais ponderados por capacidade, quando disponíveis, devem ser fornecidos separadamente, com fórmula e regra de arredondamento.

Os fluxos de 2019 T4 referem-se a 1 de outubro–31 de dezembro de 2019; não equivalem a fluxos anuais de 2019. Diferenças de stock entre trimestres não substituem fluxos observados nem identificam, por si só, cessações.

## Alternativa: arquivo de estados ou alterações

Se os agregados não estiverem disponíveis, solicita-se informação sobre um extrato mínimo que permita reconstruí-los: identificador estável do registo, datas e estados administrativos, freguesia e respetiva versão, capacidade e respetivas datas de validade, data de referência do extrato e data de revisão. São necessários os registos relevantes para o período, incluindo os cessados ou cancelados que já não constem das consultas atuais.

Um histórico de eventos deverá incluir uma situação inicial suficiente para identificar os registos existentes antes de 1 de outubro de 2019 e as alterações até 31 de dezembro de 2025. Solicita-se a distinção entre data de efeito e data de entrada/correção no sistema, bem como a regra para eventos no mesmo dia, cancelamentos, reposições e mudanças de freguesia ou capacidade. Uma data única de cessação pode não representar vários períodos de atividade administrativa.

Não são necessários nomes de titulares ou estabelecimentos, NIF, contactos, moradas completas ou coordenadas individuais. Caso a harmonização geográfica dependa de localização, solicita-se preferencialmente a correspondência ou agregação efetuada pelo serviço responsável.

## Definições e reconciliação

Solicita-se esclarecimento sobre:

1. Estados que integram o stock, conservação de registos cessados/cancelados, reposições e eventuais alterações de âmbito ao longo do período.
2. Distinção entre data de registo, abertura ao público, início de atividade, cessação e cancelamento; convenções de data/fuso horário e tratamento de correções retroativas. Indicar se o histórico reproduz o que era conhecido em cada data ou uma versão posteriormente revista.
3. Método de atribuição de freguesia e versão dos limites, incluindo alterações de localização e correspondência com CAOP2025.
4. Disponibilidade do histórico de capacidade, significado de valores nulos e zeros e regras de contagem ou arredondamento.
5. Possibilidade de fornecer, como validação adicional fora da grelha trimestral, o stock não ponderado no final de novembro de 2022 e a sua decomposição por freguesia, para reconciliação com os 20 134 registos publicados pela CML. Indicar separadamente o âmbito e a data exata dos quadros de capacidade e AL ponderado de novembro de 2019 e novembro de 2022.
6. Significado e política de correção de datas de registo muito antigas: as consultas oficiais de 1 de outubro de 2026 apresentam sete registos anteriores a 2000. A presença destas datas não foi tratada automaticamente como erro.

## Elementos de apoio já preservados

| Evidência | Referência e limite de interpretação |
| --- | --- |
| Relatório municipal de dezembro de 2022 | [Cópia Arquivo.pt do PDF oficial](https://arquivo.pt/noFrame/replay/20260216185851id_/https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf), captura de 2026-02-16. Páginas impressas 2/87: intercâmbio mensal; página 38 (página 50 do PDF): 20 134 registos no final de novembro de 2022. |
| Comparação das interfaces oficiais | [Auditoria de 2026-10-01](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/33336c0091e3978d7f2fc358ae4555195015f6b5/docs/rnal-coverage.md): 11 865 registos SOAP, nenhuma cessação preenchida, 172 divergências de freguesia entre registos comuns. As capturas SOAP/GIS não são simultâneas. A reconstrução dos sobreviventes para novembro de 2022 contém 11 525 registos; a diferença de 8 609 face ao relatório não identifica encerramentos. |
| Quadros municipais por freguesia | [Transcrição verificada](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/33336c0091e3978d7f2fc358ae4555195015f6b5/docs/cml-historical-benchmarks.md): quadros 18/19, páginas impressas 93/95 (105/107 do PDF), AL ponderado e capacidade de utentes. Estes indicadores e a sua precisão mensal não substituem stock não ponderado no final do trimestre. |
| Arquivo comunitário RNAL | [Avaliação de 13 capturas](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/33336c0091e3978d7f2fc358ae4555195015f6b5/docs/rnal-archive-coverage.md), de maio de 2025 a outubro de 2026. A cobertura incompleta e os reaparecimentos de registos impedem a sua utilização como série histórica definitiva; não se atribui uma causa às ausências. |

## Proveniência e acesso

Para cada conjunto disponibilizado, solicita-se identificação da entidade e sistema de origem, cobertura temporal, data de extração, versão, filtros aplicados, dicionário, limitações conhecidas e política de revisão. Um endereço público estável para os dados e a documentação poderá substituir o envio de anexos.

Solicita-se a indicação das condições de acesso e citação e do que é permitido conservar ou redistribuir: ficheiros recebidos, extratos minimizados e agregados por freguesia. Interessa poder arquivar uma versão fixa com identificação e hash e permitir a reprodução do estudo por terceiros. A licença do software do projeto não é tomada como licença dos dados. Se a disponibilização pública dos ficheiros não for possível, agradece-se a indicação de uma via de acesso reproduzível e das restrições aplicáveis.

[Voltar aos pedidos preparados e critérios de avaliação](../rnal-history-request.md)
