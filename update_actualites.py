#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L’ÉCO DE LA SEMAINE — V4
Objectifs :
- 2 à 3 repères chiffrés fiables, uniquement à partir de types de publications
  explicitement reconnus ;
- 3 brèves économiques à portée générale, sans obligation de chiffre ;
- élimination renforcée des contenus administratifs, trop techniques ou trop sectoriels ;
- zéro API payante, zéro IA.

Le script écrit actualites.json, consommé par index.html.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import feedparser


SORTIE = Path("actualites.json")
AGE_MAX_JOURS = 10
NB_REPERES_MAX = 3
NB_BREVES = 3
FUSEAU_PARIS = ZoneInfo("Europe/Paris")


# ---------------------------------------------------------------------------
# SOURCES
# ---------------------------------------------------------------------------

SOURCES_REPERES = [
    {
        "nom": "INSEE",
        "url": "https://www.insee.fr/fr/flux/1",
        "bonus": 8,
    },
    {
        "nom": "Eurostat",
        "url": (
            "https://ec.europa.eu/eurostat/fr/news/euro-indicators"
            "?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK"
            "&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view"
            "&p_p_resource_id=atom&p_p_cacheability=cacheLevelPage"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=25"
            "&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_sort=lastUpdateDate"
        ),
        "bonus": 6,
    },
]

SOURCES_BREVES = [
    {
        "nom": "Ministère de l’Économie",
        "url": "https://www.economie.gouv.fr/rss/toutesactualites",
        "bonus": 9,
    },
    {
        "nom": "DG Trésor",
        "url": "https://www.tresor.economie.gouv.fr/Flux/Atom/Articles/Home",
        "bonus": 8,
    },
    {
        "nom": "BCE",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "bonus": 3,
    },
]


# ---------------------------------------------------------------------------
# GRANDES NOTIONS DU COURS
# ---------------------------------------------------------------------------

