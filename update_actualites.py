#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import html,json,re,unicodedata
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Optional
import feedparser
SORTIE=Path('actualites.json'); AGE_MAX_JOURS=10; NB_REPERES_MAX=3; NB_BREVES=3
SOURCES_REPERES=[
 {'nom':'INSEE','url':'https://www.insee.fr/fr/flux/1','bonus':7},
 {'nom':'Eurostat','url':'https://ec.europa.eu/eurostat/fr/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=atom&p_p_cacheability=cacheLevelPage&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=25&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_sort=lastUpdateDate','bonus':5}
]
SOURCES_BREVES=[
 {'nom':'Ministère de l’Économie','url':'https://www.economie.gouv.fr/rss/toutesactualites','bonus':8},
 {'nom':'DG Trésor','url':'https://www.tresor.economie.gouv.fr/Flux/Atom/Articles/Home','bonus':6},
 {'nom':'BCE','url':'https://www.ecb.europa.eu/rss/press.html','bonus':3}
]
NOTIONS={
 'Croissance':(['pib','gdp','croissance','economic growth','gross domestic product'],9,'La croissance mesure l’évolution de la production de biens et services. Ce repère permet de situer le rythme de l’activité économique.','Que peut provoquer une croissance durablement faible pour les entreprises et l’emploi ?'),
 'Inflation':(['inflation','prix a la consommation','consumer prices','hicp','ipc'],9,'L’inflation mesure l’évolution générale des prix. Son rythme influence notamment le pouvoir d’achat et les coûts des entreprises.','Pourquoi un ralentissement de l’inflation ne signifie-t-il pas que les prix baissent ?'),
 'Emploi et chômage':(['chomage','unemployment','emploi','employment','jobless'],9,'L’emploi et le chômage renseignent sur la situation du marché du travail. Ils influencent les revenus, la consommation et l’activité.','Comment une hausse du chômage peut-elle affecter la consommation ?'),
 'Consommation':(['consommation','depenses des menages','household consumption','retail sales','retail trade','commerce de detail'],8,'La consommation des ménages constitue une composante majeure de la demande. Son évolution peut soutenir ou freiner l’activité.','Pourquoi une baisse de la consommation peut-elle rapidement affecter les entreprises ?'),
 'Investissement':(['investissement','investment','capital formation','formation brute de capital'],8,'L’investissement permet d’accroître ou de renouveler les capacités de production. Il joue sur l’activité présente et la croissance future.','Pourquoi l’incertitude peut-elle freiner l’investissement des entreprises ?'),
 'Taux d’intérêt':(["taux d'interet",'interest rate','interest rates','politique monetaire','monetary policy','bce','ecb'],8,'Les taux d’intérêt influencent le coût du crédit. Ils peuvent modifier les décisions de consommation et d’investissement.','Pourquoi une baisse des taux peut-elle encourager l’investissement ?'),
 'Pouvoir d’achat':(["pouvoir d'achat",'purchasing power','revenu disponible','household income','salaires','wages'],7,'Le pouvoir d’achat dépend des revenus mais aussi de l’évolution des prix. Il conditionne en partie la consommation des ménages.','Pourquoi une hausse du salaire nominal ne garantit-elle pas une hausse du pouvoir d’achat ?'),
 'Finances publiques':(['dette publique','public debt','government debt','deficit public','government deficit','budget','finances publiques'],7,'Déficit et dette renseignent sur la situation des administrations publiques et sur leurs marges de manœuvre budgétaires.','Pourquoi les finances publiques peuvent-elles se dégrader lorsque l’activité ralentit ?'),
 'Commerce international':(['exportations','exports','importations','imports','commerce exterieur','international trade','trade','droits de douane','tariffs'],7,'Les échanges internationaux relient l’économie nationale au reste du monde. Ils influencent la production, les prix et les entreprises.','Comment une modification des échanges internationaux peut-elle affecter les entreprises françaises ?'),
 'Production':(['production industrielle','industrial production','production','industrie','industry','usine','factory'],6,'La production renseigne sur l’activité réalisée dans les différents secteurs. Ses variations donnent une indication sur la conjoncture.','Pourquoi une baisse de la production peut-elle ensuite affecter l’emploi ?'),
 'Énergie':(['energie','energy','petrole','oil','gaz','gas','electricite','electricity'],5,'L’énergie affecte les dépenses des ménages et les coûts de production. Ses variations peuvent se diffuser au reste de l’économie.','Comment une hausse du coût de l’énergie peut-elle se transmettre aux prix ?'),
 'Entreprises':(['entreprise','entreprises','company','companies','pme','industrie','industrial','site de production','investissement industriel'],5,'Les décisions des entreprises traduisent concrètement les évolutions de la demande, des coûts, de l’investissement et de l’emploi.','Quel lien peut-on faire entre cette décision et la conjoncture économique ?')
}
EXCLUSIONS=['nomination','recrutement','concours','agenda','colloque','webinaire','seminaire','appel a candidatures','marches publics','bulletin officiel','organisation du ministere']
MOIS=['','janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
@dataclass
class Item: source:str; titre:str; resume:str; url:str; date:datetime; notion:str; score:int; chiffre:str=''; zone:str=''
def na(s):
 s=unicodedata.normalize('NFKD',s or ''); return ''.join(c for c in s if not unicodedata.combining(c))
def norm(s): return na(html.unescape(s or '')).lower()
def clean(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(s or ''))).strip()
def dt_entry(e)->Optional[datetime]:
 for k in ('published_parsed','updated_parsed','created_parsed'):
  v=getattr(e,k,None)
  if v:return datetime(*v[:6],tzinfo=timezone.utc)
 return None
