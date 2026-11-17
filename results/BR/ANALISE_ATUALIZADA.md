# Brasil: análise dos resultados atualizados

16/11/2026. Dez estados, escala municipal, clima do NASA POWER de 1981 a 2025.
Esta leitura substitui os resultados anteriores, obtidos quando o `ano` da
PAM era tratado como ano de plantio; a extensão brasileira do README traz o
mesmo conteúdo em inglês. Agora `ano` é o ano da colheita:
a produtividade de `t` é casada com a estação de setembro de `t−1` a abril de
`t`, com janela crítica em janeiro–fevereiro de `t`
(ver `docs/DADOS_FALTANTES.md`, seção 8).

Todos os números vêm dos arquivos em `results/BR/<UF>/` gerados pelos scripts
`br_07`, `br_11`, `br_13`, `br_14`, `br_16` e `br_17`, e de
`results/_literature_models/` (script 48). Produtividade em bu/acre, como no
restante do repositório.

## Resumo

1. **O clima explica a produtividade no Sul e em Mato Grosso do Sul, e pouco
   no Cerrado e no Matopiba.** Em RS, PR e MS o calor de janeiro–fevereiro
   reduz a produtividade de forma significativa; em SP o efeito é menor e
   limítrofe. Em MT, GO, MG, BA, TO e MA nenhum termo de temperatura é
   significativo no modelo de efeitos fixos.
2. **Esses quatro estados estão acima do ótimo térmico.** A Tmax de
   janeiro–fevereiro que maximiza a produtividade fica entre 26 e 28 °C; a
   média observada é de 29,5 a 31,5 °C.
3. **Só no RS o clima prevê bem fora da amostra** (22% melhor que prever
   anomalia zero). PR e MS ganham pouco; nos demais o modelo de clima não
   supera a linha de base.
4. **As projeções CMIP6 são negativas em todos os estados e cenários**, com os
   oito modelos concordando no sinal em oito dos dez estados. A perda é grande
   onde o sinal de clima é real (PR, MS, RS) e pequena onde ele é fraco.
5. **O solo explica o nível e a volatilidade entre municípios, mas não
   melhora a previsão ano a ano**, exceto em MS e, pouco, no PR.
6. **A seca pesa mais que a chuva total.** No painel conjunto, o déficit de
   pressão de vapor e o SPEI da janela crítica são os preditores mais fortes.

## 1. Painel

| Estado | Municípios no painel balanceado | Observações | R² só com efeito fixo de município | R² com efeito de ano |
| --- | --- | --- | --- | --- |
| RS | 406 | 15.165 | 0,39 | 0,65 |
| PR | 368 | 14.272 | 0,22 | 0,49 |
| MS | 74 | 2.921 | 0,19 | 0,47 |
| TO | 58 | 1.614 | 0,07 | 0,30 |
| SP | 302 | 10.550 | 0,05 | 0,13 |
| MG | 153 | 5.243 | 0,04 | 0,21 |
| BA | 10 | 355 | 0,03 | 0,77 |
| MA | 27 | 830 | 0,03 | 0,51 |
| MT | 102 | 3.374 | 0,02 | 0,32 |
| GO | 173 | 5.963 | 0,02 | 0,22 |

A coluna sem efeito de ano é a que mostra quanto o clima de
janeiro–fevereiro explica por si. O salto ao incluir o efeito de ano em BA e
MA vem de choques comuns a poucos municípios, não do clima: com 10 e 27
municípios esses dois painéis são pequenos demais para conclusões firmes.

## 2. Resposta ao calor e à chuva (`br_07`, modelo de efeitos fixos de município e ano)