NOTIONS = {
    "Croissance": {
        "mots": [
            "pib", "gdp", "croissance", "economic growth",
            "gross domestic product", "activité économique"
        ],
        "priorite": 10,
        "explication": (
            "La croissance mesure l’évolution de la production de biens et services. "
            "Ce repère permet de situer le rythme de l’activité économique."
        ),
        "question": (
            "Que peut provoquer une croissance durablement faible pour les entreprises et l’emploi ?"
        ),
    },
    "Inflation": {
        "mots": [
            "inflation", "prix a la consommation", "prix à la consommation",
            "consumer prices", "hicp", "ipc"
        ],
        "priorite": 10,
        "explication": (
            "L’inflation mesure l’évolution générale des prix. "
            "Son rythme influence notamment le pouvoir d’achat et les coûts des entreprises."
        ),
        "question": (
            "Pourquoi un ralentissement de l’inflation ne signifie-t-il pas que les prix baissent ?"
        ),
    },
    "Emploi et chômage": {
        "mots": [
            "chomage", "chômage", "unemployment", "emploi", "employment",
            "jobless", "marché du travail"
        ],
        "priorite": 10,
        "explication": (
            "L’emploi et le chômage renseignent sur la situation du marché du travail. "
            "Ils influencent les revenus, la consommation et l’activité."
        ),
        "question": (
            "Comment une hausse du chômage peut-elle affecter la consommation ?"
        ),
    },
    "Consommation": {
        "mots": [
            "consommation", "depenses des menages", "dépenses des ménages",
            "household consumption", "retail sales", "retail trade",
            "commerce de detail", "commerce de détail"
        ],
        "priorite": 9,
        "explication": (
            "La consommation des ménages constitue une composante majeure de la demande. "
            "Son évolution peut soutenir ou freiner l’activité."
        ),
        "question": (
            "Pourquoi une baisse de la consommation peut-elle rapidement affecter les entreprises ?"
        ),
    },
    "Investissement": {
        "mots": [
            "investissement", "investment", "capital formation",
            "formation brute de capital", "investit", "investir"
        ],
        "priorite": 9,
        "explication": (
            "L’investissement permet d’accroître ou de renouveler les capacités de production. "
            "Il joue sur l’activité présente et la croissance future."
        ),
        "question": (
            "Pourquoi l’incertitude peut-elle freiner l’investissement des entreprises ?"
        ),
    },
    "Taux d’intérêt": {
        "mots": [
            "taux d'interet", "taux d’intérêt", "interest rate", "interest rates",
            "politique monetaire", "politique monétaire", "monetary policy",
            "taux directeur"
        ],
        "priorite": 9,
        "explication": (
            "Les taux d’intérêt influencent le coût du crédit. "
            "Ils peuvent modifier les décisions de consommation et d’investissement."
        ),
        "question": (
            "Pourquoi une baisse des taux peut-elle encourager l’investissement ?"
        ),
    },
    "Pouvoir d’achat": {
        "mots": [
            "pouvoir d'achat", "pouvoir d’achat", "purchasing power",
            "revenu disponible", "household income", "salaires", "wages"
        ],
        "priorite": 8,
        "explication": (
            "Le pouvoir d’achat dépend des revenus mais aussi de l’évolution des prix. "
            "Il conditionne en partie la consommation des ménages."
        ),
        "question": (
            "Pourquoi une hausse du salaire nominal ne garantit-elle pas une hausse du pouvoir d’achat ?"
        ),
    },
    "Finances publiques": {
        "mots": [
            "dette publique", "public debt", "government debt",
            "deficit public", "déficit public", "government deficit",
            "budget", "finances publiques"
        ],
        "priorite": 8,
        "explication": (
            "Déficit et dette renseignent sur la situation des administrations publiques "
            "et sur leurs marges de manœuvre budgétaires."
        ),
        "question": (
            "Pourquoi les finances publiques peuvent-elles se dégrader lorsque l’activité ralentit ?"
        ),
    },
    "Commerce international": {
        "mots": [
            "exportations", "exports", "importations", "imports",
            "commerce exterieur", "commerce extérieur", "international trade",
            "trade", "droits de douane", "tariffs", "balance commerciale"
        ],
        "priorite": 8,
        "explication": (
            "Les échanges internationaux relient l’économie nationale au reste du monde. "
            "Ils influencent la production, les prix et les entreprises."
        ),
        "question": (
            "Comment une modification des échanges internationaux peut-elle affecter les entreprises françaises ?"
        ),
    },
    "Production": {
        "mots": [
            "production industrielle", "industrial production",
            "production manufacturiere", "production manufacturière",
            "manufacturing production"
        ],
        "priorite": 7,
        "explication": (
            "La production renseigne sur l’activité réalisée dans les différents secteurs. "
            "Ses variations donnent une indication sur la conjoncture."
        ),
        "question": (
            "Pourquoi une baisse de la production peut-elle ensuite affecter l’emploi ?"
        ),
    },
    "Productivité": {
        "mots": [
            "productivite", "productivité", "productivity",
            "productivite horaire", "productivité horaire",
            "productivity growth"
        ],
        "priorite": 8,
        "explication": (
            "La productivité mesure la quantité de richesse produite à partir des ressources mobilisées. "
            "Elle joue un rôle central dans la croissance à long terme et les niveaux de vie."
        ),
        "question": (
            "Pourquoi une progression plus faible de la productivité peut-elle freiner la croissance à long terme ?"
        ),
    },
    "Énergie": {
        "mots": [
            "energie", "énergie", "energy", "petrole", "pétrole", "oil",
            "gaz", "gas", "electricite", "électricité", "electricity"
        ],
        "priorite": 5,
        "explication": (
            "L’énergie affecte les dépenses des ménages et les coûts de production. "
            "Ses variations peuvent se diffuser au reste de l’économie."
        ),
        "question": (
            "Comment une hausse du coût de l’énergie peut-elle se transmettre aux prix ?"
        ),
    },
    "Entreprises": {
        "mots": [
            "entreprise", "entreprises", "company", "companies", "pme",
            "site industriel", "site de production", "investissement industriel",
            "fermeture d'usine", "fermeture d’usine", "ouverture d'usine",
            "ouverture d’usine"
        ],
        "priorite": 6,
        "explication": (
            "Les décisions des entreprises traduisent concrètement les évolutions "
            "de la demande, des coûts, de l’investissement et de l’emploi."
        ),
        "question": (
            "Quel lien peut-on faire entre cette décision et la conjoncture économique ?"
        ),
    },
}


