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
| PR | +3,2% | +5,5% | −1,9% | +3,5% |
| MS | +2,8% | +11,6% | −2,2% | −3,2% |
| SP | −0,9% | −0,1% | −2,0% | +0,2% |
| GO | −4,3% | −4,2% | −3,5% | −5,0% |
| MG | −4,3% | −3,2% | −3,9% | −0,9% |
| MT | −6,0% | −6,8% | −5,2% | −39,3% |
| BA | −6,4% | −8,2% | −3,2% | −12,7% |
| MA | −18,5% | −13,8% | −7,5% | −19,8% |
| TO | −19,0% | −17,2% | −5,4% | −20,2% |

- **RS é o único estado onde o modelo de clima é claramente útil para
  prever**, e o ganho se mantém quando uma mesorregião inteira fica fora do
  treino.
- **Em MS as variáveis de processo e de solo quase quadruplicam o ganho**
  (de 2,8% para 11,6%). É o único estado onde isso acontece com folga.
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
- **Parte importante dos cenários é extrapolação.** Com +2 °C, a Tmax de
  janeiro–fevereiro passa do máximo que o próprio município já viveu em 9% a
  19% dos anos no Sul e no Centro-Oeste (SP 9%, MS 12%, RS 13%, MG e MT 15%,
  PR 19%, GO 23%) e em 27% a 48% no Matopiba (BA 27%, MA 33%, TO 48%). Com
  −20% de chuva, 5% a 16% dos anos ficam abaixo da menor chuva já registrada
  no município. Comparar com o máximo do estado inteiro, como na versão
  anterior, subestimava isso (menos de 2%).
- **A curva de temperatura é côncava (com um ótimo) em nove estados e convexa
  na BA**, onde o ajuste não é significativo; ali o aquecimento extrapolado
  apareceria como ganho. Os valores da BA não devem ser interpretados.
- Até 16/11/2026 estes cenários usavam um modelo de árvores sobre níveis
  absolutos de clima e davam ganho de produtividade com o aquecimento; aquele
  resultado está retirado (ver o docstring do `br_14`).

## 7. Solo (`br_11`)

Nove termos de solo: argila, areia, matéria orgânica, pH, densidade e CTC da
camada superficial, matéria orgânica da subsuperfície, Latossolo (sim/não) e
água disponível no primeiro metro (`soil_aws_0_100cm`, script 43).

| Estado | Municípios | R² do solo para o nível de produtividade (ajustado) | R² para a tendência | R² para a volatilidade |
| --- | --- | --- | --- | --- |
| RS | 400 | 0,35 (0,34) | 0,26 | 0,32 |
| PR | 363 | 0,33 (0,31) | 0,39 | 0,49 |
| MT | 102 | 0,31 (0,24) | 0,25 | 0,18 |
| SP | 286 | 0,12 (0,09) | 0,25 | 0,13 |
| MS | 74 | 0,14 (0,02) | 0,30 | 0,27 |
| GO | 169 | 0,09 (0,04) | 0,10 | 0,16 |
| MG | 153 | 0,09 (0,03) | 0,24 | 0,16 |
| TO | 58 | 0,14 (−0,02) | 0,45 | 0,36 |
| MA | 27 | 0,36 (0,02) | 0,19 | 0,38 |
| BA | 10 | saturado | — | — |

- **A água disponível só pesa no RS.** Lá ela é o termo de solo mais forte
  para a produtividade média (+0,68 bu/acre por cm de água no primeiro metro,
  p < 0,001) e eleva o R² do nível de 0,30 para 0,35. Nos outros nove estados
  o coeficiente não é significativo (p de 0,12 em SP a 0,90 em MS). É coerente
  com o RS ser o estado onde a seca mais explica a produtividade, e onde a
  água disponível é mais baixa (mediana de 7 cm, contra 9 a 15 cm nos demais).
- **No PR, RS e MT o solo explica cerca de um terço da diferença de
  produtividade média entre municípios**, e no PR quase metade da diferença
  de volatilidade.
