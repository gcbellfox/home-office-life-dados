# Dados do Home Office Life

Dados reais usados pelo jogo **Home Office Life**, atualizados sozinhos todo dia pelo GitHub Actions e publicados pelo GitHub Pages:
- `custos.json`: custos de vida das 27 capitais;
- `oportunidades.json`: anúncios reais de trabalho online (freelas e vagas remotas).

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

## Anúncios reais de trabalho (`oportunidades.json`)
| Fonte | O que traz | Observação |
|---|---|---|
| Comunidades de vagas no GitHub (frontendbr, backend-br, react-brasil) | Vagas remotas brasileiras de tecnologia | API pública do GitHub |
| Remotive | Vagas remotas internacionais abertas a quem está no Brasil ou na América Latina | A Remotive pede: mostrar o link original e citar a Remotive como fonte |
| Jobicy | Vagas remotas internacionais | Link para o anúncio original |
| Freelancer.com | Projetos de freela com orçamento | API pública de projetos; o nome do cliente não é guardado |
| Banco Central (PTAX) | Cotação oficial do dólar, euro e outras moedas | Converte os orçamentos para reais |

- Mostra o nome da **empresa** como está no anúncio público. **Nunca** guarda dados pessoais (nome de cliente pessoa física, email, telefone).
- O jogo **não envia proposta real** a ninguém. O jogador vê o anúncio original e decide se tenta na vida real.
- Plataformas cujos termos não permitem coleta automática (como Workana, 99Freelas e GetNinjas) **não são coletadas**: o jogo só indica os sites.