# ---------------------------------------------------------------------------
# REPÈRES : LISTE BLANCHE STRICTE
# ---------------------------------------------------------------------------

# On ne retient un repère que si le titre correspond clairement à un type
# d'indicateur économique défini ici.
REPERES_AUTORISES = [
    {
        "notion": "Croissance",
        "obligatoires": ["pib", "gdp", "gross domestic product"],
        "interdits": ["prix", "price"],
        "libelle": "variation du PIB",
    },
    {
        "notion": "Inflation",
        "obligatoires": ["inflation", "prix a la consommation", "consumer prices", "hicp", "ipc"],
        "interdits": ["prix de production", "producer prices", "prix agricoles"],
        "libelle": "inflation",
    },
    {
        "notion": "Emploi et chômage",
        "obligatoires": ["chomage", "unemployment", "taux de chomage"],
        "interdits": [],
        "libelle": "taux de chômage",
    },
    {
        "notion": "Consommation",
        "obligatoires": [
            "consommation des menages", "household consumption",
            "retail trade", "retail sales", "commerce de detail"
        ],
        "interdits": ["prix"],
        "libelle": "évolution de la consommation",
    },
    {
        "notion": "Production",
        "obligatoires": [
            "production industrielle", "industrial production",
            "production manufacturiere", "manufacturing production"
        ],
        "interdits": [
            "prix de production", "producer prices", "production prices",
            "prix agricoles", "prix a la production", "prix à la production"
        ],
        "libelle": "évolution de la production",
    },
    {
        "notion": "Finances publiques",
        "obligatoires": [
            "deficit public", "government deficit", "dette publique",
            "government debt", "public debt"
        ],
        "interdits": [],
        "libelle": "finances publiques",
    },
]

# Éliminations supplémentaires, même si un mot-clé autorisé est présent.
EXCLUSIONS_REPERES = [
    "prix de production",
    "producer prices",
    "production prices",
    "prix agricoles",
    "agricultural prices",
    "indice du cout",
    "indice du coût",
    "cost index",
    "cout du travail",
    "coût du travail",
    "labour cost",
    "prix d'importation",
    "prix d’importation",
    "import prices",
    "prix d'exportation",
    "prix d’exportation",
    "export prices",
]


# ---------------------------------------------------------------------------
# BRÈVES : FILTRE ÉDITORIAL
# ---------------------------------------------------------------------------

EXCLUSIONS_BREVES = [
    # administratif
    "nomination", "nomme ", "nommée ", "recrutement", "concours",
    "agenda", "colloque", "webinaire", "seminaire", "séminaire",
    "appel a candidatures", "appel à candidatures",
    "appel a manifestation", "appel à manifestation",
    "marches publics", "marchés publics",
    "bulletin officiel",
    "organisation du ministere", "organisation du ministère",
    "consultation publique", "concertation publique",
    "procedure de selection", "procédure de sélection",
    "selection des organismes", "sélection des organismes",
    "organismes certificateurs", "organisme certificateur",
    "habilitation", "habilites a", "habilités à",
    "audit de second niveau", "audits de second niveau",
    "certification des organismes", "accreditation", "accréditation",
    "liste des operateurs", "liste des opérateurs",
    "avis de vacance", "avis de recrutement",

    # trop technique / réglementaire pour un bulletin L1
    "arrete du", "arrêté du", "decret du", "décret du",
    "instruction technique", "cahier des charges",
    "modalites de depot", "modalités de dépôt",
]

