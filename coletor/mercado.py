"""Coleta os dados REAIS do mercado para o Home Office Life (simulador de investimentos).

Só fontes oficiais e abertas (nada de sites que proíbem a coleta, como o Investidor10):
- B3, séries históricas (COTAHIST): preço de fechamento diário de ações, FIIs e ETFs
  https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/series-historicas/
- Banco Central (SGS): Selic meta (432), CDI diário (12), IPCA 12 meses (13522)
- Tesouro Transparente: preços e taxas do Tesouro Direto (dados abertos)
- CVM, informe mensal dos FIIs: dividend yield do mês (dado oficial informado pelo fundo)

Resultado: mercado.json. Só usa Python padrão. Uso: python coletor/mercado.py
O jogo usa esses dados como PONTO DE PARTIDA: o mercado do jogo é simulado a partir deles.
"""
import csv
import datetime as dt
import io
import json
import math
import pathlib
import statistics
import urllib.request
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / 'mercado.json'
MANUAIS = pathlib.Path(__file__).resolve().parent / 'mercado_manuais.json'
B3 = 'https://bvmf.bmfbovespa.com.br/InstDados/SerHist/'
BCB = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados/ultimos/{}?formato=json'
TESOURO = ('https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/'
           '796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv')
CVM_FII = 'https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{}.zip'
AGENTE = {'User-Agent': 'home-office-life-coletor (simulador educativo)'}

# ativos do jogo (os mais negociados e conhecidos de cada tipo); quem não aparecer nos dados fica de fora
ACOES = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'BBAS3', 'ABEV3', 'WEGE3', 'ITSA4', 'TAEE11', 'EGIE3', 'B3SA3', 'BBSE3',
         'CMIG4', 'SANB11', 'VIVT3', 'PRIO3', 'RADL3', 'SUZB3', 'KLBN11', 'CXSE3', 'CPLE6', 'GGBR4', 'RENT3', 'FESA4', 'ISAE4']
FIIS = ['HGLG11', 'KNRI11', 'MXRF11', 'XPML11', 'VISC11', 'KNCR11', 'BTLG11', 'XPLG11', 'CPTS11', 'IRDM11', 'HGRU11',
        'KNIP11', 'RBRR11', 'TRXF11', 'VGIR11']
ETFS = ['BOVA11', 'IVVB11', 'SMAL11']
TIPO = {**{t: 'acao' for t in ACOES}, **{t: 'fii' for t in FIIS}, **{t: 'etf' for t in ETFS}}


def baixar(url, tentativas=3):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            print(f'  tentando de novo ({e})')


# ===== B3: preços de fechamento =====
def ler_cotahist(conteudo, precos, nomes):
    """lê um arquivo COTAHIST (zip) linha por linha e guarda só os ativos do jogo (mercado à vista)"""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        with z.open(z.namelist()[0]) as f:
            for bruta in f:
                linha = bruta.decode('latin-1')
                if not linha.startswith('01') or linha[24:27] != '010':
                    continue
                ticker = linha[12:24].strip()
                if ticker not in TIPO:
                    continue
                data = f'{linha[2:6]}-{linha[6:8]}-{linha[8:10]}'
                precos.setdefault(ticker, {})[data] = int(linha[108:121]) / 100
                nomes[ticker] = linha[27:39].strip()


def coletar_b3(hoje):
    precos, nomes = {}, {}
    # últimos 12 meses fechados (arquivos mensais) + dias do mês atual (arquivos diários)
    mes = dt.date(hoje.year, hoje.month, 1)
    meses = []
    for _ in range(12):
        mes = (mes - dt.timedelta(days=1)).replace(day=1)
        meses.append(mes)
    for m in reversed(meses):
        nome = f'COTAHIST_M{m.month:02d}{m.year}.ZIP'
        print(f'  B3 {nome}')
        try:
            ler_cotahist(baixar(B3 + nome), precos, nomes)
        except Exception as e:  # noqa: BLE001
            print(f'    não deu: {e}')
    d = dt.date(hoje.year, hoje.month, 1)
    while d <= hoje:
        if d.weekday() < 5:
            nome = f'COTAHIST_D{d.day:02d}{d.month:02d}{d.year}.ZIP'
            try:
                ler_cotahist(baixar(B3 + nome, 1), precos, nomes)
                print(f'  B3 {nome}')
            except Exception:  # noqa: BLE001
                pass                                      # feriado ou ainda não publicado
        d += dt.timedelta(days=1)
    return precos, nomes


