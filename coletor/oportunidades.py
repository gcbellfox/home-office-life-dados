"""Coletor de oportunidades REAIS de trabalho online para o Home Office Life.

Roda todo dia no GitHub Actions (ou à mão: python coletor/oportunidades.py). Só biblioteca padrão.
Gera oportunidades.json, que o jogo baixa.

Regras (documento do projeto, seções 6, 7, 29 e 31):
- só fontes com acesso aberto para aplicativos (APIs públicas); cada anúncio guarda fonte, link e data;
- mostra o nome da EMPRESA como está no anúncio público; nunca guarda dado pessoal
  (nome de cliente pessoa física, email, telefone, recrutador);
- o jogo NUNCA envia proposta real: o jogador vê o anúncio original e decide se tenta na vida real;
- se uma fonte falhar, mantém os anúncios anteriores dela (até 30 dias) e registra um aviso.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / 'oportunidades.json'
AGENTE = {'User-Agent': 'HomeOfficeLife-coletor/1.0 (jogo educativo; coleta diaria de anuncios publicos)'}
AGORA = dt.datetime.now(dt.timezone.utc)
HOJE = AGORA.date().isoformat()
DIAS_VALIDADE = 30

# ===== profissão de cada anúncio, pelas palavras do título (a ordem importa) =====
PALAVRAS = [
    ('video', ['video edit', 'vídeo', 'video', 'editor de v', 'youtube', 'reels', 'motion', 'after effects', 'premiere', 'capcut']),
    ('social', ['social media', 'redes sociais', 'instagram', 'tiktok', 'community manager', 'mídias sociais', 'social-media']),
    ('design', ['design', 'designer', 'logo', 'ui/ux', ' ui ', ' ux ', 'figma', 'identidade visual', 'gráfic', 'graphic', 'illustrat', 'ilustra']),
    ('redacao', ['copywrit', 'redator', 'redação', 'writer', 'writing', 'conteúdo', 'content', 'artigo', 'article', 'blog', 'tradu', 'translat', 'revis']),
    ('web', ['develop', 'desenvolvedor', 'programador', 'engineer', 'react', 'front', 'back-end', 'backend', 'full stack', 'fullstack',
             'wordpress', 'website', 'site', 'php', 'python', 'javascript', 'node', 'web']),
]


def profissao_de(titulo):
    t = f' {titulo.lower()} '
    for prof, palavras in PALAVRAS:
        if any(p in t for p in palavras):
            return prof
    return None


def nivel_de(texto):
    t = texto.lower()
    if any(p in t for p in ['sênior', 'senior', 'sr.', 'lead', 'líder', 'staff', 'principal', 'especialista', 'head']):
        return 3
    if any(p in t for p in ['júnior', 'junior', 'jr.', 'estágio', 'estagi', 'intern', 'trainee', 'entry', 'iniciante', 'assistant', 'assistente']):
        return 1
    return 2


def limpar(texto):
    """tira emails, telefones e links de um texto curto (título)"""
    texto = re.sub(r'\S+@\S+', '', texto)
    texto = re.sub(r'https?://\S+', '', texto)
    texto = re.sub(r'\+?\d[\d\s().-]{8,}\d', '', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def pegar(url, cabecalhos=None):
    req = urllib.request.Request(url, headers={**AGENTE, **(cabecalhos or {})})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


LOCAIS_OK = ['worldwide', 'anywhere', 'latam', 'latin america', 'south america', 'americas', 'brazil', 'brasil', 'global']


def aceita_brasil(local):
    l = (local or '').lower()
    return any(p in l for p in LOCAIS_OK)


# ===== cotação oficial (Banco Central, PTAX de fechamento) =====
def cotacoes():
    res = {'BRL': {'valor': 1.0}}
    ini = (AGORA - dt.timedelta(days=10)).strftime('%m-%d-%Y')
    fim = AGORA.strftime('%m-%d-%Y')
    for moeda in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
        url = ('https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,'
               f"dataFinalCotacao=@dataFinalCotacao)?@moeda='{moeda}'&@dataInicial='{ini}'&@dataFinalCotacao='{fim}'"
               "&$format=json&$orderby=dataHoraCotacao%20desc&$top=10")
        vals = [v for v in pegar(url.replace(' ', '%20'))['value'] if v['tipoBoletim'] == 'Fechamento']
        if vals:
            res[moeda] = {'valor': vals[0]['cotacaoVenda'], 'data': vals[0]['dataHoraCotacao'][:10]}
    return res


def em_reais(valor, moeda, cot):
    c = cot.get(moeda)
    return round(valor * c['valor'], 2) if c and valor is not None else None


# ===== fontes =====
def github_vagas():
    """Comunidades brasileiras que publicam vagas como issues no GitHub (tecnologia)."""
    token = os.environ.get('GITHUB_TOKEN')
    cab = {'Authorization': f'Bearer {token}'} if token else {}
    res = []
    for repo in ['frontendbr/vagas', 'backend-br/vagas', 'react-brasil/vagas']:
        for i in pegar(f'https://api.github.com/repos/{repo}/issues?state=open&per_page=40', cab):
            if 'pull_request' in i:
                continue
            titulo = limpar(i['title'])
            rotulos = [l['name'] for l in i.get('labels', [])]
            if not any(r.lower() in ('remoto', 'remote') for r in rotulos) and 'remoto' not in titulo.lower():
                continue                                       # o jogo é sobre trabalhar de casa
            m = re.search(r'\bna\s+([^|\[\]]+?)\s*(\||$)', titulo)
            res.append({
                'tipo': 'vaga', 'titulo': titulo, 'profissao': profissao_de(titulo) or 'web', 'nivel': nivel_de(titulo + ' ' + ' '.join(rotulos)),
                'empresa': m.group(1).strip() if m else None, 'contratacao': ', '.join(r for r in rotulos if r in ('CLT', 'PJ', 'Estágio')) or None,
                'plataforma': f'Vagas no GitHub ({repo})', 'fonte': f'Comunidade {repo} no GitHub', 'url': i['html_url'],
                'publicado': i['created_at'][:10], 'idioma': 'pt', 'local': 'Remoto (Brasil)', 'valor': None,
            })
    return res


def remotive():
    """Vagas remotas internacionais. A Remotive pede: mostrar o link original e citar a Remotive como fonte."""
    res = []
    for categoria in ['design', 'software-dev', 'writing', 'marketing', 'video']:
        dados = pegar(f'https://remotive.com/api/remote-jobs?category={categoria}&limit=60') if categoria != 'video' \
            else pegar('https://remotive.com/api/remote-jobs?search=video&limit=40')
        for j in dados.get('jobs', []):
            if not aceita_brasil(j.get('candidate_required_location')):
                continue
            titulo = limpar(j['title'])
            prof = profissao_de(titulo) or {'design': 'design', 'software-dev': 'web', 'writing': 'redacao', 'marketing': 'social'}.get(categoria)
            if not prof:
                continue
            res.append({
                'tipo': 'vaga', 'titulo': titulo, 'profissao': prof, 'nivel': nivel_de(titulo), 'empresa': limpar(j['company_name']),
                'contratacao': (j.get('job_type') or '').replace('_', ' ') or None, 'plataforma': 'Remotive', 'fonte': 'Remotive (remotive.com)',
                'url': j['url'], 'publicado': j['publication_date'][:10], 'idioma': 'en', 'local': j.get('candidate_required_location'),
                'valor': {'texto': j['salary']} if j.get('salary') else None,
            })
    return res


def jobicy():
    """Vagas remotas internacionais (Jobicy), com link para o anúncio original."""
    res = []
    for tag in ['design', 'video', 'copywriting', 'social-media', 'developer']:
        for j in pegar(f'https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}').get('jobs', []):
            if not aceita_brasil(j.get('jobGeo')):
                continue
            titulo = limpar(j['jobTitle'])
            prof = profissao_de(titulo)
            if not prof:
                continue
            sal = None
            if j.get('annualSalaryMin'):
                sal = {'texto': f"{j['annualSalaryMin']}–{j.get('annualSalaryMax') or ''} {j.get('salaryCurrency') or ''} por ano".strip()}
            res.append({
                'tipo': 'vaga', 'titulo': titulo, 'profissao': prof, 'nivel': nivel_de(titulo + ' ' + str(j.get('jobLevel'))),
                'empresa': limpar(j['companyName']), 'contratacao': ', '.join(j.get('jobType') or []) or None, 'plataforma': 'Jobicy',
                'fonte': 'Jobicy (jobicy.com)', 'url': j['url'], 'publicado': j['pubDate'][:10], 'idioma': 'en', 'local': j.get('jobGeo'), 'valor': sal,
            })
    return res


def freelancer(cot):
    """Projetos de freela com orçamento (Freelancer.com). Cliente é pessoa ou empresa: o nome NÃO é guardado."""
    # categorias de habilidade da própria plataforma (a busca por palavra não filtra direito)
    categorias = {
        'video': [688, 676, 52],          # Video Editing, Video Production, Video Services
        'design': [32, 20],               # Logo Design, Graphic Design
        'web': [17, 69],                  # Website Design, WordPress
        'redacao': [21, 174, 662],        # Copywriting, Article Writing, Content Writing
        'social': [1055, 663],            # Social Media Management, Social Media Marketing
    }
    res, vistos = [], set()
    for prof, ids in categorias.items():
        for idioma in ['pt', 'en', 'es']:
            q = urllib.parse.urlencode([('jobs[]', i) for i in ids] + [('languages[]', idioma), ('limit', 30), ('project_types[]', 'fixed')])
            for p in pegar(f'https://www.freelancer.com/api/projects/0.1/projects/active/?{q}')['result']['projects']:
                if p['id'] in vistos or p.get('type') != 'fixed' or p.get('nonpublic'):
                    continue
                vistos.add(p['id'])
                titulo = limpar(p['title'])
                moeda, b = p['currency']['code'], p.get('budget') or {}
                usd = p['currency'].get('exchange_rate')               # quanto 1 unidade da moeda vale em dólar (dado da plataforma)
                def reais(v):
                    if v is None:
                        return None
                    return em_reais(v, moeda, cot) if moeda in cot else (round(v * usd * cot['USD']['valor'], 2) if usd and 'USD' in cot else None)
                res.append({
                    'tipo': 'freela', 'titulo': titulo, 'profissao': prof, 'nivel': nivel_de(titulo),
                    'empresa': None, 'contratacao': 'Projeto com preço fechado', 'plataforma': 'Freelancer.com',
                    'fonte': 'Freelancer.com (API pública de projetos)', 'url': f"https://www.freelancer.com/projects/{p['seo_url']}",
                    'publicado': dt.datetime.fromtimestamp(p['time_submitted'], dt.timezone.utc).date().isoformat(),
                    'idioma': p.get('language') or '?', 'local': 'Remoto', 'propostas': (p.get('bid_stats') or {}).get('bid_count'),
                    'valor': {'min': b.get('minimum'), 'max': b.get('maximum'), 'moeda': moeda,
                              'brlMin': reais(b.get('minimum')), 'brlMax': reais(b.get('maximum'))},
                })
    return res


def main():
    anterior = json.loads(SAIDA.read_text(encoding='utf-8')) if SAIDA.exists() else {'oportunidades': [], 'cotacoes': {}}
    avisos = []
    try:
        cot = cotacoes()
    except Exception as erro:
        cot = anterior.get('cotacoes') or {'BRL': {'valor': 1.0}}
        avisos.append(f'cotação do Banco Central: falhou ({erro}); usada a anterior')
    novas, fontes_ok = [], set()
    for nome, funcao in [('GitHub', github_vagas), ('Remotive', remotive), ('Jobicy', jobicy), ('Freelancer.com', lambda: freelancer(cot))]:
        try:
            achadas = funcao()
            novas += achadas
            fontes_ok.add(nome)
            print(f'{nome}: {len(achadas)} anúncios')
        except Exception as erro:
            avisos.append(f'{nome}: falhou ({erro}); mantidos os anúncios anteriores')
            print('AVISO', avisos[-1], file=sys.stderr)
    # mantém os anúncios das fontes que falharam hoje
    for o in anterior.get('oportunidades', []):
        if not any(o['plataforma'].startswith(f) or (f == 'GitHub' and 'GitHub' in o['plataforma']) for f in fontes_ok):
            novas.append(o)
    limite = (AGORA.date() - dt.timedelta(days=DIAS_VALIDADE)).isoformat()
    unicos = {}
    repetidas = set()
    for o in novas:
        chave = (o['titulo'].lower(), (o.get('empresa') or '').lower()) if o['tipo'] == 'vaga' else None
        if chave and chave in repetidas:
            continue                                           # a mesma vaga publicada em duas comunidades
        if chave:
            repetidas.add(chave)
        if o['publicado'] >= limite and o['url'] not in unicos:
            o['id'] = re.sub(r'[^a-z0-9]+', '-', o['url'].lower())[-60:].strip('-')
            o['coletadoEm'] = o.get('coletadoEm') or HOJE
            unicos[o['url']] = o
    lista = sorted(unicos.values(), key=lambda o: o['publicado'], reverse=True)
    # no máximo 25 freelas e 25 vagas por profissão, para o arquivo ficar leve no celular
    por_prof, final = {}, []
    for o in lista:
        chave = f"{o['profissao']}/{o['tipo']}"
        por_prof[chave] = por_prof.get(chave, 0) + 1
        if por_prof[chave] <= 25:
            final.append(o)
    saida = {'versao': 1, 'geradoEm': HOJE, 'cotacoes': cot, 'oportunidades': final, 'avisos': avisos,
             'fontes': {'Remotive': 'Anúncios da Remotive: sempre mostrar o link original e citar a Remotive como fonte (pedido da própria Remotive).'}}
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'oportunidades.json: {len(final)} anúncios, {len(avisos)} aviso(s); por profissão: {por_prof}')


if __name__ == '__main__':
    main()