# Bonus pour des événements à portée générale et pédagogiquement exploitables.
EVENEMENTS_BONUS = {
    "reforme": 5, "réforme": 5,
    "entre en vigueur": 5,
    "entrée en vigueur": 5,
    "annonce": 4,
    "accord": 4,
    "adopte": 4,
    "adoption": 4,
    "decision": 4,
    "décision": 4,
    "investit": 5,
    "investissement": 4,
    "ouvre": 4,
    "ouverture": 4,
    "ferme": 5,
    "fermeture": 5,
    "emploi": 4,
    "licenciement": 5,
    "recrutement massif": 4,
    "budget": 4,
    "impot": 4,
    "impôt": 4,
    "droits de douane": 5,
    "tarifs douaniers": 5,
    "industrie": 3,
    "entreprise": 3,
    "productivite": 5,
    "productivité": 5,
    "numerique": 4,
    "numérique": 4,
    "intelligence artificielle": 4,
    "ia ": 3,
    "croissance": 4,
    "inflation": 4,
    "chomage": 4,
    "chômage": 4,
    "consommation": 4,
    "exportations": 4,
    "importations": 4,
    "energie": 3,
    "énergie": 3,
}

# Certains termes signalent des sujets très micro-sectoriels.
PENALITES_BREVES = {
    "biocarburants": -6,
    "certificateurs": -8,
    "certification": -5,
    "audit": -4,
    "norme technique": -5,
    "reglement delegue": -5,
    "règlement délégué": -5,
}


MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]


@dataclass
class Item:
    source: str
    titre: str
    resume: str
    url: str
    date: datetime
    notion: str
    score: int
    chiffre: str = ""
    zone: str = ""
    libelle: str = ""


# ---------------------------------------------------------------------------
# OUTILS TEXTE
# ---------------------------------------------------------------------------

def sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))


def norm(s: str) -> str:
    return sans_accents(html.unescape(s or "")).lower()


def nettoyer_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def date_entree(entry) -> Optional[datetime]:
    for champ in ("published_parsed", "updated_parsed", "created_parsed"):
        v = getattr(entry, champ, None)
        if v:
            return datetime(*v[:6], tzinfo=timezone.utc)
    return None


def date_fr(dt: datetime) -> str:
    d = dt.astimezone(FUSEAU_PARIS)
    return f"{d.day} {MOIS_FR[d.month]} {d.year}"


def periode(now: datetime) -> str:
    d = now.astimezone(FUSEAU_PARIS)
    lundi = d - timedelta(days=d.weekday())
    dimanche = lundi + timedelta(days=6)

    if lundi.month == dimanche.month:
        return (
            f"Semaine du {lundi.day} au {dimanche.day} "
            f"{MOIS_FR[dimanche.month]} {dimanche.year}"
        )

    return (
        f"Semaine du {lundi.day} {MOIS_FR[lundi.month]} "
        f"au {dimanche.day} {MOIS_FR[dimanche.month]} {dimanche.year}"
    )

def classer(texte: str):
    t = norm(texte)
    scores = {}

    for notion, cfg in NOTIONS.items():
        score = 0
        for mot in cfg["mots"]:
            if norm(mot) in t:
                score += 5

        if score:
            scores[notion] = score + cfg["priorite"]

    if not scores:
        return None, 0

    notion = max(scores, key=scores.get)
    return notion, scores[notion]


def premier_pourcentage(titre: str) -> str:
    # Repères : jamais de chiffre extrait du résumé.
    m = re.search(r"(?<!\d)([+\-−]?\s*\d+(?:[.,]\d+)?)\s*%", titre)
    if not m:
        return ""

    v = re.sub(r"\s+", "", m.group(1))
    v = v.replace("−", "-").replace(".", ",")
    return v + " %"


