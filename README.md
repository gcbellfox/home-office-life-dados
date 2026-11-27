# Dados do Home Office Life

Dados reais usados pelo jogo **Home Office Life**, atualizados sozinhos todo dia pelo GitHub Actions e publicados pelo GitHub Pages:
- `custos.json`: custos de vida das 27 capitais;
- `mercado.json`: ponto de partida real do mercado simulado (ações, FIIs, ETFs, Tesouro e indicadores).

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
python coletor/mercado.py
```
Precisa só do Python 3, sem bibliotecas extras.

## Mercado (`mercado.json`)
| Dado | Fonte | Como é coletado |
|---|---|---|
| Preços e histórico de 12 meses (ações, FIIs, ETFs) | B3, arquivos COTAHIST | Arquivos públicos diários e mensais |
| Dividendos e JCP das ações (últimos 12 meses, por data com) | B3, proventos em dinheiro das empresas listadas | Consulta pública por empresa |
| Rendimento dos FIIs | CVM, informe mensal dos fundos | Dados abertos da CVM |
| Selic, CDI e IPCA | Banco Central (SGS 432, 12 e 13522) | API pública |
| Títulos do Tesouro Direto | Tesouro Transparente | Planilha pública |

- Ativo sem dado real de proventos fica **sem dado** (o jogo não compra). Nada é estimado.
- O Investidor10 não é coletado (os termos proíbem): o jogo só mostra o link da página do ativo.