def resumo_ativo(serie):
    """preço atual, volatilidade anual e retorno de 12 meses, a partir dos fechamentos diários"""
    datas = sorted(serie)
    valores = [serie[d] for d in datas]
    rets = [math.log(b / a) for a, b in zip(valores, valores[1:]) if a > 0 and b > 0]
    # saltos de mais de 40% num dia quase sempre são desdobramento/grupamento (o arquivo não ajusta): ficam de fora
    rets = [r for r in rets if abs(r) < 0.34]
    vol = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 20 else None
    semanal = [[d, serie[d]] for i, d in enumerate(datas) if i % 5 == 0 or i == len(datas) - 1]
    return {
        'preco': valores[-1], 'data': datas[-1],
        'volAnual': round(vol, 4) if vol else None,
        'retorno12m': round(math.exp(sum(rets)) - 1, 4) if rets else None,
        'historico': semanal,
    }


# ===== Banco Central =====
def serie_bcb(codigo, n=1):
    dados = json.loads(baixar(BCB.format(codigo, n)))
    return [(x['data'], float(x['valor'])) for x in dados]


def coletar_bcb():
    selic_data, selic = serie_bcb(432)[-1]
    cdi_data, cdi_dia = serie_bcb(12)[-1]
    ipca_data, ipca = serie_bcb(13522)[-1]
    fonte = 'Banco Central do Brasil, SGS'
    return {
        'selic': {'valor': selic / 100, 'unidade': 'ao ano', 'data': selic_data, 'fonte': f'{fonte} (série 432, meta Selic)', 'tipo': 'oficial'},
        'cdi': {'valor': round((1 + cdi_dia / 100) ** 252 - 1, 4), 'unidade': 'ao ano', 'data': cdi_data,
                'fonte': f'{fonte} (série 12, CDI diário, anualizado em 252 dias úteis)', 'tipo': 'oficial'},
        'ipca12m': {'valor': ipca / 100, 'unidade': '12 meses', 'data': ipca_data, 'fonte': f'{fonte} (série 13522)', 'tipo': 'oficial'},
    }


# ===== Tesouro Direto =====
def coletar_tesouro():
    texto = baixar(TESOURO).decode('latin-1')
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=';'))
    num = lambda s: float(s.replace('.', '').replace(',', '.')) if s else None  # noqa: E731
    data_iso = lambda s: '-'.join(reversed(s.split('/')))  # noqa: E731
    ultima = max(data_iso(x['Data Base']) for x in linhas)
    titulos = []
    for x in linhas:
        if data_iso(x['Data Base']) != ultima:
            continue
        nome = x['Tipo Titulo']
        if nome not in ('Tesouro Selic', 'Tesouro IPCA+', 'Tesouro Prefixado'):
            continue                                      # os outros pagam juros no meio do caminho: ficam para depois
        venc = data_iso(x['Data Vencimento'])
        if venc <= ultima:
            continue
        titulos.append({'titulo': f"{nome} {venc[:4]}", 'tipo': nome, 'vencimento': venc,
                        'taxa': num(x['Taxa Compra Manha']) / 100 if num(x['Taxa Compra Manha']) else None,
                        'pu': num(x['PU Compra Manha']) or num(x['PU Base Manha']), 'data': ultima})
    titulos = [t for t in titulos if t['pu']]
    titulos.sort(key=lambda t: (t['tipo'], t['vencimento']))
    return {'data': ultima, 'fonte': 'Tesouro Transparente, preços e taxas do Tesouro Direto', 'url': TESOURO, 'titulos': titulos}


