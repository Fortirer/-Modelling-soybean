# Variáveis disponíveis e o que elas mostram, por estado

Gerado por `scripts/57_state_inventory.py` a partir de `data/final/model_panel_us.csv.gz`
(12 estados, condado × ano, 1980–2025, 260 colunas) e `model_panel_br.csv.gz`
(10 estados, município × ano, 1974–2025, 152 colunas). Tabelas completas:
`state_coverage.csv`, `state_descriptive.csv`, `state_yield_correlations.csv`.

## 1. Cobertura: o que existe para cada estado

Percentual de unidade-anos com produtividade que também têm a variável.

| Grupo de variáveis | EUA (12 estados) | Brasil (10 estados) |
|---|---|---|
| Produtividade, área, produção | 100% | 100% |
| Clima mensal da estação (nClimDiv / POWER) | 100% | 89–100% (só falta 1974–1980) |
| PDSI / índice Z de Palmer | 100% | não existe |
| Extremos diários: graus-dia, dias quentes, VPD, ETCCDI (estação e janela crítica) | 100% (Daymet) e 97–99% (POWER) | 88–100% (POWER; falta 1974–1981) |
| SPI/SPEI, umidade do solo (GWETROOT) | 97–99% | 88–100% |
| Fenologia ano a ano (semeadura, R1–R8, janela de enchimento) | 96–99% (NASS Crop Progress) | não existe por ano; janela fixa pelo ZARC e data mediana da Conab |
| Balanço hídrico (déficit, dias de estresse) | 90–98% | 89–100% |
| Solo: textura, MO, pH, densidade, CEC, AWC/AWS | 91–100% (SSURGO) | 94–100% (SoilGrids) |
| Solo: ksat, drenagem, declividade, % Mollisol | 91–100% | não existe |
| Irrigação | 99–100% (Censo, média) | 78–98% (Censo 2017, fixo) |
| CO₂, ONI/ENSO | 100% | 100% |
| Clima mensal (m1–m5) e semanal (w01–w26) | todos | todos |
| Deltas mensais CMIP6 | todos | todos |
| Graus-dia diários NEX-GDDP (1 modelo, 2051–60) | todos | todos |
| Data de semeadura Conab por safra (2020–2026) | — | todos, mais PA, PI, SC (fora do painel) |
| NDVI MODIS (jan–fev) | — | só RS, PR, MS |

Para planejar o modelo, três coisas pesam mais do que esse percentual:

- **No Brasil, a janela útil começa em 1982.** O IBGE tem produtividade desde 1974, mas o
  NASA POWER começa em 1981 e a primeira safra completa é 1981/82. As lacunas de clima
  de 1974–1980 respondem por todos os percentuais abaixo de 100%. De 1982 em diante, a
  cobertura é de 100% nos 10 estados.
- **Painel balanceado fino em alguns estados.** Com pelo menos 20 anos de dados:

  | Estado | Unidades no painel balanceado | Total de unidades |
  |---|---|---|
  | ND | 17 | 52 |
  | SD | 27 | 63 |
  | MI | 36 | 72 |
  | KS | 48 | 105 |
  | BA | 10 | 46 |
  | MA | 27 | 94 |

  Nesses estados, efeitos fixos de município e coeficientes por estado têm pouca
  informação. Prefira coeficientes pooled por país ou por região.
- **Lacunas específicas.**
  - O SSURGO de SD (91%) e MI (99%) falha nos levantamentos multi-condado. Esses
    condados aparecem sem solo até o Soil Data Access voltar (script 54).
  - A irrigação de TO cobre só 78%.
  - O NDVI existe apenas para RS, PR e MS.

## 2. Perfil climático e produtivo (2016–2025)

Medianas por unidade-ano. EDD30 são os graus-dia acima de 30 °C. A janela crítica é
julho–agosto nos EUA e janeiro–fevereiro no Brasil.