| Estado | Efeito de +1 °C na Tmax de jan–fev, na média (bu/acre) | p (Tmax, Tmax²) | Ótimo térmico | Tmax média | Chuva significativa? |
| --- | --- | --- | --- | --- | --- |
| MS | −2,27 | 0,014 / 0,003 | 27,1 °C | 31,5 °C | não (p = 0,96) |
| PR | −1,45 | <0,001 / <0,001 | 27,5 °C | 29,5 °C | sim (p < 0,001) |
| RS | −0,57 | <0,001 / <0,001 | 26,4 °C | 29,7 °C | sim (p < 0,001) |
| SP | −0,38 | 0,073 / 0,027 | 27,9 °C | 29,5 °C | não (p = 0,49) |
| MA | −3,00 | 0,19 / 0,29 | não identificado | 30,4 °C | não |
| BA | −1,10 | 0,065 / 0,052 | não identificado | 29,3 °C | não |
| TO | −0,31 | 0,96 / 0,84 | não identificado | 30,0 °C | não |
| MG | −0,26 | 0,79 / 0,52 | não identificado | 27,9 °C | não |
| GO | +0,11 | 0,24 / 0,32 | não identificado | 28,5 °C | sim (p = 0,025) |
| MT | +0,10 | 0,44 / 0,47 | não identificado | 29,0 °C | não |

Leitura:

- **RS, PR, MS e SP têm curva côncava e estão do lado quente do ótimo.** O
  termo quadrático é negativo e significativo nos quatro.
- **No PR o calor pesa mais quando chove** (−2,0 bu/acre por °C em anos
  úmidos contra −0,9 em anos secos; interação com p < 0,001). Em RS e MS o
  efeito é parecido nos dois casos.
- **Em MA e BA a curva estimada é convexa** (termo quadrático positivo), então
  o "ótimo" calculado é um mínimo, não um ótimo. Não interprete.
- **MT e GO não mostram efeito de calor no modelo conjunto**, mas a regressão
  linear por faixa de latitude (seção 4) dá sinal negativo em MT.

## 3. Previsão fora da amostra (`br_11`, janela expansiva; `br_17`, mesorregião de fora)

Ganho sobre prever anomalia zero. Negativo significa pior que a linha de base.

| Estado | Só clima | Clima + processo + solo | Só solo | Só clima, mesorregião de fora |
| --- | --- | --- | --- | --- |
| RS | +22,6% | +22,2% | −1,9% | +20,8% |
| PR | +3,2% | +6,0% | −1,9% | +3,5% |
| MS | +2,8% | +11,9% | −2,2% | −3,2% |
| SP | −0,9% | 0,0% | −2,0% | +0,2% |
| GO | −4,3% | −4,3% | −3,5% | −5,0% |
| MG | −4,3% | −3,5% | −3,9% | −0,9% |
| MT | −6,0% | −7,0% | −5,2% | −39,3% |
| BA | −6,4% | −8,5% | −3,2% | −12,7% |
| MA | −18,5% | −15,4% | −7,5% | −19,8% |
| TO | −19,0% | −16,9% | −5,4% | −20,2% |

- **RS é o único estado onde o modelo de clima é claramente útil para
  prever**, e o ganho se mantém quando uma mesorregião inteira fica fora do
  treino.
- **Em MS as variáveis de processo e de solo quase quadruplicam o ganho**
  (de 2,8% para 11,9%). É o único estado onde isso acontece com folga.
- **Em MT o modelo piora muito ao transferir entre mesorregiões** (−39%): o
  que ele aprende numa região não vale na outra.
- **Em TO e MA o modelo é bem pior que a linha de base.** Com 58 e 27
  municípios e sinal fraco, ele ajusta ruído.

## 4. Resposta ao calor por latitude (`br_17`)

Coeficiente linear da Tmax de janeiro–fevereiro por terço de latitude
(sul / centro / norte do estado), em bu/acre por °C.

