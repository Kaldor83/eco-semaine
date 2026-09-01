#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import feedparser

NB_FAITS = 4
AGE_MAX_JOURS = 10
SORTIE = Path("actualites.json")

SOURCES = [
    {
        "nom": "INSEE",
        "zone": "France",
        "url": "https://www.insee.fr/fr/flux/1",
        "bonus": 5,
    },
    {
        "nom": "Eurostat",
        "zone": "zone euro / UE",
        "url": (
            "https://ec.europa.eu/eurostat/fr/news/euro-indicators"
            "?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK"
            "&p_p_lifecycle=2"
            "&p_p_state=normal"
            "&p_p_mode=view"
            "&p_p_resource_id=atom"
            "&p_p_cacheability=cacheLevelPage"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=25"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_sort=lastUpdateDate"
        ),
        "bonus": 4,
    },
    {
        "nom": "BCE",
        "zone": "zone euro",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "bonus": 2,
    },
    {
        "nom": "BCE",
        "zone": "zone euro",
        "url": "https://www.ecb.europa.eu/rss/statpress.html",
        "bonus": 3,
    },
]

NOTIONS = {
    "Croissance": {
        "priorite": 8,
        "mots": {"pib": 12, "gdp": 12, "croissance": 9, "economic growth": 9, "gross domestic product": 12},
        "unite": "activité et PIB",
        "explication": "Ce chiffre renseigne sur l’évolution de l’activité économique. La croissance mesure la variation de la production de biens et services.",
        "question": "Quels effets une variation de la croissance peut-elle avoir sur les entreprises et l’emploi ?",
    },
    "Inflation": {
        "priorite": 8,
        "mots": {"inflation": 12, "prix a la consommation": 10, "consumer prices": 10, "hicp": 8, "ipc": 8},
        "unite": "évolution générale des prix",
        "explication": "Ce taux renseigne sur le rythme d’évolution générale des prix. Il influence notamment le pouvoir d’achat et les coûts supportés par les entreprises.",
        "question": "Pourquoi une baisse de l’inflation ne signifie-t-elle pas nécessairement une baisse des prix ?",
    },
    "Emploi et chômage": {
        "priorite": 8,
        "mots": {"chomage": 12, "unemployment": 12, "taux de chomage": 14, "emploi": 7, "employment": 7, "jobless": 8},
        "unite": "marché du travail",
        "explication": "Ce chiffre renseigne sur la situation du marché du travail. L’emploi et le chômage influencent les revenus, la consommation et l’activité économique.",
        "question": "Par quels mécanismes une hausse du chômage peut-elle affecter la consommation ?",
    },
    "Consommation": {
        "priorite": 7,
        "mots": {"consommation": 11, "household consumption": 11, "depenses des menages": 10, "retail trade": 11, "commerce de detail": 11, "retail sales": 10},
        "unite": "consommation des ménages",
        "explication": "La consommation des ménages constitue une composante majeure de la demande. Son évolution peut soutenir ou freiner l’activité des entreprises.",
        "question": "Pourquoi une variation de la consommation peut-elle rapidement affecter la production ?",
    },
    "Investissement": {
        "priorite": 7,
        "mots": {"investissement": 12, "investment": 12, "formation brute de capital": 12, "gross fixed capital": 12, "capital formation": 12},
        "unite": "investissement",
        "explication": "L’investissement correspond à des dépenses destinées à accroître ou renouveler les capacités de production. Il joue un rôle important dans l’activité présente et la croissance future.",
        "question": "Pourquoi les entreprises peuvent-elles réduire leurs investissements lorsque l’incertitude augmente ?",
    },
    "Taux d’intérêt": {
        "priorite": 7,
        "mots": {"taux d'interet": 14, "taux d’intérêt": 14, "interest rate": 14, "interest rates": 14, "deposit facility": 10, "refinancing rate": 10, "monetary policy": 8, "politique monetaire": 8},
        "unite": "taux d’intérêt",
        "explication": "Les taux d’intérêt influencent le coût du crédit et la rémunération de l’épargne. Ils peuvent donc modifier les décisions de consommation et d’investissement.",
        "question": "Pourquoi une baisse des taux d’intérêt peut-elle encourager l’investissement ?",
    },
    "Finances publiques": {
        "priorite": 7,
        "mots": {"dette publique": 14, "public debt": 14, "government debt": 14, "deficit public": 14, "government deficit": 14, "public deficit": 14, "finances publiques": 10, "government finance": 10},
        "unite": "finances publiques",
        "explication": "Ce chiffre renseigne sur la situation financière des administrations publiques. Déficit et dette conditionnent notamment les marges de manœuvre de la politique budgétaire.",
        "question": "Pourquoi un déficit public peut-il augmenter même sans nouvelle dépense exceptionnelle ?",
    },
    "Commerce international": {
        "priorite": 6,
        "mots": {"exportations": 11, "exports": 11, "importations": 11, "imports": 11, "commerce exterieur": 12, "international trade": 12, "balance commerciale": 12, "trade balance": 12},
        "unite": "échanges internationaux",
        "explication": "Les exportations et les importations relient l’économie nationale au reste du monde. Leur évolution affecte l’activité des entreprises et la demande globale.",
        "question": "Comment une hausse des importations peut-elle avoir des effets à la fois positifs et négatifs ?",
    },
    "Production": {
        "priorite": 5,
        "mots": {"production industrielle": 12, "industrial production": 12, "services production": 10, "production de services": 10, "production in construction": 10, "production dans la construction": 10, "production": 5},
        "unite": "production",
        "explication": "La production mesure l’activité réalisée dans les différents secteurs de l’économie. Ses variations donnent une indication sur la conjoncture économique.",
        "question": "Pourquoi une baisse de la production peut-elle précéder une dégradation de l’emploi ?",
    },
    "Revenus et pouvoir d’achat": {
        "priorite": 5,
        "mots": {"pouvoir d'achat": 12, "pouvoir d’achat": 12, "purchasing power": 12, "revenu disponible": 11, "household income": 11, "real income": 11, "salaires": 8, "wages": 8},
        "unite": "revenus et pouvoir d’achat",
        "explication": "Les revenus déterminent en partie les possibilités de consommation et d’épargne des ménages. Le pouvoir d’achat tient également compte de l’évolution des prix.",
        "question": "Pourquoi une hausse du revenu nominal ne garantit-elle pas une hausse du pouvoir d’achat ?",
    },
    "Épargne": {
        "priorite": 4,
        "mots": {"epargne": 12, "épargne": 12, "saving rate": 12, "household saving": 12, "savings": 10},
        "unite": "épargne des ménages",
        "explication": "L’épargne correspond à la partie du revenu qui n’est pas consommée immédiatement. Son évolution dépend notamment des revenus, des taux d’intérêt et de l’incertitude.",
        "question": "Pourquoi une forte incertitude économique peut-elle pousser les ménages à davantage épargner ?",
    },
    "Énergie et matières premières": {
        "priorite": 4,
        "mots": {"energie": 9, "énergie": 9, "energy": 9, "petrole": 10, "pétrole": 10, "oil": 10, "gaz": 8, "gas": 8, "electricite": 8, "électricité": 8, "electricity": 8, "carburant": 8, "fuel": 8},
        "unite": "énergie et matières premières",
        "explication": "Les prix de l’énergie et des matières premières affectent directement les ménages et les coûts de production. Ils peuvent également se diffuser à l’ensemble des prix.",
        "question": "Pourquoi une hausse du prix de l’énergie peut-elle affecter des entreprises qui en consomment peu directement ?",
    },
}

MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

@dataclass
class Candidat:
    source: str
    zone: str
    titre_source: str
    resume_source: str
    url: str
    date: datetime
    notion: str
    score: int
    chiffre: str
    unite: str
    titre: str
    explication: str
    question: str

def sans_accents(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in texte if not unicodedata.combining(c))

def normaliser(texte: str) -> str:
    return sans_accents(html.unescape(texte or "")).lower()

def nettoyer_html(texte: str) -> str:
    texte = html.unescape(texte or "")
    texte = re.sub(r"<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()

def couper(texte: str, max_mots: int = 45) -> str:
    mots = texte.split()
    return texte if len(mots) <= max_mots else " ".join(mots[:max_mots]).rstrip(" ,;:") + "…"

def date_entree(entry) -> Optional[datetime]:
    for champ in ("published_parsed", "updated_parsed", "created_parsed"):
        valeur = getattr(entry, champ, None)
        if valeur:
            return datetime(*valeur[:6], tzinfo=timezone.utc)
    return None

def format_date_fr(dt: datetime) -> str:
    return f"{dt.day} {MOIS_FR[dt.month]} {dt.year}"

def periode_semaine(now: datetime) -> str:
    local = now.astimezone()
    lundi = local - timedelta(days=local.weekday())
    dimanche = lundi + timedelta(days=6)
    if lundi.month == dimanche.month:
        return f"Semaine du {lundi.day} au {dimanche.day} {MOIS_FR[dimanche.month]} {dimanche.year}"
    return f"Semaine du {lundi.day} {MOIS_FR[lundi.month]} au {dimanche.day} {MOIS_FR[dimanche.month]} {dimanche.year}"

def classer(texte: str):
    t = normaliser(texte)
    scores = {}
    for notion, cfg in NOTIONS.items():
        total = 0
        for mot, poids in cfg["mots"].items():
            if normaliser(mot) in t:
                total += poids
        if total:
            scores[notion] = total + cfg["priorite"]
    if not scores:
        return None, 0
    notion = max(scores, key=scores.get)
    return notion, scores[notion]

def extraire_chiffre(texte: str) -> str:
    m = re.search(r"(?<!\d)([+\-−]?\s*\d+(?:[.,]\d+)?)\s*%", texte)
    if m:
        valeur = re.sub(r"\s+", "", m.group(1).replace("−", "-").replace(".", ","))
        return f"{valeur} %"
    m = re.search(r"(?<!\d)([+\-−]?\s*\d+(?:[.,]\d+)?)\s*(milliards?|millions?)\s*(?:d['’ ]?euros?|€)?", texte, flags=re.I)
    if m:
        valeur = re.sub(r"\s+", "", m.group(1).replace("−", "-").replace(".", ","))
        return f"{valeur} {m.group(2).lower()}"
    return ""

def direction(texte: str) -> str:
    t = normaliser(texte)
    hausse = ["augmente", "hausse", "progresse", "progression", "up by", "increased", "increase", "grew", "rises", "rose", "higher"]
    baisse = ["diminue", "baisse", "recule", "recul", "down by", "decreased", "decrease", "fell", "falls", "lower", "decline"]
    if any(x in t for x in hausse):
        return "hausse"
    if any(x in t for x in baisse):
        return "baisse"
    return "stable"

def titre_francais(source: str, titre: str, notion: str, chiffre: str, zone: str) -> str:
    if source == "INSEE":
        return couper(titre, 16)
    d = direction(titre)
    verbe = {"hausse": "progresse", "baisse": "recule", "stable": "évolue"}[d]
    if notion == "Croissance":
        return f"Le PIB {verbe} dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Inflation":
        return (f"L’inflation ralentit dans la {zone}" if d == "baisse" else f"L’inflation évolue dans la {zone}") + (f" : {chiffre}" if chiffre else "")
    if notion == "Emploi et chômage":
        return f"Le chômage dans la {zone}" + (f" s’établit à {chiffre}" if chiffre else " évolue")
    if notion == "Consommation":
        return f"La consommation {verbe} dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Production":
        return f"La production {verbe} dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Finances publiques":
        return f"Les finances publiques de la {zone} évoluent" + (f" : {chiffre}" if chiffre else "")
    if notion == "Taux d’intérêt":
        return f"Les taux d’intérêt de la {zone} évoluent" + (f" : {chiffre}" if chiffre else "")
    if notion == "Commerce international":
        return f"Les échanges internationaux {verbe}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Investissement":
        return f"L’investissement {verbe} dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Revenus et pouvoir d’achat":
        return f"Les revenus et le pouvoir d’achat évoluent dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    if notion == "Épargne":
        return f"L’épargne évolue dans la {zone}" + (f" : {chiffre}" if chiffre else "")
    return f"Un indicateur économique {verbe}" + (f" : {chiffre}" if chiffre else "")

def lire_source(cfg: dict, maintenant: datetime) -> list[Candidat]:
    flux = feedparser.parse(cfg["url"], request_headers={"User-Agent": "EcoSemaine/1.0", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    if getattr(flux, "bozo", False) and not flux.entries:
        print(f"[AVERTISSEMENT] Flux inaccessible : {cfg['nom']} — {getattr(flux, 'bozo_exception', '')}")
        return []
    candidats = []
    limite = maintenant - timedelta(days=AGE_MAX_JOURS)
    for entry in flux.entries:
        dt = date_entree(entry)
        if not dt or dt < limite:
            continue
        titre = nettoyer_html(getattr(entry, "title", ""))
        resume = nettoyer_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        url = getattr(entry, "link", "") or ""
        texte = f"{titre} {resume}"
        notion, score_notion = classer(texte)
        if not notion:
            continue
        chiffre = extraire_chiffre(texte)
        score = score_notion + cfg["bonus"] + (7 if chiffre else 0) + (2 if extraire_chiffre(titre) else 0)
        age = max(0, (maintenant - dt).days)
        score += max(0, 5 - age)
        if cfg["nom"] == "BCE" and notion not in {"Taux d’intérêt", "Inflation", "Emploi et chômage", "Croissance", "Finances publiques"}:
            score -= 5
        candidats.append(Candidat(
            source=cfg["nom"], zone=cfg["zone"], titre_source=titre, resume_source=resume,
            url=url, date=dt, notion=notion, score=score, chiffre=chiffre or "Repère",
            unite=f"{NOTIONS[notion]['unite']}, {cfg['zone']}",
            titre=titre_francais(cfg["nom"], titre, notion, chiffre, cfg["zone"]),
            explication=NOTIONS[notion]["explication"], question=NOTIONS[notion]["question"]
        ))
    print(f"[INFO] {cfg['nom']} : {len(candidats)} publication(s) pertinente(s)")
    return candidats

def selectionner(candidats: list[Candidat]) -> list[Candidat]:
    uniques = {}
    for c in candidats:
        cle = c.url or f"{c.source}:{c.titre_source}"
        if cle not in uniques or c.score > uniques[cle].score:
            uniques[cle] = c
    pool = sorted(uniques.values(), key=lambda c: (c.score, c.date), reverse=True)
    selection, notions, compte_source = [], set(), {}
    def ajouter(c):
        if c in selection or c.notion in notions or compte_source.get(c.source, 0) >= 2:
            return False
        selection.append(c); notions.add(c.notion); compte_source[c.source] = compte_source.get(c.source, 0) + 1
        return True
    for c in pool:
        if c.source == "INSEE" and ajouter(c):
            break
    for c in pool:
        if c.source in {"Eurostat", "BCE"} and ajouter(c):
            break
    for c in pool:
        if len(selection) >= NB_FAITS:
            break
        ajouter(c)
    if len(selection) < NB_FAITS:
        for c in pool:
            if len(selection) >= NB_FAITS:
                break
            if c in selection or compte_source.get(c.source, 0) >= 2:
                continue
            selection.append(c); compte_source[c.source] = compte_source.get(c.source, 0) + 1
    return selection[:NB_FAITS]

def produire_json(selection: list[Candidat], maintenant: datetime) -> dict:
    return {
        "periode": periode_semaine(maintenant),
        "publie": format_date_fr(maintenant.astimezone()),
        "sources": sorted({c.source for c in selection}),
        "faits": [{
            "chiffre": c.chiffre, "unite": c.unite, "titre": c.titre,
            "explication": c.explication, "notion": c.notion, "question": c.question,
            "source": c.source, "date": format_date_fr(c.date.astimezone()), "url": c.url,
        } for c in selection],
    }

def main():
    maintenant = datetime.now(timezone.utc)
    candidats = []
    for cfg in SOURCES:
        try:
            candidats.extend(lire_source(cfg, maintenant))
        except Exception as exc:
            print(f"[ERREUR] {cfg['nom']} : {exc}")
    selection = selectionner(candidats)
    if not selection:
        raise SystemExit("Aucune publication pertinente trouvée. actualites.json n'est pas remplacé.")
    SORTIE.write_text(json.dumps(produire_json(selection, maintenant), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {len(selection)} fait(s) écrits dans {SORTIE}")
    for i, c in enumerate(selection, 1):
        print(f"  {i}. [{c.notion}] {c.source} — {c.titre}")

if __name__ == "__main__":
    main()