def valeur_pourcentage(chiffre: str) -> Optional[float]:
    if not chiffre:
        return None
    m = re.search(r"([+\-−]?\s*\d+(?:[.,]\d+)?)", chiffre)
    if not m:
        return None
    try:
        return float(
            m.group(1).replace("−", "-").replace(" ", "").replace(",", ".")
        )
    except ValueError:
        return None


def direction_depuis_titre(titre: str) -> str:
    """N'infère une direction que si le titre source la formule explicitement."""
    t = norm(titre)

    stable = [
        "stable", "unchanged", "remains at", "remain at",
        "reste stable", "est stable", "sans changement"
    ]
    hausse = [
        "up to", "up by", "increased", "increase", "rose", "rises",
        "higher", "grew", "augmente", "augmentation", "hausse",
        "progresse", "progression", "remonte", "accelere"
    ]
    baisse = [
        "down to", "down by", "decreased", "decrease", "fell", "falls",
        "lower", "decline", "declined", "diminue", "diminution",
        "baisse", "recule", "recul", "ralentit", "decelere"
    ]

    if any(m in t for m in stable):
        return "stable"
    if any(m in t for m in hausse):
        return "hausse"
    if any(m in t for m in baisse):
        return "baisse"
    return "neutre"


def detecter_zone(texte: str, source: str) -> str:
    t = norm(texte)

    if source == "INSEE" or "france" in t:
        return "France"

    if "euro area" in t or "zone euro" in t:
        return "zone euro"

    if (
        "european union" in t
        or "union europeenne" in t
        or "union européenne" in texte.lower()
    ):
        return "Union européenne"

    return "Europe"


def resume_breve(texte: str, max_mots: int = 42) -> str:
    texte = nettoyer_html(texte)
    if not texte:
        return ""

    phrases = re.split(r"(?<=[.!?])\s+", texte)

    sortie = ""
    for p in phrases:
        tentative = (sortie + " " + p).strip()
        if len(tentative.split()) > max_mots:
            break

        sortie = tentative

        if len(sortie.split()) >= 18:
            break

    if sortie:
        return sortie

    mots = texte.split()
    return " ".join(mots[:max_mots]) + ("…" if len(mots) > max_mots else "")


def lire_flux(cfg):
    f = feedparser.parse(
        cfg["url"],
        request_headers={
            "User-Agent": "EcoSemaine/3.0",
            "Accept": (
                "application/rss+xml, application/atom+xml, "
                "application/xml, text/xml, */*"
            ),
        },
    )

    if getattr(f, "bozo", False) and not f.entries:
        print(
            f"[AVERTISSEMENT] {cfg['nom']} inaccessible : "
            f"{getattr(f, 'bozo_exception', '')}"
        )
        return []

    return f.entries


# ---------------------------------------------------------------------------
# REPÈRES
# ---------------------------------------------------------------------------

def type_repere_autorise(titre: str):
    t = norm(titre)

    if any(norm(x) in t for x in EXCLUSIONS_REPERES):
        return None

    for regle in REPERES_AUTORISES:
        obligatoires = [norm(x) for x in regle["obligatoires"]]
        interdits = [norm(x) for x in regle["interdits"]]

        if not any(x in t for x in obligatoires):
            continue

        if any(x in t for x in interdits):
            continue

        return regle

    return None