| Estado | Sul | Centro | Norte | Inclinações iguais? (p) |
| --- | --- | --- | --- | --- |
| MS | −3,36 | −1,80 | −0,28 | <0,001 |
| PR | −2,12 | −2,25 | −2,52 | 0,011 |
| RS | −0,85 | −2,57 | −1,94 | <0,001 |
| TO | −1,56 | −1,56 | −1,58 | 1,00 |
| SP | −1,54 | −1,16 | −1,17 | 0,018 |
| MA | −0,52 | −0,70 | −0,96 | 0,32 |
| MT | −0,52 | −0,71 | −0,83 | 0,046 |
| MG | −0,11 | −0,01 | −0,43 | 0,004 |
| GO | −0,07 | −0,05 | +0,29 | 0,009 |
| BA | +0,12 | −0,31 | +0,19 | <0,001 (10 municípios) |

- **O sinal é negativo em quase todo terço de quase todo estado.** As
  exceções (norte de GO, BA) são pequenas e, na BA, de 2 a 5 municípios.
- **MS tem o gradiente mais forte:** o sul perde 3,4 bu/acre por °C e o norte
  quase nada.
- **TO e MT têm resposta negativa e uniforme no modelo linear**, embora o
  modelo quadrático conjunto da seção 2 não a detecte. Onde as duas
  especificações discordam, a evidência de efeito de calor é fraca, não nula.

## 5. Projeções CMIP6 (`br_13`, mediana de 8 modelos, deltas mensais sobre jan–fev)

Variação da produtividade em relação à média histórica.

| Estado | SSP2-4.5, meio do século | SSP5-8.5, fim do século | ΔTmax jan–fev (SSP5-8.5, fim) | Chuva jan–fev | Fora da faixa observada | Modelos concordam no sinal? |
| --- | --- | --- | --- | --- | --- | --- |
| PR | −9,6% | −32,8% | +4,0 °C | −1,9% | 10,7% | sim |
| MS | −7,3% | −26,7% | +4,2 °C | −0,6% | 15,5% | sim |
| RS | −8,4% | −21,3% | +3,4 °C | +8,3% | 3,4% | sim |
| TO | −6,5% | −17,4% | +3,7 °C | +1,7% | 41,5% | sim |
| SP | −5,0% | −16,4% | +3,9 °C | −1,1% | 8,4% | sim |
| MA | −2,1% | −6,8% | +3,1 °C | +11,6% | 14,7% | sim |
| MT | −2,2% | −6,4% | +3,9 °C | −2,0% | 3,1% | sim |
| GO | −0,2% | −3,1% | +3,8 °C | +3,1% | 10,6% | sim |
| MG | −0,5% | −1,6% | +3,9 °C | +4,2% | 7,0% | não |
| BA | −0,7% | −1,3% | +3,7 °C | +0,6% | 11,3% | não |

- **Nenhum estado tem ganho projetado em nenhum cenário.** No PR, 364 dos 368
  municípios pioram no SSP5-8.5 de fim de século; no RS, os 406.
- **No RS a perda ocorre mesmo com mais chuva projetada (+8%)**: o aquecimento
  domina.
- **Confie mais nos números de PR, MS, RS e SP**, onde a curva de resposta é
  estatisticamente identificada. Em MT, GO, MG, BA, TO e MA a projeção
  extrapola coeficientes não significativos; os valores são pequenos porque o
  ajuste é quase plano, não porque o risco seja baixo.
- **Em TO, 41% dos anos projetados ficam fora da faixa de clima observada**;
  os −17% são sobretudo extrapolação.
- **Estes números usam deltas mensais.** Um delta mensal não reproduz a
  mudança na frequência de dias acima de 30 °C. Para projeção com graus-dia,
  o script 46 baixa as séries diárias do NEX-GDDP-CMIP6.
- Não há efeito de fertilização por CO₂, de adaptação nem de mudança de
  cultivar nestas projeções.

## 6. Cenários idealizados (`br_14`)

Perturbação uniforme do clima observado de janeiro–fevereiro, com o mesmo
modelo quadrático de efeito fixo de município que o `br_13` usa para o CMIP6.
Variação da produtividade média, em %.