def date_fr(d): return f'{d.day} {MOIS[d.month]} {d.year}'
def periode(now):
 d=now.astimezone(); l=d-timedelta(days=d.weekday()); di=l+timedelta(days=6)
 return f'Semaine du {l.day} au {di.day} {MOIS[di.month]} {di.year}' if l.month==di.month else f'Semaine du {l.day} {MOIS[l.month]} au {di.day} {MOIS[di.month]} {di.year}'
def classer(txt):
 t=norm(txt); scores={}
 for n,(mots,p,_,_) in NOTIONS.items():
  s=sum(5 for m in mots if norm(m) in t)
  if s:scores[n]=s+p
 return (max(scores,key=scores.get),max(scores.values())) if scores else (None,0)
def pct(titre):
 m=re.search(r'(?<!\d)([+\-−]?\s*\d+(?:[.,]\d+)?)\s*%',titre)
 return (re.sub(r'\s+','',m.group(1)).replace('−','-').replace('.',',')+' %') if m else ''
def zone(txt,source):
 t=norm(txt)
 if source=='INSEE' or 'france' in t:return 'France'
 if 'euro area' in t or 'zone euro' in t:return 'zone euro'
 if 'european union' in t or re.search(r'\beu\b',t):return 'Union européenne'
 return 'Europe'
def titre_rep(x):
 z,c=x.zone,x.chiffre
 return {'Croissance':f'Le PIB évolue en {z} : {c}','Inflation':f'L’inflation s’établit à {c} en {z}','Emploi et chômage':f'Le chômage s’établit à {c} en {z}','Consommation':f'La consommation évolue de {c} en {z}','Production':f'La production évolue de {c} en {z}','Finances publiques':f'Un indicateur de finances publiques atteint {c} en {z}'}.get(x.notion,x.titre)
def unite(x): return f"{ {'Croissance':'variation du PIB','Inflation':'inflation','Emploi et chômage':'taux de chômage','Consommation':'évolution de la consommation','Production':'évolution de la production','Finances publiques':'finances publiques'}.get(x.notion,x.notion.lower())}, {x.zone}"
def feed(cfg):
 f=feedparser.parse(cfg['url'],request_headers={'User-Agent':'EcoSemaine/2.0','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'})
 if getattr(f,'bozo',False) and not f.entries: print('[WARN]',cfg['nom'],getattr(f,'bozo_exception','')); return []
 return f.entries
