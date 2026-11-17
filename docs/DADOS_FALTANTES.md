# Dados faltantes: o que foi coletado e como rodar os modelos

Este documento fecha as lacunas apontadas no relatório *Artigos de modelagem
clima × soja e variáveis para baixar de bases públicas* (16/11/2026). Ele diz,
para cada lacuna, o que foi baixado, onde está, com qual script se refaz, e o
que ainda depende de uma credencial sua. No fim há a correspondência
artigo → modelo → colunas, e o comando que ajusta os modelos.

Tudo aqui é adicional: nenhum script de `01` a `37` nem `br_01` a `br_20` foi
alterado. Os scripts novos são `38` a `48`, mais os módulos `_gap.py` e
`_indices.py`.

## 1. Situação de cada lacuna

| Lacuna do relatório | Situação | Arquivo gerado | Script |
| --- | --- | --- | --- |
| Graus-dia > 30 °C no painel dos EUA | Feito | `data/processed/<UF>/heat_extremes_daymet.csv` | 40, 41 |
| Clima diário dos EUA em 1980 e 2025 | Feito (Daymet, 1980–2025) | `data/raw/<UF>/daymet_daily.csv.gz` | 40 |
| Clima diário do Brasil até 2025 | Feito (NASA POWER, 1981–2025) | `data/raw/BR/<UF>/power_daily.csv.gz` | 39 |
| Índice de seca no Brasil (SPI, SPEI) | Feito, 3 e 6 meses | `data/processed/BR/<UF>/drought_soil_moisture_features.csv` | 42 |
| Umidade do solo, EUA e Brasil | Feito com MERRA-2 (sem login); NLDAS-2 e ERA5-Land dependem de login | mesmo arquivo acima; colunas `gwetroot_*` | 39, 42 (44, 45 com login) |
| Ondas de calor e índices ETCCDI | Feito | `heat_extremes_*.csv` | 41 |
| CO₂ anual | Feito (1959–2025) | `data/raw/global/co2_annual_mlo.csv` | 38 |
| Índice ONI (El Niño) | Feito (1950–2026) | `data/raw/global/oni_monthly.csv`, `oni_crop_year.csv` | 38 |
| SoilGrids incompleto | Feito: de ~650 para 11 municípios incompletos | `data/raw/BR/<UF>/soilgrids_horizons.csv` | 43 |
| Água disponível no solo, Brasil | Feito, 2.441 municípios | `data/processed/BR/<UF>/soil_awc_features.csv` | 43 |
| CMIP6 diário (NEX-GDDP) | Um modelo (MPI-ESM1-2-LR), 2005–2014 histórico e 2051–2060 SSP5-8.5; ver seção 3 | `data/raw/<UF>/nex_gddp/` | 46, 56 |
| Painéis prontos para modelar | Feito | `data/final/model_panel_us.csv.gz`, `model_panel_br.csv.gz` | 47 |
| Modelos dos artigos | Feito, como exemplo | `results/_literature_models/` | 48, 51, 55 |
| Água disponível nos modelos de solo do Brasil | Feito | `results/BR/<UF>/br14_soil_explains_level.csv` | br_09, br_11 |
| Janela crítica por região | Feito, pela data do ZARC e pela data observada da Conab | `data/processed/BR/<UF>/regional_window_features_*.csv` | 49 |
| Calendário de semeadura e colheita da Conab | Feito, 2020–2026, por estado | `data/raw/BR/conab_soja_progress.csv` | 52 |
| NDVI do MODIS | RS, PR e MS (848 municípios, 2001–2025); ver seção 3 | `data/processed/BR/<UF>/modis_ndvi_features.csv` | 53, 55 |
| Produtividade de NE e KS | Conferido: idêntico ao NASS atual; ver seção 3 | — | 01 |
| SSURGO multi-condado | Script pronto; o Soil Data Access estava fora do ar | — | 54 |

`<UF>` é a sigla do estado. Illinois não tem subpasta (os arquivos ficam direto
em `data/raw/` e `data/processed/`), como no restante do repositório.

## 2. Cobertura obtida

Clima diário, sem nenhuma unidade com falha de download:

| | Unidades | NASA POWER (script 39) | Daymet (script 40) | Calor e extremos (41) | Seca e umidade do solo (42) |
| --- | --- | --- | --- | --- | --- |
| EUA, 12 estados | 1.055 condados | 1981–2025 | 1980–2025 | 1980–2025 | 1981–2025 |
| Brasil, 10 estados | 2.519 municípios produtores | 1981–2025 | não cobre | safras plantadas 1981–2024 | safras plantadas 1981–2024 |

Os arquivos diários somam 1,3 GB (POWER) e 0,36 GB (Daymet). No Brasil a
safra plantada em 2025 fica de fora: ela precisa de janeiro–fevereiro de
2026. No painel, onde o ano é o da colheita, as colunas novas vão de 1982 a
2025.

Solo do Brasil (script 43):

| Estado | Municípios com SoilGrids | Ainda incompletos | Com água disponível | Mediana, cm no 1º metro |
| --- | --- | --- | --- | --- |
| MT | 141 | 0 | 139 | 14,6 |
| PR | 392 | 5 | 386 | 9,2 |
| GO | 239 | 2 | 236 | 12,2 |
| RS | 479 | 3 | 459 | 7,0 |
| MS | 79 | 1 | 78 | 15,1 |
| MG | 392 | 0 | 392 | 11,6 |
| BA | 46 | 0 | 46 | 11,5 |
| TO | 117 | 0 | 117 | 14,7 |
| SP | 496 | 0 | 496 | 15,0 |
| MA | 92 | 0 | 92 | 13,4 |

Os municípios com propriedades faltando caíram de cerca de 650 para 11. Os
que continuam sem valor (os 11 incompletos, e 35 municípios de SP, 9 de MG,
2 do MA e poucos em outros estados sem nenhum dado) são centroides onde o
SoilGrids devolve vazio, em geral área urbana ou água. A mediana do RS (7 cm)
é bem menor que a da função de pedotransferência (12,7 cm); confira antes de
usar em balanço hídrico.

Painéis (script 47), sem nenhum bloco de entrada faltando:

| Painel | Linhas | Unidades | Colunas | Anos |
| --- | --- | --- | --- | --- |
| `model_panel_us.csv.gz` | 39.180 | 1.029 condados | 260 | 1980–2025 |
| `model_panel_br.csv.gz` | 73.800 | 2.520 municípios | 152 | 1974–2025 (clima a partir de 1981) |

No painel dos EUA, 1980 tem calor e chuva (Daymet), mas não SPEI nem umidade
do solo, porque o NASA POWER começa em 1981. As colunas de fenologia do
script 18 foram refeitas com o clima diário novo e vão de 1981 a 2025; cerca
de 10% dos valores antigos mudaram, por um dia na data de algum estádio
(correlação com os anteriores acima de 0,999).

## 3. O que ficou parcial ou depende de você

- **NLDAS-2 (EUA) e ERA5-Land (Brasil).** As duas bases exigem conta pessoal
  (NASA Earthdata e Copernicus CDS). Os scripts 44 e 45 estão escritos, mas
  **nunca foram executados**: podem precisar de ajuste no nome do arquivo ou
  da variável. O cabeçalho de cada um traz o passo a passo da credencial. A
  umidade do solo do MERRA-2 (script 42) cobre os dois países enquanto isso.
- **NEX-GDDP-CMIP6.** Cada arquivo tem ~245 MB (um modelo, um cenário, uma
  variável, um ano, o globo inteiro) e não há serviço público de recorte; o
  desenho de 8 modelos do script 12 seria ~3.600 arquivos. Foi baixado um
  modelo (MPI-ESM1-2-LR) para 2005–2014 (histórico) e 2051–2060 (SSP5-8.5),
  todas as regiões. Para mais modelos ou anos, rode o script 46 com outro
  `--model` ou `--years`; ele retoma de onde parou. A extração dos pontos foi
  reescrita em 17/11: a versão anterior lia o arquivo global ponto a ponto e
  não terminava.
- **NDVI do MODIS.** O serviço do ORNL devolve no máximo 10 imagens por pedido
  e leva 3 a 8 s por pedido, então cada município custa 25 pedidos (um por
  safra, 2001–2025). Foram coletados RS, PR e MS, os estados do Sul usados nos
  artigos de previsão dentro da safra, só o NDVI (o EVI dobraria o tempo).
  Para os demais: `python scripts/53_download_modis_ndvi.py BR:SP BR:GO ...`,
  que retoma pelo cache.