- **O solo não melhora a previsão ano a ano em nenhum estado**: o ganho de
  incluir o solo no modelo de clima e processo fica entre −2,4 e +1,1 ponto
  percentual. É o esperado para uma variável fixa no tempo.
- **BA (10 municípios, 10 parâmetros) está saturada; MA e TO têm R² ajustado
  perto de zero.** Não interprete esses três.

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

## 9b. Efeitos mês a mês e clima semanal (script 51)

**Mourtzinis et al. (2015): efeito de cada mês da estação.** Mesmo painel e
mesmos efeitos fixos da seção 9; meses de outubro a fevereiro no Brasil e de
maio a setembro nos EUA. Variação da produtividade, em %:

| Mês (Brasil) | +1 °C | +100 mm | Mês (EUA) | +1 °C | +100 mm |
| --- | --- | --- | --- | --- | --- |
| Out | +1,9 (p < 0,001) | −1,6 (0,28) | Mai | +0,2 (0,19) | +0,2 (0,86) |
| Nov | −1,7 (0,25) | +1,4 (0,21) | Jun | +1,3 (0,001) | +1,8 (0,02) |
| Dez | +1,4 (0,69) | +5,3 (0,08) | Jul | −0,5 (0,41) | +5,6 (0,002) |
| Jan | **−3,0 (0,02)** | +3,5 (0,15) | Ago | **−3,1 (< 0,001)** | **+9,1 (< 0,001)** |
| Fev | **−3,7 (0,002)** | +6,7 (0,09) | Set | +0,5 (0,17) | +0,6 (0,42) |

- **O calor prejudica só no enchimento de grãos nos dois países**: janeiro e
  fevereiro no Brasil, agosto nos EUA, com perdas parecidas (−3% a −4% por
  °C). Calor no início da estação (outubro no Brasil, junho nos EUA) chega a
  ajudar.
- **A chuva importa mais no fim da estação.** Nos EUA o efeito cresce de junho
  a agosto; no Brasil os coeficientes de dezembro a fevereiro são positivos e
  grandes, mas imprecisos com 10 grupos de erro-padrão.
- Isso confirma a escolha de janeiro–fevereiro e julho–agosto como janelas
  críticas.

**Khaki et al. (2020): o clima semana a semana prevê melhor?** O modelo
original é uma rede CNN-RNN; aqui, com as mesmas entradas semanais (26
semanas de Tmax, Tmin, chuva e VPD), comparei uma rede neural densa e um
random forest com a regressão de Schlenker-Roberts. R² em anos fora do treino:

| Modelo | Brasil | EUA |
| --- | --- | --- |
| Regressão de Schlenker-Roberts (4 termos) | 0,06 | 0,24 |
| Random forest, clima semanal (104 entradas) | 0,15 | 0,16 |
| Rede neural, clima semanal (104 entradas) | 0,01 | −0,04 |
| Random forest, índices sazonais (26 entradas, seção 9) | 0,22 | 0,28 |

- **O detalhe semanal não ajuda.** Nos dois países o random forest com índices
  sazonais bem escolhidos (SPEI, dias secos, umidade do solo) supera o mesmo
  modelo com 104 médias semanais, e a rede neural simples não aprende nada
  útil. O ganho do trabalho de Khaki vem da arquitetura recorrente, do solo
  por camada e do progresso de plantio, que não estão nesta comparação.

## 9c. Quando a soja é semeada: Conab × ZARC (scripts 52 e 49)

A Conab publica toda semana a fração da área de soja semeada e colhida em
cada estado. A série coletada vai de abril de 2020 a novembro de 2026 e cobre
5 a 6 safras completas por estado (colheitas de 2022 a 2027). Mediana entre
safras do dia em que metade da área estava semeada e colhida, comparada com a
data de menor risco do ZARC:

