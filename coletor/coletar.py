"""Coletor de custos de vida das capitais para o Home Office Life.

Roda sozinho uma vez por mês no GitHub Actions (ou à mão: python coletor/coletar.py).
Usa só a biblioteca padrão do Python. Gera o arquivo custos.json, que o jogo baixa.

Regras (documento do projeto, seções 6, 7 e 25):
- cada valor guarda fonte, URL, mês de referência, data da coleta e tipo (oficial, observado);
- só usa fontes que permitem acesso automático (planilhas e APIs públicas); não contorna bloqueios;
- se uma fonte falhar, mantém o último valor bom e registra um aviso: nunca inventa números.
"""
import datetime as dt
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / 'custos.json'
MANUAIS = RAIZ / 'coletor' / 'manuais.json'
AGENTE = {'User-Agent': 'HomeOfficeLife-coletor/1.0 (jogo educativo; coleta mensal de dados publicos)'}
HOJE = dt.date.today().isoformat()

# capital -> aba da planilha FipeZAP e sigla da distribuidora de energia nos dados abertos da ANEEL
CAPITAIS = {
    'Rio Branco/AC': (None, 'EAC'), 'Maceió/AL': ('Maceió', 'EQUATORIAL AL'), 'Macapá/AP': (None, 'CEA'),
    'Manaus/AM': ('Manaus', 'Âmbar Amazonas'), 'Salvador/BA': ('Salvador', 'COELBA'), 'Fortaleza/CE': ('Fortaleza', 'ENEL CE'),
    'Brasília/DF': ('Brasília', 'Neoenergia Brasília'), 'Vitória/ES': ('Vitória', 'EDP ES'), 'Goiânia/GO': ('Goiânia', 'EQUATORIAL GO'),
    'São Luís/MA': ('São Luís', 'EQUATORIAL MA'), 'Cuiabá/MT': ('Cuiabá', 'EMT'), 'Campo Grande/MS': ('Campo Grande', 'EMS'),
    'Belo Horizonte/MG': ('Belo Horizonte', 'CEMIG-D'), 'Belém/PA': ('Belém', 'EQUATORIAL PA'), 'João Pessoa/PB': ('João Pessoa', 'EPB'),
    'Curitiba/PR': ('Curitiba', 'COPEL-DIS'), 'Recife/PE': ('Recife', 'Neoenergia PE'), 'Teresina/PI': ('Teresina', 'EQUATORIAL PI'),
    'Rio de Janeiro/RJ': ('Rio de Janeiro', 'LIGHT SESA'), 'Natal/RN': ('Natal', 'COSERN'), 'Porto Alegre/RS': ('Porto Alegre', 'CEEE-D'),
    'Porto Velho/RO': (None, 'ERO'), 'Boa Vista/RR': (None, 'Âmbar Roraima'), 'Florianópolis/SC': ('Florianópolis', 'CELESC'),
    'São Paulo/SP': ('São Paulo', 'ELETROPAULO'), 'Aracaju/SE': ('Aracaju', 'ESE'), 'Palmas/TO': (None, 'ETO'),
}

URL_FIPEZAP = 'https://downloads.fipe.org.br/indices/fipezap/fipezap-serieshistoricas.xlsx'
URL_ANEEL = 'https://dadosabertos.aneel.gov.br/api/3/action/datastore_search'
RECURSO_ANEEL = 'fcf2906c-7c32-4b9b-a637-054e7a5234f4'   # tarifas homologadas das distribuidoras (CSV com consulta)
PAGINA_ANEEL = 'https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def baixar(url, tempo=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=AGENTE), timeout=tempo).read()


def numero(texto):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