- **Produtividade de Nebraska e Kansas.** Baixei de novo do arquivo bruto
  atual do NASS (`qs.crops_20261117`): os valores são **idênticos** aos que já estavam
  no repositório. Não há erro de download. A queda no número de condados vem
  de o NASS publicar parte crescente da produção só como "OTHER (COMBINED)
  COUNTIES" para não identificar produtores: em 2025, 47% da produção de
  Nebraska e 37% da de Kansas (27% em Iowa). Esses valores não podem ser
  atribuídos a condados. No caminho, o NASS tinha mudado o endereço dos
  arquivos brutos; `_nass_bulk.py` foi corrigido, o que também conserta os
  scripts 23 e 29.
- **SSURGO, condados em levantamentos multi-condado** (9 em SD, 2 em MN, 5 em
  MI). O script 54 resolve: consulta a tabela de sobreposição do SSURGO e
  arquiva as linhas já baixadas sob o condado certo, com a área de cada
  unidade de mapeamento dentro dele. **Não rodou** porque o Soil Data Access
  do USDA estava fora do ar (erro 502 até na página inicial) durante toda a
  sessão de 17/11. Quando voltar: `python scripts/54_ssurgo_multicounty.py` e
  depois `STATE=SD python scripts/15_soil_features.py` (idem MN, MI).
- **Calendário da Conab.** Coletado (script 52), mas a Conab só mantém online
  os boletins de 2020 em diante e só por estado; não substitui uma calibração
  da fenologia por município.

## 4. Como refazer tudo

Do diretório raiz do repositório. Sem argumentos, cada script percorre os 12
estados dos EUA e os 10 do Brasil; `US`, `BR`, `US:IA` ou `BR:MT` restringem.

```bash
pip install -r requirements.txt
python scripts/38_download_co2_oni.py                    # segundos
python scripts/39_download_power_daily_all.py            # ~1 h, retomável
python scripts/40_download_daymet_daily.py               # ~25 min, retomável
python scripts/41_heat_extremes_features.py              # EUA: Daymet; Brasil: POWER
python scripts/41_heat_extremes_features.py --source power US   # EUA igual ao Brasil
python scripts/42_drought_soil_moisture.py
python scripts/43_br_soil_water.py                       # ~3 h (API lenta), retomável
python scripts/47_build_model_panels.py
python scripts/48_literature_models.py
python scripts/49_br_regional_window.py --sowing conab   # ou --sowing zarc
python scripts/50_monthly_weekly_weather.py
python scripts/51_literature_models_inseason.py
python scripts/52_download_conab_progress.py             # ~10 min
python scripts/53_download_modis_ndvi.py BR:RS BR:PR     # lento: ~35 s por município
python scripts/55_inseason_ndvi_prediction.py
python scripts/46_download_nex_gddp_daily.py --scenario historical --years 2005 2014
python scripts/46_download_nex_gddp_daily.py --scenario ssp585 --years 2051 2060
python scripts/56_degree_day_projection.py
python scripts/54_ssurgo_multicounty.py                  # precisa do Soil Data Access no ar
python -m pytest tests -q                                # testes das funções de índice
```

Depois do script 43, para atualizar `soil_features.csv` de cada estado com as
propriedades preenchidas: `UF=MT python scripts/br_09_soil_features.py`.

Os arquivos diários (`power_daily.csv.gz`, `daymet_daily.csv.gz`) são grandes
e estão no `.gitignore`; quem clonar o repositório os recria com os scripts 39
e 40. Com eles no lugar, os scripts antigos que dependem do clima diário
(`18`, `br_05`, `br_10`) voltam a rodar. O `power_daily.csv.gz` novo tem as
mesmas colunas de antes mais `gwetroot`, `gwettop` e `rh_pct`, e vai até 2025.

## 5. Arquivos novos e colunas

**`heat_extremes_daymet.csv` / `heat_extremes_power.csv`** — uma linha por
unidade e ano-safra. Prefixo `gs_` = estação de crescimento (EUA abril–setembro;
Brasil setembro–abril); `cw_` = janela crítica (EUA julho–agosto; Brasil
janeiro–fevereiro).