| Estado | Conab: 50% semeado | Variação entre safras (dias após 1º set) | ZARC: menor risco | Conab − ZARC (dias) | Conab: 50% colhido | Ciclo (dias) |
| --- | --- | --- | --- | --- | --- | --- |
| MT | 18 out | 43–55 | 81 | −35 | 12 fev | 117 |
| SP | 21 out | 49–56 | 76 | −26 | 7 mar | 137 |
| MS | 23 out | 50–54 | 75 | −23 | 27 fev | 127 |
| PR | 26 out | 52–59 | 71 | −17 | 9 mar | 134 |
| GO | 5 nov | 54–70 | 85 | −20 | 1 mar | 116 |
| MG | 11 nov | 62–80 | 79 | −8 | 9 mar | 118 |
| TO | 12 nov | 62–76 | 91 | −20 | 4 mar | 112 |
| BA | 17 nov | 67–84 | 64 | +13 | 19 mar | 122 |
| RS | 23 nov | 79–90 | 83 | 0 | 21 abr | 149 |
| MA | 1 dez | 80–108 | 148 | −57 | 19 mar | 108 |

- **Na maior parte do país o agricultor semeia 2 a 5 semanas antes da data de
  menor risco do ZARC.** Só no RS as duas coincidem, e na BA o plantio é mais
  tardio. O ZARC indica a janela de menor risco climático, não a data
  praticada, e não deve ser usado como data de semeadura.
- **Com semeadura em outubro (MT, SP, MS, PR), o enchimento de grãos cai em
  dezembro–janeiro**; no RS e no Matopiba, em janeiro–fevereiro. O RS tem o
  ciclo mais longo (149 dias até 50% colhido).

**Janela crítica móvel (script 49).** Em cada estado, a janela de
janeiro–fevereiro foi substituída pelos dias 60 a 105 após a semeadura (uma
suposição para R3–R6), usando a data do ZARC por município ou a data
observada da Conab por estado. Mesmo modelo quadrático, mesmas linhas; R²
dentro do município:

| Estado | Janeiro–fevereiro | Janela pela data do ZARC | Janela pela data da Conab |
| --- | --- | --- | --- |
| RS | **0,402** | 0,347 | 0,362 |
| PR | **0,213** | 0,208 | 0,211 |
| MS | 0,172 | **0,186** | 0,143 |
| MG | 0,046 | 0,033 | **0,050** |
| SP | **0,045** | 0,038 | 0,043 |
| MT | 0,017 | 0,023 | **0,034** |
| TO | 0,034 | **0,045** | 0,028 |
| GO | 0,020 | 0,016 | **0,023** |
| BA | 0,025 | **0,115** | 0,045 |
| MA | 0,017 | **0,063** | 0,045 |
| Todos | **0,187** | 0,170 | 0,172 |

- **Janeiro–fevereiro continua sendo a melhor janela no conjunto e nos dois
  estados com sinal climático forte (RS e PR).** Posicionar a janela pela
  semeadura, observada ou recomendada, não melhora o ajuste ali.
- **Onde o sinal é fraco, qualquer janela posicionada pela semeadura ajuda um
  pouco** (MT, Matopiba), mas o R² continua abaixo de 0,12.
- Interpretação: o dano por calor e seca no enchimento de grãos se concentra
  em janeiro–fevereiro em quase todo o país mesmo com semeaduras diferentes,
  e a janela de 46 dias após uma data estadual única é estreita demais para a
  dispersão de semeadura dentro de cada estado.

## 9d. O NDVI melhora a previsão dentro da safra? (scripts 53 e 55)

NDVI do MODIS (MOD13Q1, 250 m) no centroide de cada município, máximo e média
das imagens de janeiro–fevereiro, colheitas de 2001 a 2025, para os três
estados do Sul usados nos artigos de previsão (RS, PR e MS; 848
municípios). O mesmo random forest da seção 9, com e sem o NDVI, nas mesmas
linhas e com anos inteiros fora do treino. R² fora da amostra:

| Estado | Municípios | Clima e seca | Clima, seca e NDVI | Ganho |
| --- | --- | --- | --- | --- |
| RS | 394 | 0,413 | 0,424 | +0,011 |
| PR | 368 | 0,198 | 0,203 | +0,005 |
| MS | 70 | 0,105 | 0,124 | +0,019 |
| Os três juntos | 832 | 0,293 | 0,314 | +0,021 |

