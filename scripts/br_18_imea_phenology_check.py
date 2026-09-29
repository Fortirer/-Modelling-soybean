"""BR 18 - IMEA regional planting/harvest timing check for Mato Grosso.

WHAT THIS DOES AND DOES NOT DO
  Neither CONAB nor IMEA (checked live, see chat) publish a municipality-
  resolution crop-progress series -- IMEA's own "Informe de Semeadura" and
  "Informe de Colheita" bulletins (public PDF reports, one per safra,
  scraped from https://www.imea.com.br/imea-site/relatorios-mercado)
  report percent-of-area-planted/harvested at the level of IMEA's OWN
  7-region breakdown of Mato Grosso (Centro-Sul, Medio-Norte, Nordeste,
  Noroeste, Norte, Oeste, Sudeste) -- a real, first-party, weekly-updated
  regional split, but coarser than IBGE's 5-mesorregiao grouping used in
  br_17, and far coarser than the 141-municipio panel the rest of this
  branch runs at. This CANNOT calibrate a municipio-level phenology model
  (that remains the genuine, unresolved gap noted in br_10/br_17).

  What it CAN do: most archived bulletins contain a full within-season
  weekly progress curve (percent planted/harvested each week, all 7
  regions at once), not just a single snapshot. For each region and
  season we interpolate the calendar day the curve first reaches 50%
  complete (days after 1-Sep for planting, 1-Feb for harvest) and test
  with a one-way ANOVA whether regions differ in typical timing, plus
  Kendall's W on the season-to-season earliness rank as a distribution-
  free check. This directly tests the question br_05/br_10's fixed
  Sep-Dec / Jan-Feb calendar-window assumption is resting on, at IMEA's
  regional resolution.

DATA
  15 seasons of Semeadura (planting) bulletins (2012/13-2026/27) and 13
  seasons of Colheita (harvest) bulletins (2013/14-2025/26), URLs scraped
  live from IMEA's site on 2026-09-29 (signed S3 links, ~5-day expiry --
  re-scrape if this script is run much later and downloads start failing).
  One Colheita link (safra 15/16) is mislabeled on IMEA's own site as an
  Algodão report; detected and skipped by content check below.
"""
import sys, re, json, time, urllib.request, urllib.parse
from pathlib import Path
import numpy as np, pandas as pd
import pdfplumber
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, FIG
from _viz import *

PDF_DIR = RAW / "imea_pdfs"
(PDF_DIR / "semeadura").mkdir(parents=True, exist_ok=True)
(PDF_DIR / "colheita").mkdir(parents=True, exist_ok=True)

REGIONS = ["Centro-Sul", "Medio-Norte", "Nordeste", "Noroeste", "Norte", "Oeste", "Sudeste"]
MONTHS = dict(jan=1, fev=2, mar=3, abr=4, mai=5, jun=6, jul=7, ago=8, set=9, out=10, nov=11, dez=12)