| Coluna | Significado |
| --- | --- |
| `gdd_10_30` | graus-dia entre 10 e 30 °C |
| `edd_29`, `edd_30`, `edd_32`, `edd_34` | graus-dia acima do limiar (seno simples) |
| `hot_days_30/32/35` | dias com Tmax ≥ limiar |
| `warm_nights_20/24` | dias com Tmin ≥ limiar |
| `txx`, `tnn`, `tmax_mean`, `tmin_mean` | extremos e médias (°C) |
| `wsdi_days` | dias em sequências ≥ 6 dias com Tmax acima do percentil 90 da unidade para o mês (base 1981–2010) |
| `prcp_mm`, `dry_days`, `cdd`, `rx1day`, `rx5day`, `r20mm` | chuva total, dias < 1 mm, maior sequência seca, máximo de 1 e 5 dias, dias ≥ 20 mm |
| `vpd_mean_kpa` | déficit de pressão de vapor médio |

**`drought_soil_moisture_features.csv`** — uma linha por unidade e ano-safra.

| Coluna | Significado |
| --- | --- |
| `spei3_critical`, `spi3_critical` | índice de 3 meses terminando no fim da janela crítica (EUA agosto; Brasil fevereiro) |
| `spei6_season`, `spi6_season` | índice de 6 meses no fim da estação (EUA setembro; Brasil março) |
| `spei3_min_grow` | SPEI-3 mais seco da estação |
| `drought_months_grow` | meses da estação com SPEI-3 < −1 |
| `gwetroot_grow`, `gwetroot_critical`, `gwettop_critical` | umidade do solo, fração da saturação (0–1), zona radicular 0–100 cm e superfície |
| `gwetroot_critical_z` | anomalia padronizada em relação à própria unidade |
| `gwetroot_min_month` | mês mais seco da estação |

`drought_monthly.csv` traz a série mensal completa (chuva, ET0, SPI, SPEI,
umidade do solo), útil para definir outras janelas.

**`soil_awc_features.csv`** (Brasil) — `soil_aws_0_100cm` é a água disponível
no primeiro metro, em cm, pelos mapas de retenção do SoilGrids (33 e 1500 kPa);
mesmo nome e unidade da coluna dos EUA. As colunas com sufixo `_sr` são a
mesma grandeza pela função de pedotransferência de Saxton & Rawls (2006).

**`model_panel_us.csv.gz` / `model_panel_br.csv.gz`** — tudo junto, chave
`fips5` + `year`. `data/final/MODEL_PANEL_COLUMNS.csv` lista cada coluna, o
bloco de origem, a cobertura e o intervalo de anos. No painel dos EUA as
colunas `pw_*` são os mesmos índices de calor calculados com NASA POWER, para
modelos conjuntos EUA + Brasil que não podem misturar fontes.

## 6. Artigo → modelo → colunas

O script 48 ajusta uma especificação por artigo, com o mesmo código nos dois
países. Efeitos fixos de unidade e tendência quadrática por estado em todas.

| Artigo | Especificação no script 48 | Colunas do painel |
| --- | --- | --- |
| Schlenker & Roberts 2009 | `schlenker_roberts_2009` | `gs_gdd_10_30`, `gs_edd_30`, `gs_prcp_mm` e seu quadrado |
| Ortiz-Bobea et al. 2019 | `ortiz_bobea_2019` | as anteriores + `gwetroot_critical` e seu quadrado |
| Lobell et al. 2014 | `lobell_2014` | `gs_gdd_10_30`, `cw_vpd_mean_kpa`, `cw_prcp_mm` e seu quadrado |
| Silva et al. 2023 | `silva_2023` | temperatura média da estação, `gs_prcp_mm` e seu quadrado |
| Parisoto et al. 2026 | `parisoto_2026` | `spei3_critical`, `cw_wsdi_days` e o produto (evento composto) |
| Leng & Hall 2020; Benso et al. 2025 | random forest contra a regressão, anos inteiros fora do treino | 26 variáveis de clima, seca, umidade do solo e ONI |
| Mourtzinis et al. 2015 | script 51, efeito de cada mês da estação | `m1_tmean`…`m5_prcp` (script 50) |
| Khaki et al. 2020 | script 51: random forest e rede neural densa sobre 26 semanas de clima (não a CNN-RNN original) | `w01_tmax`…`w26_vpd` (script 50) |
| von Bloh 2023; Schwalbert 2020; Azevedo & Boccato 2026 | script 55: random forest com e sem NDVI de janeiro–fevereiro | `ndvi_jf_max`, `ndvi_jf_mean` (script 53) |
| Jägermeyr 2021; Zilli 2020; Guilpart 2022 | script 56: variação de graus-dia com séries diárias do NEX-GDDP e coeficientes de Schlenker-Roberts; CO₂ disponível em `co2_ppm`, não usado | `nex_gddp/*.csv.gz` (script 46) |

