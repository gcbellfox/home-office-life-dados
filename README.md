# Dados do Home Office Life

Custos de vida das 27 capitais brasileiras usados pelo jogo **Home Office Life**. O arquivo `custos.json` é atualizado sozinho uma vez por mês pelo GitHub Actions, e o jogo baixa ele pelo GitHub Pages.

## O que tem no arquivo
Para cada capital, cada dado guarda **fonte, link, mês de referência, data da coleta e tipo** (`oficial` = órgão ou pesquisa oficial; `observado` = preços anunciados).

| Dado | Fonte | Como é coletado |
|---|---|---|
| Aluguel (R$/m²) | Índice FipeZAP (FIPE e ZAP), preço médio anunciado de locação residencial; imóveis de 1 dormitório quando existe | Planilha pública da série histórica |
| Tarifa de energia (R$/kWh, sem impostos) | ANEEL, tarifas homologadas das distribuidoras (residencial B1 convencional, TUSD + TE) | Dados abertos da ANEEL (API) |
| Cesta básica (R$/mês) | Pesquisa Nacional da Cesta Básica DIEESE/Conab | **Manual** (`coletor/manuais.json`): só existe em PDF e página comum |

Capitais fora da pesquisa FipeZAP (Rio Branco, Macapá, Porto Velho, Boa Vista e Palmas) usam a média das cidades pesquisadas, e o arquivo marca isso.

## Regras
- Só usa fontes que permitem acesso automático. Não contorna bloqueios nem termos de uso.
- Se uma fonte falhar, mantém o último valor bom e registra um aviso em `avisos`. Nunca inventa números.
- O jogo calcula os custos mensais (por exemplo, aluguel = R$/m² × 30 m²) e mostra na tela que são **estimativas feitas a partir desses dados**.

## Rodar à mão
```
python coletor/coletar.py
```
Precisa só do Python 3, sem bibliotecas extras.