def candidats_reperes(now: datetime):
    limite = now - timedelta(days=AGE_MAX_JOURS)
    resultats = []

    for cfg in SOURCES_REPERES:
        try:
            entries = lire_flux(cfg)
        except Exception as e:
            print(f"[ERREUR] {cfg['nom']} : {e}")
            continue

        for e in entries:
            dt = date_entree(e)
            if not dt or dt < limite:
                continue

            titre = nettoyer_html(getattr(e, "title", ""))
            url = getattr(e, "link", "") or ""

            regle = type_repere_autorise(titre)
            if not regle:
                continue

            chiffre = premier_pourcentage(titre)
            if not chiffre:
                continue

            notion = regle["notion"]
            zone = detecter_zone(titre, cfg["nom"])

            # Score simple et transparent.
            score = (
                NOTIONS[notion]["priorite"]
                + cfg["bonus"]
                + max(0, 5 - (now - dt).days)
            )

            resultats.append(
                Item(
                    source=cfg["nom"],
                    titre=titre,
                    resume="",
                    url=url,
                    date=dt,
                    notion=notion,
                    score=score,
                    chiffre=chiffre,
                    zone=zone,
                    libelle=regle["libelle"],
                )
            )

    return resultats


def choisir_reperes(items):
    items = sorted(items, key=lambda x: (x.score, x.date), reverse=True)

    choisis = []
    notions = set()
    sources = {}

    for x in items:
        if x.notion in notions:
            continue

        if sources.get(x.source, 0) >= 2:
            continue

        choisis.append(x)
        notions.add(x.notion)
        sources[x.source] = sources.get(x.source, 0) + 1

        if len(choisis) >= NB_REPERES_MAX:
            break

    return choisis


def titre_repere(item: Item) -> str:
    n, z, c = item.notion, item.zone, item.chiffre
    valeur = valeur_pourcentage(c)
    direction = direction_depuis_titre(item.titre)
    variation_nulle = valeur is not None and abs(valeur) < 0.0001

    if n == "Croissance":
        if variation_nulle or direction == "stable":
            return f"Le PIB est stable en {z}"
        if valeur is not None and valeur > 0:
            return f"Le PIB progresse de {c} en {z}"
        if valeur is not None and valeur < 0:
            return f"Le PIB recule de {c.replace('-', '').strip()} en {z}"
        return f"Le PIB évolue de {c} en {z}"

    if n == "Inflation":
        if direction == "hausse":
            return f"L’inflation remonte à {c} en {z}"
        if direction == "baisse":
            return f"L’inflation ralentit à {c} en {z}"
        if direction == "stable":
            return f"L’inflation reste stable à {c} en {z}"
        return f"L’inflation s’établit à {c} en {z}"

    if n == "Emploi et chômage":
        if direction == "hausse":
            return f"Le chômage remonte à {c} en {z}"
        if direction == "baisse":
            return f"Le chômage recule à {c} en {z}"
        if direction == "stable":
            return f"Le chômage reste stable à {c} en {z}"
        return f"Le chômage s’établit à {c} en {z}"

    if n == "Consommation":
        if variation_nulle or direction == "stable":
            return f"La consommation est stable en {z}"
        if valeur is not None and valeur > 0:
            return f"La consommation progresse de {c} en {z}"
        if valeur is not None and valeur < 0:
            return f"La consommation recule de {c.replace('-', '').strip()} en {z}"
        return f"La consommation évolue de {c} en {z}"

    if n == "Production":
        if variation_nulle or direction == "stable":
            return f"La production industrielle est stable en {z}"
        if valeur is not None and valeur > 0:
            return f"La production industrielle progresse de {c} en {z}"
        if valeur is not None and valeur < 0:
            return f"La production industrielle recule de {c.replace('-', '').strip()} en {z}"
        return f"La production industrielle évolue de {c} en {z}"

    if n == "Finances publiques":
        return f"Un indicateur de finances publiques atteint {c} en {z}"

    return item.titre

def unite_repere(item: Item) -> str:
    return f"{item.libelle}, {item.zone}"


# ---------------------------------------------------------------------------
# BRÈVES
# ---------------------------------------------------------------------------

def score_evenement(texte: str) -> int:
    t = norm(texte)
    score = 0

    for mot, bonus in EVENEMENTS_BONUS.items():
        if norm(mot) in t:
            score += bonus

    for mot, penalite in PENALITES_BREVES.items():
        if norm(mot) in t:
            score += penalite

    return score