| Estado | +1 °C | −10% de chuva | +1 °C e −10% | +2 °C | +2 °C e −20% | Municípios que pioram com +2 °C |
| --- | --- | --- | --- | --- | --- | --- |
| PR | −6,3 | +0,3 | −5,5 | −14,9 | −12,5 | 360 de 368 |
| RS | −5,3 | −2,9 | −7,9 | −12,0 | −17,7 | 406 de 406 |
| MS | −5,5 | −0,1 | −5,6 | −12,2 | −12,2 | 74 de 74 |
| TO | −4,7 | +0,9 | −3,2 | −9,5 | −5,3 | 58 de 58 |
| SP | −3,3 | +0,5 | −2,5 | −7,6 | −5,8 | 302 de 302 |
| MA | −1,9 | −0,3 | −2,2 | −4,2 | −5,0 | 27 de 27 |
| MT | −1,7 | +0,3 | −1,3 | −3,5 | −2,7 | 102 de 102 |
| MG | −0,4 | −0,7 | −1,1 | −0,9 | −2,5 | 153 de 153 |
| GO | −0,1 | −0,6 | −0,4 | −0,8 | −1,0 | 136 de 173 |
| BA | −0,3 | −0,6 | −0,6 | −0,2 | −0,5 | 6 de 10 |

- **Os cenários agora concordam com as projeções CMIP6** em sinal e ordem dos
  estados: PR, RS e MS perdem 12% a 15% com +2 °C.
- **Só no RS a falta de chuva agrava a perda de forma clara** (−12% com +2 °C,
  −18% com +2 °C e −20% de chuva). No PR, SP, TO e MT a perda é um pouco
  *menor* com menos chuva: o modelo estima que o calor pesa mais em anos
  úmidos. Isso reflete o termo de interação e não deve ser lido como benefício
  da seca.
- **Menos de 2% dos anos perturbados ficam fora da faixa observada**, exceto
  em TO (6,8% com +2 °C).
- Até 16/11/2026 estes cenários usavam um modelo de árvores sobre níveis
  absolutos de clima e davam ganho de produtividade com o aquecimento; aquele
  resultado está retirado (ver o docstring do `br_14`).

## 7. Solo (`br_11`)

| Estado | Municípios | R² do solo para o nível de produtividade (ajustado) | R² para a tendência | R² para a volatilidade |
| --- | --- | --- | --- | --- |
| PR | 363 | 0,33 (0,31) | 0,39 | 0,47 |
| RS | 400 | 0,30 (0,28) | 0,26 | 0,32 |
| MT | 102 | 0,31 (0,25) | 0,25 | 0,17 |
| SP | 286 | 0,11 (0,09) | 0,24 | 0,11 |
| GO | 169 | 0,09 (0,05) | 0,07 | 0,12 |
| MS | 74 | 0,14 (0,04) | 0,28 | 0,27 |
| MG | 153 | 0,08 (0,03) | 0,24 | 0,16 |
| TO | 58 | 0,14 (0,00) | 0,43 | 0,36 |
| MA | 27 | 0,33 (0,04) | 0,17 | 0,29 |
| BA | 10 | 0,99 (0,97) | 0,92 | 0,89 |

- **No PR, RS e MT o solo explica cerca de 30% da diferença de produtividade
  média entre municípios**, e no PR quase metade da diferença de
  volatilidade.
- **O solo sozinho não prevê a anomalia de um ano** (ganho negativo em todos
  os estados, tabela da seção 3). É o esperado: o solo é fixo no tempo.
- **BA é sobreajuste** (10 municípios, 9 parâmetros). MA e TO têm R² ajustado
  perto de zero.
- Estes modelos já usam o SoilGrids preenchido (script 43). A água disponível
  no solo (`soil_aws_0_100cm`) está no painel de modelagem, mas ainda não
  entra no `br_11`.

## 8. Irrigação (`br_16`, Censo Agropecuário 2017)