# ===== FipeZAP: preço médio anunciado de locação residencial (R$/m²) =====
def ler_planilha(dados):
    z = zipfile.ZipFile(io.BytesIO(dados))
    textos = [''.join(t.text or '' for t in si.iter(NS + 't')) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si')]
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    abas = {s.get('name'): rels[s.get(NS_REL + 'id')] for s in ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets')}

    def linhas(nome):
        caminho = 'xl/' + abas[nome].replace('/xl/', '').lstrip('/')
        for row in ET.fromstring(z.read(caminho)).iter(NS + 'row'):
            cel = {}
            for c in row.findall(NS + 'c'):
                v = c.find(NS + 'v')
                if v is not None:
                    cel[re.match(r'[A-Z]+', c.get('r')).group(0)] = textos[int(v.text)] if c.get('t') == 's' else v.text
            yield cel
    return abas, linhas


def aluguel_da_aba(linhas, nome):
    """Último mês com preço de locação. Prefere imóveis de 1 dormitório (coluna AM); senão o total (AL)."""
    ultimo = None
    for cel in linhas(nome):
        data = numero(cel.get('B'))
        if data is None:
            continue
        um, total = numero(cel.get('AM')), numero(cel.get('AL'))
        if um or total:
            mes = (dt.date(1899, 12, 30) + dt.timedelta(days=int(data))).strftime('%Y-%m')
            ultimo = {'valor': round(um or total, 2), 'dormitorios': '1 dormitório' if um else 'todos os tamanhos', 'referencia': mes}
    return ultimo


def coletar_aluguel():
    abas, linhas = ler_planilha(baixar(URL_FIPEZAP, 180))
    media = aluguel_da_aba(linhas, next(n for n in abas if n.startswith('Índice FipeZAP')))
    base = {'fonte': 'Índice FipeZAP (FIPE e ZAP), preço médio anunciado de locação residencial',
            'url': URL_FIPEZAP, 'tipo': 'observado', 'coletadoEm': HOJE, 'unidade': 'R$/m²'}
    res = {}
    for capital, (aba, _) in CAPITAIS.items():
        if aba and aba in abas:
            dado = aluguel_da_aba(linhas, aba)
            if dado:
                res[capital] = {**base, **dado}
                continue
        res[capital] = {**base, **media, 'mediaNacional': True,
                        'nota': 'Cidade fora da pesquisa FipeZAP: usa a média das cidades pesquisadas'}
    return res


# ===== ANEEL: tarifa residencial convencional (B1), sem impostos =====
def coletar_energia():
    filtros = {'DscBaseTarifaria': 'Tarifa de Aplicação', 'DscSubGrupo': 'B1', 'DscModalidadeTarifaria': 'Convencional',
               'DscClasse': 'Residencial', 'DscSubClasse': 'Residencial', 'DscDetalhe': 'Não se aplica'}
    q = urllib.parse.urlencode({'resource_id': RECURSO_ANEEL, 'filters': json.dumps(filtros, ensure_ascii=False), 'limit': 10000,
                                'fields': 'SigAgente,DatInicioVigencia,DatFimVigencia,VlrTUSD,VlrTE,DscREH'})
    registros = json.loads(baixar(URL_ANEEL + '?' + q))['result']['records']
    res = {}
    for capital, (_, agente) in CAPITAIS.items():
        dele = [r for r in registros if r['SigAgente'] == agente and r['DatInicioVigencia'] <= HOJE]
        if not dele:
            continue
        r = max(dele, key=lambda x: x['DatInicioVigencia'])          # a tarifa mais recente já em vigor
        mwh = numero(r['VlrTUSD'].replace(',', '.')) + numero(r['VlrTE'].replace(',', '.') or '0')
        res[capital] = {
            'valor': round(mwh / 1000, 5), 'unidade': 'R$/kWh sem impostos', 'distribuidora': agente,
            'referencia': r['DatInicioVigencia'][:7], 'vigencia': [r['DatInicioVigencia'], r['DatFimVigencia']], 'ato': r['DscREH'],
            'fonte': 'ANEEL, dados abertos: tarifas homologadas das distribuidoras (TUSD + TE, residencial B1 convencional)',
            'url': PAGINA_ANEEL, 'tipo': 'oficial', 'coletadoEm': HOJE,
        }
    return res


def main():
    anterior = json.loads(SAIDA.read_text(encoding='utf-8')) if SAIDA.exists() else {'capitais': {}}
    manuais = json.loads(MANUAIS.read_text(encoding='utf-8'))
    avisos, coletas = [], {}
    for nome, funcao in (('aluguelM2', coletar_aluguel), ('tarifaEnergia', coletar_energia)):
        try:
            coletas[nome] = funcao()
            print(f'{nome}: {len(coletas[nome])} capitais')
        except Exception as erro:                                     # fonte fora do ar: mantém o último valor bom
            coletas[nome] = {}
            avisos.append(f'{nome}: falhou ({erro}); mantidos os valores anteriores')
            print('AVISO', avisos[-1], file=sys.stderr)
    capitais = {}
    for capital in CAPITAIS:
        velho = anterior['capitais'].get(capital, {})
        item = {}
        for nome in ('aluguelM2', 'tarifaEnergia'):
            novo = coletas[nome].get(capital) or velho.get(nome)
            if novo:
                item[nome] = novo
            else:
                avisos.append(f'{capital}: sem {nome}')
        cesta = manuais['cestaBasica']['valores'].get(capital)
        if cesta:
            m = manuais['cestaBasica']
            item['cestaBasica'] = {'valor': cesta, 'unidade': 'R$ por mês', 'referencia': m['referencia'], 'fonte': m['fonte'],
                                   'url': m['url'], 'tipo': 'oficial', 'coletadoEm': m['coletadoEm'], 'coletaManual': True}
        capitais[capital] = item
    saida = {'versao': 1, 'geradoEm': HOJE, 'capitais': capitais, 'avisos': avisos}
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'custos.json gerado com {len(capitais)} capitais e {len(avisos)} aviso(s)')


if __name__ == '__main__':
    main()