Resultados em `results/_literature_models/`: `coefficients.csv`,
`ml_comparison.csv`, `rf_importance.csv`, `config.json` (script 48);
`mourtzinis_monthly_coefficients.csv`, `khaki_weekly_comparison.csv` (51);
`br_regional_window_comparison_zarc.csv` e `_conab.csv` (49);
`inseason_ndvi_comparison.csv` (55); `degree_day_projection_*.csv` (56).

## 7. Ressalvas que afetam a leitura dos resultados

- **Daymet no lugar de PRISM ou gridMET.** O relatório sugere PRISM ou
  gridMET. O serviço de ponto do gridMET levou cerca de 2 minutos por variável
  por condado no teste de 16/11/2026, e os dois exigiriam baixar grades
  inteiras. O Daymet (1 km, 1980–2025) devolve todas as variáveis em ~2 s por
  ponto e é a fonte de Khaki et al. (2020).
- **Valor no centroide, não média da área agrícola.** Como nos scripts 17 e
  `br_04`, cada unidade recebe o valor da célula que contém o centroide.
  Schlenker & Roberts ponderam pela área de lavoura.
- **Fontes diferentes entre países.** O calor dos EUA vem do Daymet (1 km) e
  o do Brasil do NASA POWER (~50 km). No Illinois a média de graus-dia > 30 °C
  na estação foi 27 com Daymet e 24 com POWER, e os anos individuais divergem
  mais. Para comparar os países use as colunas `pw_*` do painel dos EUA.
- **Umidade do solo é de modelo.** `gwetroot` é a estimativa do modelo de
  superfície do MERRA-2, forçado por chuva corrigida; não é medida.
- **SPI/SPEI.** ET0 por Hargreaves-Samani (só temperatura e latitude), porque
  a radiação do POWER não existe antes de 1984. Ajuste por unidade e mês do
  calendário sobre 1981–2025. No Illinois o SPEI-3 de agosto tem correlação
  0,81 com o PDSI do NOAA já existente no painel.
- **Ano-safra do Brasil: ver a seção 8.** Nos arquivos dos scripts 41 e 42
  `year` é o ano de plantio (setembro–dezembro de `t`, janeiro–abril de
  `t+1`). No painel `model_panel_br.csv.gz` essas colunas já estão deslocadas
  para o ano da colheita, que é o ano da PAM.
- **Pedotransferência.** Saxton & Rawls foi ajustada em solos dos EUA e erra
  nos Latossolos (argila oxídica, bem agregada). Use `soil_aws_0_100cm` (mapas
  de retenção do SoilGrids) como estimativa principal.
- **Erros-padrão do script 48.** Agrupados por estado, com 12 (EUA) ou 10
  (Brasil) grupos, o que os subestima. O `p` é indicativo.
- **Deltas mensais × série diária.** Um delta mensal desloca todos os dias do
  mês igualmente e não reproduz a mudança na frequência de dias acima de
  30 °C. Para projetar com graus-dia, use o script 46.

## 8. Achado: o "ano" da PAM é o ano da colheita

Até 16/11/2026 o `br_05_process_climate.py` tratava o `ano` da PAM/IBGE como
ano de plantio e casava a produtividade de `t` com o clima de setembro de `t` a abril de `t+1`.
Os dados novos indicam que o `ano` é o da colheita: a soja semeada no fim de
`t−1` e que enche grão em janeiro–fevereiro de `t` é registrada em `t`.

Evidência, usando o SPEI-3 da janela crítica (script 42):

- No Rio Grande do Sul a produtividade despenca na PAM de 2005, 2012 e 2022,
  as colheitas das secas de 2004/05, 2011/12 e 2021/22. O SPEI mais negativo
  está nas safras plantadas em 2004, 2011 e 2021.
- A correlação entre a anomalia de produtividade e o SPEI-3 é praticamente
  zero com o alinhamento antigo do `br_05` e sobe com o deslocamento de um ano:
  RS 0,02 → 0,45; PR −0,07 → 0,36; MS −0,09 → 0,36; SP −0,02 → 0,13.