def candidats_breves(now: datetime):
    limite = now - timedelta(days=AGE_MAX_JOURS)
    resultats = []

    for cfg in SOURCES_BREVES:
        try:
            entries = lire_flux(cfg)
        except Exception as e:
            print(f"[ERREUR] {cfg['nom']} : {e}")
            continue

        for e in entries:
            dt = date_entree(e)
            if not dt or dt < limite:
                continue

            titre = nettoyer_html(getattr(e, "title", ""))
            resume = nettoyer_html(
                getattr(e, "summary", "")
                or getattr(e, "description", "")
            )
            url = getattr(e, "link", "") or ""

            bloc = f"{titre} {resume}"
            nt = norm(bloc)

            # Exclusion forte : si l'un de ces motifs est présent, on rejette.
            if any(norm(x) in nt for x in EXCLUSIONS_BREVES):
                continue

            if len(titre) < 20:
                continue

            notion, score = classer(bloc)
            if not notion:
                continue

            score += cfg["bonus"]
            score += max(0, 5 - (now - dt).days)
            score += score_evenement(bloc)

            # On exige un minimum d'intérêt éditorial.
            if score < 15:
                continue

            resultats.append(
                Item(
                    source=cfg["nom"],
                    titre=titre,
                    resume=resume_breve(resume),
                    url=url,
                    date=dt,
                    notion=notion,
                    score=score,
                )
            )

    return resultats


def choisir_breves(items):
    items = sorted(items, key=lambda x: (x.score, x.date), reverse=True)

    choisis = []
    urls = set()
    notions = {}
    sources = {}

    # Première passe : 3 notions différentes, max 2 brèves par source.
    for x in items:
        if x.url and x.url in urls:
            continue

        if notions.get(x.notion, 0) >= 1:
            continue

        if sources.get(x.source, 0) >= 2:
            continue

        choisis.append(x)

        if x.url:
            urls.add(x.url)

        notions[x.notion] = notions.get(x.notion, 0) + 1
        sources[x.source] = sources.get(x.source, 0) + 1

        if len(choisis) >= NB_BREVES:
            break

    # Seconde passe : on relâche uniquement la diversité des notions.
    if len(choisis) < NB_BREVES:
        for x in items:
            if x in choisis:
                continue

            if x.url and x.url in urls:
                continue

            if sources.get(x.source, 0) >= 2:
                continue

            choisis.append(x)

            if x.url:
                urls.add(x.url)

            sources[x.source] = sources.get(x.source, 0) + 1

            if len(choisis) >= NB_BREVES:
                break

    return choisis


# ---------------------------------------------------------------------------
# SORTIE
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)

    reperes = choisir_reperes(candidats_reperes(now))
    breves = choisir_breves(candidats_breves(now))

    if not reperes and not breves:
        raise SystemExit(
            "Aucune information exploitable : actualites.json n'est pas remplacé."
        )

    doc = {
        "periode": periode(now),
        "publie": date_fr(now),
        "sources": sorted({x.source for x in reperes + breves}),
        "reperes": [
            {
                "chiffre": x.chiffre,
                "unite": unite_repere(x),
                "titre": titre_repere(x),
                "explication": NOTIONS[x.notion]["explication"],
                "notion": x.notion,
                "question": NOTIONS[x.notion]["question"],
                "source": x.source,
                "date": date_fr(x.date),
                "url": x.url,
            }
            for x in reperes
        ],
        "breves": [
            {
                "titre": x.titre,
                "resume": x.resume,
                "notion": x.notion,
                "source": x.source,
                "date": date_fr(x.date),
                "url": x.url,
            }
            for x in breves
        ],
    }

    SORTIE.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[OK] {len(reperes)} repère(s), {len(breves)} brève(s)")

    for x in reperes:
        print(f"REPÈRE [{x.notion}] {x.source} — {x.titre}")

    for x in breves:
        print(f"BRÈVE  [{x.notion}] {x.source} — {x.titre}")


if __name__ == "__main__":
    main()