| Estado | Prevalência mediana de irrigação | Interação irrigação × chuva (p) |
| --- | --- | --- |
| SP | 69,6% | 0,79 |
| MG | 45,2% | 0,77 |
| BA | 19,1% | não estimada |
| GO | 15,0% | 0,20 |
| TO | 3,8% | 0,86 |
| RS | 2,5% | 0,13 |
| PR, MS, MA | 1,2% | 0,12 / 0,63 / <0,001 |
| MT | 0,8% | 0,83 |

A irrigação não altera a sensibilidade à chuva de forma detectável, exceto no
MA, onde quase todas as observações estão num único grupo e o contraste é
frágil. A medida é a área irrigada de todas as culturas em 2017 dividida pela
área média de soja, um indicador grosseiro; em SP e MG ela reflete cana, café
e hortaliças mais do que soja.

## 9. Modelos dos artigos, painel conjunto (script 48)

1.664 municípios com 20 anos ou mais, colheitas de 1982 a 2025, efeito fixo de
município e tendência quadrática por estado. Erros-padrão agrupados por
estado (10 grupos): o p é indicativo.

| Especificação | Brasil | EUA (911 condados) |
| --- | --- | --- |
| Schlenker & Roberts: 10 graus-dia acima de 30 °C | −1,6% (p = 0,04) | −5,7% (p < 0,001) |
| Lobell: +1 kPa de VPD na janela crítica | −37% (p < 0,001) | −34% (p < 0,001) |
| Silva: +1 °C na temperatura média da estação | −3,4% (p = 0,01) | sem efeito (p = 0,96) |
| Ortiz-Bobea: +0,1 de umidade do solo na janela crítica | +12% (p = 0,05) | +13% (p = 0,002) |
| Parisoto: +1 de SPEI-3 na janela crítica | +9,4% (p = 0,04) | +4,2% (p = 0,001) |
| R² dentro da unidade, melhor especificação | 0,22 (Lobell) | 0,26 (Lobell) |
| Random forest, anos fora do treino | R² 0,22 | R² 0,28 |
| Regressão de Schlenker-Roberts, anos fora do treino | R² 0,06 | R² 0,26 |

- **O efeito do VPD é quase idêntico nos dois países.** É o resultado mais
  robusto do conjunto.
- **Os −3,4% por °C no Brasil ficam abaixo dos −6% de Silva et al. (2023)**,
  mas com o mesmo sinal e ordem de grandeza.
- **Graus-dia acima de 30 °C pesam menos no Brasil que nos EUA.** Parte disso
  é a fonte: o NASA POWER tem células de ~50 km e suaviza os extremos; o
  Daymet dos EUA tem 1 km.
- **No Brasil o random forest supera a regressão por larga margem (0,22
  contra 0,06)**; nos EUA quase empata. A relação clima–produtividade
  brasileira é menos bem descrita por graus-dia e chuva total. As variáveis
  mais importantes para o random forest são SPEI-3, chuva e dias secos da
  janela crítica, e a umidade mínima do solo.
- **Ondas de calor (WSDI) não têm efeito próprio** em nenhum dos dois países
  depois de controlar o SPEI.

## 10. Limites desta análise

- **Um único ponto de clima por município**, o centroide, numa grade de
  ~50 km. Municípios grandes de MT, TO e MA são mal representados.
- **A janela crítica é fixa em janeiro–fevereiro para todos os estados.** No
  Matopiba e no norte de MT o plantio é mais tardio; uma janela por região,
  definida pelo ZARC, pode mudar o resultado desses estados.
- **1981 tem estação incompleta** (o NASA POWER começa em janeiro de 1981).
- **A comparação EUA × Brasil (scripts `36` e `37`) usa a janela 1980–2025**;
  ver `results/_eda_us_brazil/EDA_REPORT.md`.
- **A PAM é revista pelo IBGE**; os dados de produtividade são os baixados
  pelo `br_01` na data original, não foram atualizados agora.