# scraped 2026-09-29 from relatorios-mercado-detalhe?c=4&s=696277987813359616 (Semeadura)
SEMEADURA = [
    ("26/27", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1837734623013240832-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dc7d86ca07890db7c0a0046247568f38c5106c3155263a62d2d93fc96adee45b9"),
    ("25/26", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1705814918498091008-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D421b29d32cf851c67e50587cde113330578cb2877b1a6edc2cbaf39cb63ef7d3"),
    ("24/25", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1576388605214982144-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T234637Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dd0d182117a412a959a7fd919309985427fc9a5877e9d3c3a058e429904605aa1"),
    ("23/24", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1439469450382278656-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T234637Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dc6dcbd97e47d2ac6f658d93472813580563d4552c0a0a7b2af7570be01c59c15"),
    ("22/23", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1349531353658425344-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T234637Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dc2a2a6ce78f6f06c52edfb0209a26d1afed2d3ba31a5374563c90b399bc2f154"),
    ("21/22", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309307845503557632-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D6132419b81873baa9c1a4aadec077aa5a66f1ba075e1a0ee7972abd8e382a400"),
    ("20/21", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309306977731420160-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D54caa4becda58d88ef935a6c0c8033f402749c2f8b71412633dae9acab7eb940"),
    ("19/20", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309306012185862144-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Daeab3c28a76dcb5beb801552c0bd030050685a12cffb103b5080c21861a6618d"),
    ("18/19", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309305690897981440-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Df7f348c6048dcd3fbe3b09377e76211de6ee69c3cfaa0628a2eee73b13a607b1"),
    ("17/18", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309305418620542976-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Ddcf5593c97b17e800196710b77b6c649d25cc0977ca97b83d8fab405b24890f3"),
    ("16/17", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309305208171339776-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D16ef1ade872476dc37903c367649cd91ccb1630228dfba3c98b9a99351c46f18"),
    ("15/16", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309304935810015232-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dc224975508df9c9d57592211486862555a14df1df53614eb0478270de2be4375"),
    ("14/15", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309303452104335360-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D5e3f4d3fd9016d75906e14c99e63e91dea9a8b44996ba6e5fc7fc479add8c8b9"),
    ("13/14", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277987813359616%2F1309303153453113344-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233405Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D62493a1131a91f0e89b48b386da0be502ca86d1023a11909f8eb6e9aecc4c0c4"),
]

# scraped 2026-09-29 from relatorios-mercado-detalhe?c=4&s=696277349624840192 (Colheita)
COLHEITA = [
    ("25/26", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1746410643212468224-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D603b0ae78e19d2bc71e73d25e58be7ef75fd59b0f08e4339a731a17b8079ac2b"),
    ("24/25", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1622112890281525248-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dfa809c42180cb8ceb35df56d71004f07b20c54c640b03ca139a155ccc8d66206"),
    ("23/24", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1474630979985342464-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D7ff1dd03cdd1f9fd967afeb4f246ac4867267e998979d45e6bd5ad0d351ec5e9"),
    ("22/23", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1365903978676617216-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D4ec39783640dd77f7487ce3a93eb34f3ea6c5d243a7e92c6867e09df84be0eba"),
    ("21/22", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1249131775530049536-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D919132deb8ada6bf6b3296ccb3e5e43fe07427479acd6941103791d17f4865d0"),
    ("20/21", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F1119828559886491648-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D21504680bbf2aa3802e62c4454b8bc27ff9b4b7a45ddc07f8f245ce337f58f86"),
    ("19/20", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F987943066685874176-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D08e31497b52c79abc968f50dde8c86dfe77fa797bd09a0a299efdaced2e0729b"),
    ("18/19", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2F896538323344990208-.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Dce655c9f44d6cece1fcbbbdcde6e7b6cc8a8eb45f6a757dd7d6966ca4b2fbc19"),
    ("17/18", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2FInforme%2520de%2520Colheita%2520de%2520Soja%2520-%2520Safra%252017%2F18.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D5858159b03be21d5cc9d680ad16302677f4cf10dd351a8767ebcbbbb1f472d82"),
    ("16/17", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2FInforme%2520de%2520Colheita%2520de%2520Soja%2520-%2520Safra%252016%2F17.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D754cb1f9ccf061ce2f7c3e520dee4a620a00a91de6ffce48058e5c2aa69c1cef"),
    ("15/16", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2FInforme%2520de%2520Colheita%2520de%2520Algod%25C3%25A3o%2520-%2520Safra%252015%2F16.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D7406a59998dfbffccf9a2ebe280c806f3ea0314c426c027904b26a18f7f22ccb"),
    ("14/15", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2Finforme%2520de%2520Colheita%2520de%2520Soja%2520-%2520Safra%252014%2F15.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3Ddcf2bed0faa425d706308d1065e5ef485379fdfc11b521cb3c18d0b9ef8a60ae"),
    ("13/14", "https://www.imea.com.br/imea-site/arquivo-externo?path=https%3A%2F%2Fbucket-xiruexterno-2.s3.sa-east-1.amazonaws.com%2F4%2F696277349624840192%2Finforme%2520de%2520Colheita%2520de%2520Soja%2520-%2520Safra%252013%2F14.pdf%3FX-Amz-Expires%3D432000%26X-Amz-Algorithm%3DAWS4-HMAC-SHA256%26X-Amz-Credential%3DAKIAIOZVUSV4HGV74RLA%2F20260929%2Fsa-east-1%2Fs3%2Faws4_request%26X-Amz-Date%3D20260929T233438Z%26X-Amz-SignedHeaders%3Dhost%26X-Amz-Signature%3D94c18fd4ec3ae6affecc9dc90ce91558f312d1298603e1a99e7cece1a56c54e4"),
]

ROW_RE = re.compile(
    r"(\d{1,2})[/-]([a-z]{3})[/-](\d{2})\s+([\d,]+)%\s+([\d,]+)%\s+([\d,]+)%\s+([\d,]+)%\s+"
    r"([\d,]+)%\s+([\d,]+)%\s+([\d,]+)%\s+([\d,]+)%", re.IGNORECASE)


def direct_s3_url(proxy_url):
    """IMEA's own arquivo-externo?path=<url-encoded S3 url> proxy returns an HTML
    viewer page (needs JS), not the raw PDF, over a plain urllib request -- the
    'path' query parameter it wraps is the actual signed S3 URL, so unwrap and
    fetch that directly instead."""
    q = urllib.parse.urlparse(proxy_url).query
    path = urllib.parse.parse_qs(q)["path"][0]
    return path


def fetch(url, out_path, tries=4):
    if out_path.exists():
        return
    url = direct_s3_url(url)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (research-script)",
                "Referer": "https://www.imea.com.br/"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            if not body.startswith(b"%PDF-"):
                raise ValueError("response is not a PDF")
            out_path.write_bytes(body)
            return
        except Exception as e:
            print(f"[br18]   retry {i+1}/{tries} for {out_path.name} ({e})")
            time.sleep(2)
    print(f"[br18]   FAILED to fetch {out_path.name} -- skipping")


def parse_pdf(path):
    """Returns list of dicts, one per date-row found (region: pct), plus the date."""
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"[br18]   could not open {path.name}: {e}")
        return []
    if "Algod" in text and "Soja" not in text.split("ACOMPANHAMENTO")[0]:
        print(f"[br18]   {path.name} is a cotton (Algodao) report, not soja -- skipping "
              f"(mislabeled on IMEA's own site)")
        return []
    rows = []
    for m in ROW_RE.finditer(text):
        d, mon, yy = m.group(1), m.group(2).lower(), m.group(3)
        if mon not in MONTHS:
            continue
        year = 2000 + int(yy)
        try:
            date = pd.Timestamp(year=year, month=MONTHS[mon], day=int(d))
        except ValueError:
            continue
        pcts = [float(m.group(i).replace(",", ".")) for i in range(4, 12)]
        rows.append(dict(date=date, **dict(zip(REGIONS + ["Mato Grosso"], pcts))))
    return rows


def download_all():
    print("[br18] downloading IMEA Semeadura/Colheita bulletins ...")
    for season, url in SEMEADURA:
        fetch(url, PDF_DIR / "semeadura" / f"{season.replace('/', '_')}.pdf")
    for season, url in COLHEITA:
        fetch(url, PDF_DIR / "colheita" / f"{season.replace('/', '_')}.pdf")


def kendall_w(rank_matrix):
    """rank_matrix: seasons x regions array of ranks (1=best/most advanced)."""
    n, k = rank_matrix.shape
    rank_sums = rank_matrix.sum(axis=0)
    mean_rs = rank_sums.mean()
    S = float(np.sum((rank_sums - mean_rs) ** 2))
    W = 12 * S / (n ** 2 * (k ** 3 - k))
    chi2 = n * (k - 1) * W
    from scipy.stats import chi2 as chi2_dist
    p = float(1 - chi2_dist.cdf(chi2, k - 1))
    return float(W), float(chi2), p


def main_season_cluster(rows):
    """Each PDF also carries a compact front-page comparison table with an
    isolated 'same week last year' row -- sometimes a full year before the
    real season, sometimes only 3-4 weeks before it (close enough in time to
    survive a loose gap threshold). The real season table is weekly (~7-day
    cadence); keep only the largest contiguous cluster with gaps <=15 days,
    tight enough to exclude an isolated stray row but loose enough to
    tolerate one skipped week."""
    rows = sorted(rows, key=lambda r: r["date"])
    clusters, cur = [], [rows[0]]
    for prev, r in zip(rows, rows[1:]):
        if (r["date"] - prev["date"]).days > 15:
            clusters.append(cur)
            cur = [r]
        else:
            cur.append(r)
    clusters.append(cur)
    return max(clusters, key=len)


def day50(dates, pcts):
    """Linear-interpolated day-of-series at which pct first reaches 50, in days
    from the series' first date. None if the series never reaches 50% (still
    in progress, as with the 2026/27 season captured only 2 weeks in)."""
    days = np.array([(d - dates[0]).days for d in dates], dtype=float)
    pcts = np.asarray(pcts, dtype=float)
    if pcts.max() < 50.0:
        return None
    i = int(np.searchsorted(pcts, 50.0))
    if i == 0:
        return float(days[0])
    x0, x1, y0, y1 = days[i - 1], days[i], pcts[i - 1], pcts[i]
    if y1 == y0:
        return float(x1)
    return float(x0 + (50.0 - y0) / (y1 - y0) * (x1 - x0))


def analyze(metric):
    d = PDF_DIR / metric
    seasons = SEMEADURA if metric == "semeadura" else COLHEITA
    ref_anchor = dict(semeadura=(9, 1), colheita=(2, 1))[metric]  # Sep1 / Feb1
    day50_rows, snapshot_rows = [], []
    for season, _ in seasons:
        f = d / f"{season.replace('/', '_')}.pdf"
        if not f.exists():
            continue
        rows = parse_pdf(f)
        if not rows:
            continue
        rows = main_season_cluster(rows)
        snap = dict(rows[-1]); snap["season"] = season
        snapshot_rows.append(snap)
        # anchor date: the ref_anchor month/day in the calendar year of the
        # MOST COMMON observation in this report (season start reference;
        # more robust than the first row alone if a stray outlier survives
        # clustering at a year boundary)
        y0 = pd.Series([r["date"].year for r in rows]).mode().iloc[0]
        anchor = pd.Timestamp(year=y0, month=ref_anchor[0], day=ref_anchor[1])
        dates = [r["date"] for r in rows]
        for region in REGIONS:
            pcts = [r[region] for r in rows]
            d50 = day50(dates, pcts)
            if d50 is not None:
                day50_rows.append(dict(season=season, region=region,
                                       day50_from_anchor=(dates[0] - anchor).days + d50))
    if not day50_rows:
        print(f"[br18] no usable {metric} reports parsed")
        return None
    P = pd.DataFrame(day50_rows)
    P.round(2).to_csv(RES / f"br24_imea_{metric}_day50.csv", index=False)
    if snapshot_rows:
        snap_df = pd.DataFrame(snapshot_rows)
        snap_df[REGIONS + ["Mato Grosso"]] = snap_df[REGIONS + ["Mato Grosso"]].round(2)
        snap_df.to_csv(RES / f"br24_imea_{metric}_latest_snapshot.csv", index=False)

    n_seasons = P.season.nunique()
    print(f"\n[br18] {metric.upper()}: {n_seasons} seasons with a usable 50%-complete date, "
          f"{len(P)} region-season observations")
    by_region = P.groupby("region").day50_from_anchor.agg(["mean", "std", "count"]) \
                 .sort_values("mean")
    anchor_lbl = "1-Sep" if metric == "semeadura" else "1-Feb"
    print(f"\n[br18] mean day of 50%-complete, days after {anchor_lbl} of the season "
          f"(lower = earlier):")
    print(by_region.round(2).to_string())

    # one-way ANOVA across regions on day50_from_anchor
    from scipy.stats import f_oneway
    groups = [g.day50_from_anchor.values for _, g in P.groupby("region") if len(g) >= 3]
    if len(groups) >= 2:
        F, p = f_oneway(*groups)
    else:
        F, p = np.nan, np.nan
    spread = by_region["mean"].max() - by_region["mean"].min()
    print(f"\n[br18] spread between earliest- and latest-{('planting' if metric=='semeadura' else 'harvest')} "
          f"region: {spread:.1f} days")
    print(f"[br18] one-way ANOVA across regions: F={F:.2f}, p={p:.4f}")
    print("[br18] " + (f"regions differ significantly in typical {anchor_lbl}-relative timing "
                       f"(p<0.05) -- the fixed calendar window in br_05/br_10 is a real "
                       f"simplification of a genuine regional gradient"
                       if not np.isnan(p) and p < .05 else
                       f"no significant evidence that regions differ in typical timing "
                       f"(p>=0.05) -- the fixed calendar window is not contradicted by this "
                       f"regional data"))

    # Kendall's W on the season-to-season RANK of day50 (robust check, no distributional
    # assumption): does the region that plants/harvests earliest stay consistent?
    piv = P.pivot(index="season", columns="region", values="day50_from_anchor")
    piv = piv.dropna(axis=0, how="any")
    W = chi2 = p_w = np.nan
    if len(piv) >= 3 and piv.shape[1] >= 3:
        ranks = piv.rank(axis=1, ascending=True)  # 1 = earliest
        W, chi2, p_w = kendall_w(ranks.values)
        print(f"\n[br18] Kendall's W on season-to-season earliness rank "
              f"({len(piv)} fully-observed seasons): W={W:.3f}, p={p_w:.4f}")

    return dict(metric=metric, n_seasons=int(n_seasons),
               mean_day50_by_region=by_region["mean"].round(2).to_dict(),
               spread_days=float(spread), anova_F=float(F) if not np.isnan(F) else None,
               anova_p=float(p) if not np.isnan(p) else None,
               kendall_w=float(W) if not np.isnan(W) else None,
               kendall_p=float(p_w) if not np.isnan(p_w) else None)


def main():
    download_all()
    results = [r for r in (analyze("semeadura"), analyze("colheita")) if r]
    if not results:
        return
    json.dump(dict(
        source="IMEA (Instituto Mato-grossense de Economia Agropecuaria), public PDF bulletins, "
               "scraped from https://www.imea.com.br/imea-site/relatorios-mercado",
        scope_limit="IMEA's own 7-region breakdown, coarser than IBGE's 5-mesorregiao grouping "
                   "(br_17) and far coarser than the 141-municipio panel; this does NOT "
                   "calibrate a municipio-level phenology model -- that gap remains open",
        method="Per season and region, linearly interpolate the calendar day the weekly "
              "progress curve first reaches 50% complete, expressed as days after 1-Sep "
              "(planting) or 1-Feb (harvest) of that season. One-way ANOVA across regions "
              "on this day50 metric, plus Kendall's W on the season-to-season earliness "
              "rank as a distribution-free check.",
        results=results),
        open(RES / "br25_imea_phenology_config.json", "w"), indent=2)

    # ---------- figure ----------------------------------------------------------
    f, axes = plt.subplots(1, len(results), figsize=(6.5 * len(results), 5.4), dpi=200)
    if len(results) == 1:
        axes = [axes]
    f.patch.set_facecolor(SURFACE)
    for ax, r in zip(axes, results):
        ax.set_facecolor(SURFACE)
        mr = pd.Series(r["mean_day50_by_region"]).sort_values()
        anchor_lbl = "1-Sep" if r["metric"] == "semeadura" else "1-Feb"
        ax.barh(range(len(mr)), mr.values, color=S1)
        ax.set_yticks(range(len(mr))); ax.set_yticklabels(mr.index, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlabel(f"Mean day of 50% complete, days after {anchor_lbl}", fontsize=9.5, color=INK2)
        p_str = f"{r['anova_p']:.3f}" if r["anova_p"] is not None else "n/a"
        ax.set_title(f"{r['metric'].capitalize()}  (n={r['n_seasons']} seasons, "
                    f"ANOVA p={p_str}, spread={r['spread_days']:.0f}d)", fontsize=10.5, color=INK)
        ax.grid(axis="x", color=GRID, lw=.7); ax.set_axisbelow(True)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle("Figure BR-22. Regional planting/harvest pace, IMEA's 7-region breakdown",
               fontsize=14, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
    f.text(.02, .965, "Does the same region consistently lead or lag, season after season? "
          "A test of the uniform-calendar-window assumption at IMEA's coarser regional "
          "resolution (see br_10/br_17 for the municipio-level gap this cannot close).",
          fontsize=9.6, color=INK2, va="bottom")
    f.tight_layout(rect=[0, 0, 1, .88])
    f.savefig(FIG / "fig_br22_imea_regional_timing.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n[br18] wrote br24 (semeadura/colheita snapshots), br25_imea_phenology_config.json, "
          "fig_br22")


if __name__ == "__main__":
    main()