| Estado | Produtividade (kg/ha) | Tendência (kg/ha/ano) | CV sem tendência | Pior ano (desvio) | Tmax da estação (°C) | Chuva da estação (mm) | EDD30 da estação | EDD30 da janela | VPD da janela (kPa) | Déficit hídrico (mm) | AWS 0–100 cm (cm) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| IA | 3.921 | 37 | 9% | 2003 (−32%) | 24,9 | 630 | 14 | 7 | 0,99 | 55 | 17,9 |
| IL | 4.062 | 44 | 9% | 1988 (−22%) | 26,3 | 648 | 20 | 11 | 1,03 | 47 | 17,7 |
| IN | 3.810 | 38 | 8% | 1988 (−22%) | 25,5 | 654 | 13 | 7 | 1,00 | 43 | 16,1 |
| KS | 2.656 | 21 | 20% | 2023 (−43%) | 28,1 | 598 | 67 | 41 | 1,28 | 99 | 14,9 |
| MI | 3.087 | 28 | 9% | 2003 (−30%) | 23,3 | 540 | 5 | 3 | 0,97 | 36 | 13,7 |
| MN | 3.302 | 27 | 10% | 1993 (−33%) | 22,8 | 564 | 6 | 2 | 0,91 | 14 | 17,8 |
| MO | 3.174 | 35 | 12% | 2012 (−32%) | 27,1 | 686 | 34 | 22 | 1,08 | 82 | 15,3 |
| ND | 2.253 | 18 | 14% | 1993 (−35%) | 22,3 | 391 | 7 | 4 | 1,07 | 100 | 16,1 |
| NE | 3.948 | 43 | 10% | 2022 (−21%) | 26,2 | 526 | 32 | 17 | 1,15 | 108 | 18,0 |
| OH | 3.521 | 35 | 10% | 2002 (−26%) | 25,0 | 619 | 11 | 6 | 0,99 | 67 | 14,5 |
| SD | 2.936 | 30 | 12% | 1993 (−26%) | 24,3 | 444 | 19 | 11 | 1,15 | 88 | 17,2 |
| WI | 3.315 | 31 | 12% | 2003 (−33%) | 22,5 | 647 | 4 | 2 | 0,91 | 2 | 16,0 |
| BA | 3.568 | 63 | 20% | 2016 (−50%) | 33,1 | 724 | 233 | 28 | 1,39 | 662 | 11,4 |
| GO | 3.400 | 48 | 9% | 1990 (−28%) | 31,1 | 1.107 | 133 | 4 | 0,82 | 90 | 12,1 |
| MA | 3.059 | 42 | 18% | 1990 (−67%) | 33,3 | 948 | 300 | 19 | 0,94 | 308 | 13,3 |
| MG | 3.600 | 49 | 9% | 1990 (−25%) | 29,3 | 1.005 | 52 | 1 | 0,79 | 117 | 11,6 |
| MS | 3.120 | 38 | 14% | 2022 (−37%) | 32,9 | 942 | 224 | 38 | 1,23 | 310 | 15,0 |
| MT | 3.364 | 43 | 8% | 2024 (−21%) | 31,7 | 1.169 | 179 | 4 | 0,71 | −33 (excedente) | 14,5 |
| PR | 3.399 | 34 | 13% | 2022 (−38%) | 29,4 | 1.075 | 49 | 11 | 0,97 | 7 | 9,1 |
| RS | 2.880 | 30 | 27% | 2005 (−74%) | 27,5 | 1.004 | 28 | 14 | 1,04 | 6 | 7,1 |
| SP | 3.000 | 37 | 10% | 2024 (−28%) | 31,0 | 946 | 103 | 11 | 0,94 | 235 | 14,9 |
| TO | 3.000 | 44 | 9% | 2016 (−27%) | 32,8 | 1.184 | 249 | 14 | 0,86 | 31 | 15,1 |

O que a tabela mostra:

- **O risco está concentrado em poucos estados.** O RS tem o maior coeficiente de
  variação (27%) e a maior quebra registrada (−74% em 2005). Depois vêm KS (20%),
  BA (20%) e MA (18%). MT, GO, MG, TO, IN, IL e IA ficam abaixo de 10%.
- **O calor da estação no Brasil é de outra ordem.** BA, MA, TO, MS e MT acumulam de 180 a
  300 EDD30 na estação, contra 4 a 67 nos EUA. Porém, na janela crítica (janeiro–fevereiro,
  época de chuva), MT, GO e MG ficam com apenas 1 a 4 EDD30. O calor desses estados cai
  fora do enchimento de grãos.
- **Déficit hídrico.** O oeste da Bahia tem o maior déficit (662 mm), seguido de MS
  (310 mm), MA (308 mm) e SP (235 mm). MT tem excedente. No Sul, o déficit mediano é
  pequeno, mas o RS e o PR têm a menor água disponível no solo do conjunto (7 e 9 cm).
  Isso é coerente com a água no solo ser significativa só no RS no `br_11`.

## 3. O que se correlaciona com a produtividade, por estado

A tabela mostra a correlação dentro da unidade entre a anomalia de produtividade
(sem tendência) e cada variável, centrada na média da unidade, no painel balanceado.
Ela é descritiva: ajuda a escolher variáveis, mas não é um coeficiente causal.