# ===== CVM: dividend yield dos FIIs =====
def coletar_dy_fiis(ano):
    """média do dividend yield mensal informado à CVM nos últimos meses disponíveis, por ticker"""
    por_ticker = {}
    for a in (ano - 1, ano):
        try:
            z = zipfile.ZipFile(io.BytesIO(baixar(CVM_FII.format(a))))
        except Exception as e:  # noqa: BLE001
            print(f'  CVM {a}: não deu ({e})')
            continue
        ler = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), 'latin-1'), delimiter=';'))  # noqa: E731
        geral = next((n for n in z.namelist() if 'geral' in n), None)
        compl = next((n for n in z.namelist() if 'complemento' in n), None)
        if not geral or not compl:
            continue
        isin = {}
        for x in ler(geral):
            cod = (x.get('Codigo_ISIN') or '').strip()
            if len(cod) >= 6:
                isin[x['CNPJ_Fundo_Classe'] if 'CNPJ_Fundo_Classe' in x else x.get('CNPJ_Fundo')] = cod[2:6]
        for x in ler(compl):
            cnpj = x['CNPJ_Fundo_Classe'] if 'CNPJ_Fundo_Classe' in x else x.get('CNPJ_Fundo')
            raiz = isin.get(cnpj)
            dy = x.get('Percentual_Dividend_Yield_Mes', '').replace(',', '.')
            if not raiz or not dy:
                continue
            try:
                por_ticker.setdefault(raiz, []).append((x['Data_Referencia'], float(dy)))
            except ValueError:
                pass
    resultado = {}
    for t in FIIS:
        lista = sorted(por_ticker.get(t[:4], []))[-12:]
        # a CVM informa o rendimento do mês como fração (0,0076 = 0,76% no mês); tira valores absurdos
        lista = [v for _, v in lista if 0 < v < 0.05]
        if len(lista) >= 3:
            mensal = statistics.median(lista)
            resultado[t] = {'valor': round((1 + mensal) ** 12 - 1, 4), 'tipo': 'oficial', 'meses': len(lista),
                            'fonte': 'CVM, informe mensal dos FIIs (dividend yield do mês, mediana dos últimos meses)'}
    return resultado


def main():
    hoje = dt.date.today()
    manuais = json.loads(MANUAIS.read_text(encoding='utf-8')) if MANUAIS.exists() else {}
    print('B3...')
    precos, nomes = coletar_b3(hoje)
    print('Banco Central...')
    indicadores = coletar_bcb()
    print('Tesouro...')
    tesouro = coletar_tesouro()
    print('CVM (FIIs)...')
    dy_fii = coletar_dy_fiis(hoje.year)
    ativos = []
    for t in ACOES + FIIS + ETFS:
        if t not in precos or len(precos[t]) < 30:
            print(f'  sem dados suficientes: {t}')
            continue
        r = resumo_ativo(precos[t])
        info = manuais.get('ativos', {}).get(t, {})
        dy = dy_fii.get(t)
        if not dy and info.get('dy') is None and TIPO[t] == 'fii':
            info = {**info, 'dy': manuais.get('dyFiiPadrao', 0.10)}     # FII sem dado na CVM: estimativa
        if not dy and info.get('dy') is not None:
            dy = {'valor': info['dy'], 'tipo': 'estimativa', 'fonte': manuais.get('fonteDy', 'Estimativa do jogo')}
        ativos.append({'ticker': t, 'tipo': TIPO[t], 'nome': info.get('nome') or nomes.get(t, t), 'setor': info.get('setor'),
                       **r, 'dy': dy})
    saida = {
        'versao': 1, 'geradoEm': hoje.isoformat(),
        'aviso': 'Dados reais usados como ponto de partida de um mercado SIMULADO. Não é recomendação de investimento.',
        'fontes': {'b3': 'B3, séries históricas COTAHIST (fechamento diário, mercado à vista)'},
        'indicadores': indicadores, 'tesouro': tesouro, 'ativos': ativos,
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'ok: {len(ativos)} ativos, {len(tesouro["titulos"])} títulos do Tesouro -> {SAIDA.name}')


if __name__ == '__main__':
    main()