- Com o deslocamento, os modelos do script 48 passam a mostrar sinal de clima
  no Brasil. O R² dentro da unidade da especificação de Lobell vai de 0,01 a
  0,22, e o random forest em anos fora do treino vai de −0,02 a 0,22.

O que foi corrigido (16/11/2026, a seu pedido):

- **`br_05_process_climate.py` agora usa o ano da colheita:** setembro–dezembro
  de `t−1` e janeiro–abril de `t` contam para o `ano` `t`. Rodei de novo o
  `br_05` e o `br_06` nos 10 estados; `climate_features.csv` e o painel final
  de cada estado foram regenerados e agora cobrem 1981–2025 (antes 1980–2023,
  porque o clima diário antigo parava em 2024).
- Antes e depois, no painel balanceado de cada estado (correlação da anomalia
  de produtividade com a chuva e com a Tmax da janela crítica, e R² de uma
  regressão simples com as duas), em
  `results/_literature_models/br05_alignment_check.csv`:

| Estado | r chuva, antes → depois | r Tmax, antes → depois | R², antes → depois |
| --- | --- | --- | --- |
| RS | 0,10 → 0,43 | −0,08 → −0,50 | 0,03 → 0,32 |
| PR | −0,03 → 0,26 | 0,03 → −0,40 | 0,02 → 0,16 |
| MS | −0,09 → 0,31 | 0,14 → −0,40 | 0,03 → 0,16 |
| TO | 0,02 → 0,00 | −0,10 → −0,18 | 0,02 → 0,06 |
| SP | −0,07 → 0,10 | 0,06 → −0,19 | 0,01 → 0,04 |
| MG | −0,01 → 0,18 | 0,00 → −0,16 | 0,00 → 0,04 |
| MT | 0,04 → 0,01 | 0,05 → −0,13 | 0,01 → 0,02 |
| BA | 0,01 → 0,11 | −0,03 → −0,07 | 0,02 → 0,02 |
| MA | −0,04 → 0,11 | 0,02 → −0,14 | 0,00 → 0,02 |
| GO | −0,02 → 0,10 | 0,02 → −0,07 | 0,01 → 0,01 |

  Parte da diferença vem dos dois anos a mais de dados, não só do alinhamento.

- **`br_10_phenology_features.py` e `br_13_cmip6_scenarios.py`** tinham a
  mesma suposição e foram corrigidos do mesmo modo.
- **Todos os scripts de análise foram rodados de novo nos 10 estados** com o
  alinhamento novo: `br_10`, `br_07`, `br_11`, `br_13`, `br_14`, `br_16` e
  `br_17` (e o `br_09`, por causa do solo). Tabelas e figuras em
  `results/BR/<UF>/` e `figures/BR/<UF>/` são as novas. `br_18` (IMEA) e
  `br_20` (ZARC) não dependem do clima e não foram tocados.
- **`br_14_sensitivity_analysis.py`:** os cenários idealizados usavam um
  modelo de árvores que dava ganho de produtividade com o aquecimento. Agora
  usam o mesmo modelo quadrático do `br_13` e concordam com o CMIP6.
- A leitura dos resultados novos está em
  [`results/BR/ANALISE_ATUALIZADA.md`](../results/BR/ANALISE_ATUALIZADA.md).
  A extensão brasileira do README foi reescrita com esses resultados.
- **A comparação EUA × Brasil dos scripts `36` e `37`** foi rodada de novo
  (`results/_eda_us_brazil/`, `figures/_eda_us_brazil/`) e o `EDA_REPORT.md`
  revisto, agora com a janela 1980–2025. Com o alinhamento correto, o calor
  reduz a produtividade em 5,2% por °C no Brasil (2,6% nos EUA), e nenhum
  estado brasileiro tem efeito positivo significativo.

Detalhes que ficam:

- No painel `model_panel_br.csv.gz`, o script 47 desloca as colunas dos
  scripts 41 e 42 (`gs_*`, `cw_*`, `spei*`, `spi*`, `gwetroot*`, `oni_season`)
  para o ano da colheita e guarda o ano de plantio em `planting_year`. As
  colunas herdadas do `br_05` e do `br_10` já saem no ano da colheita.
- O primeiro ano (1981) tem estação incompleta, só janeiro–abril, porque o
  NASA POWER começa em 1981; `n_days_grow` permite filtrar.