| Estado | EDD30 janela | Tmax janela | Chuva janela | VPD janela | SPEI-3 | Umidade raiz | Dias secos seguidos | EDD janela fenológica |
|---|---|---|---|---|---|---|---|---|
| IA | −0,31 | −0,27 | 0,24 | −0,34 | 0,21 | −0,08 | −0,21 | −0,39 |
| IL | −0,49 | −0,42 | 0,43 | −0,52 | 0,42 | 0,16 | −0,31 | −0,53 |
| IN | −0,47 | −0,41 | 0,33 | −0,52 | 0,31 | 0,06 | −0,26 | −0,43 |
| KS | −0,54 | −0,56 | 0,47 | −0,51 | 0,47 | 0,27 | −0,28 | −0,54 |
| MI | −0,03 | 0,03 | 0,37 | −0,19 | 0,33 | 0,20 | −0,17 | −0,18 |
| MN | −0,12 | 0,09 | 0,23 | −0,09 | 0,08 | −0,16 | −0,12 | −0,19 |
| MO | −0,56 | −0,57 | 0,49 | −0,56 | 0,48 | 0,24 | −0,34 | −0,55 |
| ND | −0,20 | 0,03 | 0,17 | −0,20 | 0,16 | 0,08 | −0,20 | −0,15 |
| NE | −0,31 | −0,31 | 0,27 | −0,33 | 0,30 | 0,17 | −0,25 | −0,38 |
| OH | −0,38 | −0,31 | 0,36 | −0,40 | 0,28 | 0,09 | −0,25 | −0,32 |
| SD | −0,48 | −0,31 | 0,29 | −0,38 | 0,29 | 0,08 | −0,11 | −0,43 |
| WI | −0,21 | 0,00 | 0,39 | −0,25 | 0,31 | 0,07 | −0,25 | −0,39 |
| BA | −0,03 | −0,07 | 0,10 | −0,09 | 0,08 | 0,01 | **−0,45** | −0,03 |
| GO | −0,06 | −0,07 | 0,09 | −0,08 | 0,05 | 0,07 | −0,19 | −0,06 |
| MA | −0,18 | −0,15 | 0,11 | −0,16 | 0,16 | 0,06 | **−0,36** | −0,18 |
| MG | −0,14 | −0,17 | 0,18 | −0,18 | 0,16 | 0,13 | −0,15 | −0,14 |
| MS | −0,44 | −0,43 | 0,30 | −0,45 | 0,39 | 0,30 | −0,30 | −0,44 |
| MT | −0,11 | −0,13 | 0,01 | −0,10 | 0,07 | 0,08 | −0,11 | −0,11 |
| PR | −0,48 | −0,42 | 0,26 | −0,46 | 0,44 | 0,30 | −0,30 | −0,48 |
| RS | −0,49 | −0,51 | 0,44 | **−0,57** | **0,53** | 0,43 | −0,23 | −0,49 |
| SP | −0,21 | −0,19 | 0,10 | −0,20 | 0,13 | 0,11 | −0,14 | −0,21 |
| TO | −0,18 | −0,18 | 0,00 | −0,15 | 0,07 | 0,07 | −0,19 | −0,18 |

Pela força do sinal climático, os estados se dividem em três grupos:

1. **Sinal forte de calor e seca na janela crítica** (|r| de 0,45 a 0,57):
   - EUA: MO, KS, IL, IN e SD.
   - Brasil: RS, PR e MS.

   Aqui os modelos de graus-dia (Schlenker–Roberts) e de VPD funcionam bem. O VPD da
   janela é, na maioria desses estados, a variável isolada mais forte. No RS, o SPEI-3 e a
   umidade do solo também são fortes.
2. **Sinal de água, não de calor** (MI, WI, MN, ND): o EDD30 quase não pesa
   (|r| ≤ 0,2), e a chuva ou o SPEI da janela é que se relacionam com a produtividade.
   Faz sentido, porque esses estados quase não passam de 30 °C (2 a 4 EDD30 na janela).
3. **Sinal climático fraco no ponto do município** (GO, MT, MG, SP, TO, |r| < 0,25;
   BA e MA, com exceção dos dias secos seguidos):
   - No Matopiba (BA e MA), o que pesa são os veranicos (dias secos seguidos,
     r = −0,45 e −0,36), não o calor.
   - No Centro-Oeste, chove o bastante em janeiro–fevereiro (EDD30 de 1 a 4), e a
     variação de produtividade vem mais de outros fatores: semeadura (2 a 5 semanas antes
     do ZARC, Conab), ciclo da cultivar, segunda safra, manejo. Um pixel do POWER no
     centroide também capta mal a chuva local.

     Para esses estados, variáveis de semeadura e veranico ajudam mais do que graus-dia.
     A janela móvel pela data da Conab (script 49) e o NDVI ainda não baixado também são
     candidatos.

## 4. Implicações para os modelos

- **Projeções.** O impacto projetado se concentra onde o calor já pesa e onde ele vai
  crescer: no NEX-GDDP (MPI-ESM1-2-LR, SSP5-8.5, 2051–60), MT −17%, TO −12%, BA −10%,
  MA −9% e MS −7%; nos EUA, KS −22%, SD −12% e NE −9%. Esses são justamente estados onde
  o EDD30 da estação já é alto. A projeção de MT e TO, porém, se apoia num coeficiente
  pooled: no próprio estado, o sinal histórico de calor é fraco (r ≈ −0,1). Isso precisa
  aparecer como limitação no texto.
- **Estados com poucas unidades balanceadas** (ND, SD, MI, KS, BA, MA): use-os dentro de
  modelos pooled, não com coeficiente próprio.
- **Comparação entre países.** Mantenha a janela comum de 1982–2025. Use apenas as
  variáveis presentes nos dois painéis:
  - graus-dia e ETCCDI da estação e da janela crítica;
  - VPD;
  - SPI e SPEI;
  - GWETROOT;
  - textura e AWC do solo;
  - CO₂ e ONI.

  PDSI, fenologia anual, ksat e drenagem existem só nos EUA. Entram apenas nos modelos
  dos EUA.
- **Previsão dentro da safra com NDVI.** Só é possível em RS, PR e MS por enquanto. O
  script 53 baixa os outros sete estados.