- **O NDVI acrescenta pouco** (+0,005 a +0,021 de R²): a seca de
  janeiro–fevereiro, que o NDVI registra, já está nos índices de clima (SPEI,
  dias secos, umidade do solo). Schwalbert et al. (2020) encontraram ganho
  maior com NDVI ao longo de toda a safra e com máscara de lavoura; aqui é um
  pixel no centroide, que nem sempre é soja.
- O NDVI só serve para previsão durante a safra, nunca para projeção.
- Para os outros sete estados: `python scripts/53_download_modis_ndvi.py BR:SP
  BR:GO ...` e depois o script 55 (cerca de 35 s por município).

## 9e. Graus-dia acima de 30 °C com séries diárias de cenário (scripts 46 e 56)

Séries diárias corrigidas do NEX-GDDP-CMIP6 (0,25°), um modelo
(MPI-ESM1-2-LR), colheitas de 2005–2014 (histórico) contra 2051–2060
(SSP5-8.5). A variação de graus-dia e chuva na estação é convertida em
variação de produtividade pelos coeficientes de Schlenker-Roberts de cada
país (seção 9). Medianas por estado:

| Estado | Graus-dia > 30 °C, histórico | Variação | Variação de GDD 10–30 °C | Chuva | Produtividade | Municípios que pioram |
| --- | --- | --- | --- | --- | --- | --- |
| MT | 251 | +145 | +197 | −5% | **−17%** | 100% |
| TO | 201 | +119 | +204 | −2% | **−12%** | 100% |
| BA | 113 | +114 | +264 | +5% | −10% | 94% |
| MA | 194 | +90 | +162 | +3% | −9% | 100% |
| MS | 198 | +89 | +211 | +1% | −7% | 100% |
| GO | 146 | +66 | +212 | +9% | −3% | 76% |
| SP | 95 | +54 | +273 | +2% | −1% | 54% |
| PR | 42 | +34 | +319 | 0% | +4% | 25% |
| RS | 28 | +35 | +357 | −4% | +4% | 31% |
| MG | 47 | +35 | +302 | +6% | +4% | 32% |

- **Com séries diárias, o Centro-Oeste e o Matopiba são os mais
  prejudicados** (MT −17%, TO −12%): já começam com muitos graus-dia acima de
  30 °C e ganham mais 90 a 145.
- **No Sul o resultado inverte o das projeções por deltas mensais (seção 5).**
  O RS e o PR ganham ~4% porque o aumento de graus-dia benéficos (10–30 °C)
  supera o de graus-dia acima de 30 °C, que partem de níveis baixos. As
  projeções mensais da seção 5 usam o modelo quadrático de Tmax média, em que
  o RS e o PR já estão acima do ótimo.
- As duas abordagens respondem a perguntas diferentes e nenhuma é a resposta
  final: a de graus-dia usa coeficientes do painel conjunto (os mesmos para
  todos os estados), e a de deltas mensais não capta a mudança na frequência
  de dias quentes. **Um modelo e dez anos não bastam para uma projeção**: o
  objetivo aqui é demonstrar o método diário; para publicar, rode o script 46
  com mais modelos e períodos de 30 anos.

## 10. Limites desta análise

- **Um único ponto de clima por município**, o centroide, numa grade de
  ~50 km. Municípios grandes de MT, TO e MA são mal representados.
- **A janela crítica é fixa em janeiro–fevereiro** em todas as tabelas acima.
  Janelas posicionadas pela semeadura (seção 9c) melhoram o ajuste só onde o
  sinal é fraco (MT e Matopiba), e pouco.
- **A data de semeadura da Conab é estadual** e só cobre 2020–2026; o
  deslocamento de 60 a 105 dias até o enchimento de grãos é suposto.
- **1981 tem estação incompleta** (o NASA POWER começa em janeiro de 1981).
- **A comparação EUA × Brasil (scripts `36` e `37`) usa a janela 1980–2025**;
  ver `results/_eda_us_brazil/EDA_REPORT.md`.
- **A PAM é revista pelo IBGE**; os dados de produtividade são os baixados
  pelo `br_01` na data original, não foram atualizados agora.