def reperes(now):
 out=[]; lim=now-timedelta(days=AGE_MAX_JOURS); admis={'Croissance','Inflation','Emploi et chômage','Consommation','Production','Finances publiques'}
 for cfg in SOURCES_REPERES:
  for e in feed(cfg):
   d=dt_entry(e); titre=clean(getattr(e,'title',''))
   if not d or d<lim:continue
   n,s=classer(titre); c=pct(titre)
   if n not in admis or not c:continue
   out.append(Item(cfg['nom'],titre,'',getattr(e,'link','') or '',d,n,s+cfg['bonus']+max(0,5-(now-d).days),c,zone(titre,cfg['nom'])))
 out.sort(key=lambda x:(x.score,x.date),reverse=True); ch=[]; ns=set(); ss={}
 for x in out:
  if x.notion in ns or ss.get(x.source,0)>=2:continue
  ch.append(x);ns.add(x.notion);ss[x.source]=ss.get(x.source,0)+1
  if len(ch)>=NB_REPERES_MAX:break
 return ch
def resumer(txt,maxm=42):
 txt=clean(txt)
 if not txt:return ''
 phrases=re.split(r'(?<=[.!?])\s+',txt); out=''
 for p in phrases:
  test=(out+' '+p).strip()
  if len(test.split())>maxm:break
  out=test
  if len(out.split())>=18:break
 if out:return out
 m=txt.split(); return ' '.join(m[:maxm])+('…' if len(m)>maxm else '')
def breves(now):
 out=[];lim=now-timedelta(days=AGE_MAX_JOURS)
 for cfg in SOURCES_BREVES:
  for e in feed(cfg):
   d=dt_entry(e)
   if not d or d<lim:continue
   t=clean(getattr(e,'title','')); r=clean(getattr(e,'summary','') or getattr(e,'description','')); bloc=t+' '+r; nb=norm(bloc)
   if any(norm(x) in nb for x in EXCLUSIONS) or len(t)<20:continue
   n,s=classer(bloc)
   if not n:continue
   bonus=sum(2 for m in ['annonce','accord','decision','investit','investissement','ouvre','ferme','fermeture','hausse','baisse','reforme','tarif','droits de douane','industrie','emploi','entreprise','budget','export'] if norm(m) in nb)
   out.append(Item(cfg['nom'],t,resumer(r),getattr(e,'link','') or '',d,n,s+cfg['bonus']+max(0,5-(now-d).days)+bonus))
 out.sort(key=lambda x:(x.score,x.date),reverse=True); ch=[];urls=set();ns={};ss={}
 for x in out:
  if x.url in urls or ns.get(x.notion,0)>=1 or ss.get(x.source,0)>=2:continue
  ch.append(x);urls.add(x.url);ns[x.notion]=1;ss[x.source]=ss.get(x.source,0)+1
  if len(ch)>=NB_BREVES:return ch
 for x in out:
  if x in ch or x.url in urls or ss.get(x.source,0)>=2:continue
  ch.append(x);urls.add(x.url);ss[x.source]=ss.get(x.source,0)+1
  if len(ch)>=NB_BREVES:break
 return ch
def main():
 now=datetime.now(timezone.utc); rs=reperes(now); bs=breves(now)
 if not rs and not bs:raise SystemExit("Aucune information exploitable : actualites.json n'est pas remplacé.")
 doc={'periode':periode(now),'publie':date_fr(now.astimezone()),'sources':sorted({x.source for x in rs+bs}),
 'reperes':[{'chiffre':x.chiffre,'unite':unite(x),'titre':titre_rep(x),'explication':NOTIONS[x.notion][2],'notion':x.notion,'question':NOTIONS[x.notion][3],'source':x.source,'date':date_fr(x.date.astimezone()),'url':x.url} for x in rs],
 'breves':[{'titre':x.titre,'resume':x.resume,'notion':x.notion,'source':x.source,'date':date_fr(x.date.astimezone()),'url':x.url} for x in bs]}
 SORTIE.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(f'[OK] {len(rs)} repère(s), {len(bs)} brève(s)')
if __name__=='__main__':main()
