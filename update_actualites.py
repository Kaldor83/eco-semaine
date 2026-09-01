#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
L’ÉCO DE LA SEMAINE — V7
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
        "reponse": "Une croissance durablement faible réduit généralement les débouchés des entreprises, freine l’investissement et peut limiter les créations d’emplois.",
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
        "reponse": "Les prix continuent d’augmenter, mais moins vite. Ils ne baissent que si l’inflation devient négative.",
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
        "reponse": "Une hausse du chômage tend à réduire la consommation, car elle diminue les revenus de certains ménages et renforce souvent l’épargne de précaution.",
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
        "reponse": "Une baisse de la consommation réduit les ventes des entreprises, qui peuvent alors diminuer leur production, leurs investissements ou leurs recrutements.",
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
        "reponse": "L’incertitude pousse les entreprises à reporter certains projets, car leurs ventes futures et la rentabilité attendue deviennent plus difficiles à prévoir.",
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
        "reponse": "Des taux plus bas réduisent le coût du crédit. Certains projets d’investissement deviennent alors plus rentables et plus faciles à financer.",
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
        "reponse": "Parce que le pouvoir d’achat dépend aussi des prix. Si les prix augmentent plus vite que le salaire, le pouvoir d’achat recule.",
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
        "reponse": "Quand l’activité ralentit, les recettes fiscales progressent moins vite tandis que certaines dépenses, notamment sociales, peuvent augmenter.",
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
        "reponse": "Une modification des échanges peut changer les débouchés, les coûts d’approvisionnement et la concurrence auxquels les entreprises françaises sont confrontées.",
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
        "reponse": "Une baisse durable de la production réduit les besoins de travail. Les entreprises peuvent alors limiter les recrutements ou supprimer des emplois.",
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
        "reponse": "Une productivité moins dynamique limite la hausse de la production potentielle, des salaires réels et, à long terme, du niveau de vie.",
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
        "reponse": "Une hausse du coût de l’énergie augmente les coûts de production et de transport, que les entreprises peuvent ensuite répercuter partiellement dans leurs prix.",
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
        "reponse": "La décision d’une entreprise dépend souvent de la demande attendue, de ses coûts, du financement disponible et du niveau d’incertitude.",
    },
}


# ---------------------------------------------------------------------------
# STRUCTURE DU COURS ET BANQUE DE QUESTIONS
# ---------------------------------------------------------------------------

THEMES = {
    "Croissance": ("Thème 1", "Produire et mesurer la richesse"),
    "Production": ("Thème 1", "Produire et mesurer la richesse"),
    "Productivité": ("Thème 1", "Produire et mesurer la richesse"),
    "Entreprises": ("Thème 1", "Produire et mesurer la richesse"),

    "Investissement": ("Thème 2", "Investir et financer les projets"),
    "Taux d’intérêt": ("Thème 2", "Investir et financer les projets"),

    "Inflation": ("Thème 3", "Comprendre l’inflation"),
    "Pouvoir d’achat": ("Thème 3", "Comprendre l’inflation"),
    "Énergie": ("Thème 3", "Comprendre l’inflation"),

    "Emploi et chômage": ("Thème 4", "Emploi, chômage et salaires"),

    "Commerce international": ("Thème 5", "Échanges internationaux et compétitivité"),

    "Finances publiques": ("Thème 6", "Politiques économiques"),
}


BANQUE_QUESTIONS = {
    # ───────────────────── THÈME 1 ─────────────────────

    "Croissance": [
        (
            "Quelle différence faut-il faire entre le PIB et la croissance économique ?",
            "Le PIB mesure la richesse produite sur une période. La croissance mesure l’évolution du PIB en volume entre deux périodes."
        ),
        (
            "Pourquoi additionne-t-on les valeurs ajoutées plutôt que les chiffres d’affaires pour calculer le PIB ?",
            "Additionner les chiffres d’affaires compterait plusieurs fois les consommations intermédiaires. La valeur ajoutée mesure uniquement la richesse réellement créée par chaque producteur."
        ),
        (
            "Pourquoi distingue-t-on le PIB en valeur du PIB en volume ?",
            "Le PIB en valeur varie avec les quantités produites mais aussi avec les prix. Le PIB en volume neutralise l’effet des prix pour mesurer l’évolution réelle de la production."
        ),
        (
            "Une hausse du PIB signifie-t-elle nécessairement une amélioration du bien-être ?",
            "Non. Le PIB mesure la production, pas directement la répartition des revenus, la qualité de vie, les inégalités ou les effets environnementaux."
        ),
        (
            "Quel lien existe entre productivité et croissance économique ?",
            "Une hausse de la productivité permet de produire davantage avec une même quantité de ressources. Elle peut donc soutenir la croissance à long terme."
        ),
        (
            "Pourquoi une croissance durablement faible peut-elle peser sur l’emploi et l’investissement ?",
            "Des débouchés moins dynamiques réduisent les besoins de production. Les entreprises peuvent alors limiter leurs recrutements et reporter certains investissements."
        ),
    ],

    "Production": [
        (
            "Quelle différence existe entre production et valeur ajoutée ?",
            "La production correspond à la valeur des biens et services produits. La valeur ajoutée retranche les consommations intermédiaires afin de mesurer la richesse créée."
        ),
        (
            "Pourquoi une hausse de la production d’une entreprise n’implique-t-elle pas forcément une hausse équivalente de sa richesse créée ?",
            "Parce qu’elle peut utiliser davantage de consommations intermédiaires. La richesse créée dépend de la valeur ajoutée, pas seulement du niveau de production."
        ),
        (
            "Comment une baisse durable de la production peut-elle affecter l’emploi ?",
            "Si les entreprises produisent moins durablement, leurs besoins de travail peuvent diminuer. Elles peuvent alors réduire les recrutements ou les effectifs."
        ),
        (
            "Peut-on produire davantage sans utiliser davantage de travail ou de capital ?",
            "Oui, si la productivité augmente. Une meilleure organisation, l’innovation ou de nouveaux équipements peuvent permettre de produire davantage avec les mêmes ressources."
        ),
    ],

    "Productivité": [
        (
            "Que mesure la productivité ?",
            "Elle rapporte la quantité produite à la quantité de facteurs de production utilisée, par exemple le nombre d’heures de travail."
        ),
        (
            "Pourquoi la productivité est-elle importante pour la croissance à long terme ?",
            "Elle permet d’augmenter la production sans accroître dans les mêmes proportions le travail ou le capital mobilisé."
        ),
        (
            "Comment l’investissement peut-il améliorer la productivité ?",
            "De nouveaux équipements, logiciels ou technologies peuvent permettre aux salariés de produire davantage ou plus efficacement."
        ),
        (
            "Une hausse de la productivité entraîne-t-elle automatiquement une hausse des salaires ?",
            "Non. Elle crée une marge permettant potentiellement d’augmenter les salaires, les profits ou de réduire les prix, mais la répartition dépend des choix et du contexte."
        ),
        (
            "La productivité peut-elle augmenter alors que l’emploi diminue ?",
            "Oui. Si la production baisse moins vite que le nombre d’heures travaillées, ou si l’organisation devient plus efficace, la productivité peut progresser malgré une baisse de l’emploi."
        ),
    ],

    "Entreprises": [
        (
            "De quoi dépend principalement la décision d’une entreprise d’augmenter sa production ?",
            "Elle dépend notamment de la demande anticipée, des capacités disponibles, des coûts de production et de la rentabilité attendue."
        ),
        (
            "Pourquoi une entreprise peut-elle investir alors même que ses capacités actuelles suffisent ?",
            "Elle peut vouloir réduire ses coûts, améliorer sa productivité, innover, remplacer des équipements ou préparer une hausse future de la demande."
        ),
        (
            "Pourquoi une hausse du chiffre d’affaires ne signifie-t-elle pas nécessairement une hausse du profit ?",
            "Les coûts peuvent augmenter plus vite que les ventes. Le profit dépend de l’écart entre les recettes et l’ensemble des coûts."
        ),
        (
            "Comment la conjoncture économique influence-t-elle les décisions des entreprises ?",
            "Elle modifie les perspectives de demande, les coûts, les conditions de financement et le niveau d’incertitude, donc les décisions de production, d’emploi et d’investissement."
        ),
    ],

    # ───────────────────── THÈME 2 ─────────────────────

    "Investissement": [
        (
            "Qu’est-ce qui distingue un investissement d’une dépense courante ?",
            "Un investissement acquiert ou améliore un actif destiné à être utilisé durablement. Une dépense courante est consommée dans le fonctionnement habituel."
        ),
        (
            "Pourquoi une entreprise investit-elle ?",
            "Elle peut augmenter ses capacités, remplacer des équipements, réduire ses coûts, améliorer sa productivité ou développer de nouveaux produits."
        ),
        (
            "Pourquoi l’incertitude peut-elle freiner l’investissement ?",
            "Un investissement engage des ressources aujourd’hui pour des résultats futurs. Plus ces résultats sont incertains, plus l’entreprise peut préférer attendre."
        ),
        (
            "Quelle différence existe entre financement interne et financement externe ?",
            "Le financement interne utilise les ressources générées par l’entreprise. Le financement externe fait appel à des prêteurs ou à des apporteurs de capitaux."
        ),
        (
            "Pourquoi le coût du financement influence-t-il le niveau d’investissement ?",
            "Plus le financement est coûteux, plus la rentabilité minimale exigée d’un projet augmente. Certains investissements deviennent alors moins intéressants."
        ),
    ],

    "Taux d’intérêt": [
        (
            "Que représente un taux d’intérêt pour un emprunteur ?",
            "Il représente le prix payé pour disposer temporairement de capitaux empruntés, auquel peuvent s’ajouter d’autres frais de financement."
        ),
        (
            "Pourquoi une hausse des taux d’intérêt peut-elle freiner l’investissement ?",
            "Elle augmente le coût du crédit et réduit la rentabilité de certains projets financés par emprunt."
        ),
        (
            "Comment les taux d’intérêt peuvent-ils influencer la consommation des ménages ?",
            "Des taux élevés rendent le crédit plus coûteux et peuvent encourager l’épargne, ce qui tend à freiner certaines dépenses de consommation."
        ),
        (
            "Quel lien existe entre taux directeurs et taux proposés par les banques ?",
            "Les taux directeurs influencent les conditions auxquelles les banques se financent et placent leurs liquidités, ce qui se transmet en partie aux taux des crédits."
        ),
        (
            "Pourquoi une baisse des taux ne suffit-elle pas toujours à relancer fortement l’investissement ?",
            "Si les entreprises anticipent une demande faible ou jugent l’avenir très incertain, elles peuvent ne pas investir malgré un financement moins coûteux."
        ),
    ],

    # ───────────────────── THÈME 3 ─────────────────────

    "Inflation": [
        (
            "Quelle différence existe entre inflation et hausse du prix d’un seul produit ?",
            "L’inflation correspond à une hausse générale et durable du niveau des prix. La hausse isolée d’un produit ne suffit donc pas à caractériser l’inflation."
        ),
        (
            "Pourquoi un ralentissement de l’inflation ne signifie-t-il pas que les prix baissent ?",
            "Les prix continuent d’augmenter, mais moins vite. Ils ne diminuent en moyenne que si le taux d’inflation devient négatif."
        ),
        (
            "Comment une hausse des coûts de production peut-elle alimenter l’inflation ?",
            "Les entreprises peuvent répercuter une partie de la hausse de leurs coûts dans leurs prix de vente, ce qui diffuse la hausse des prix dans l’économie."
        ),
        (
            "Comment une demande très dynamique peut-elle provoquer de l’inflation ?",
            "Si la demande progresse plus vite que les capacités de production, les entreprises peuvent augmenter leurs prix face aux tensions sur les biens, services et facteurs de production."
        ),
        (
            "Pourquoi l’inflation ne touche-t-elle pas tous les ménages de la même manière ?",
            "Les ménages n’achètent pas les mêmes biens dans les mêmes proportions. Leur inflation réellement ressentie dépend donc de leur structure de consommation."
        ),
        (
            "Pourquoi les banques centrales cherchent-elles généralement à limiter une inflation trop élevée ?",
            "Une inflation élevée et instable réduit la visibilité économique, déforme les décisions et peut fortement affecter le pouvoir d’achat et la confiance."
        ),
    ],

    "Pouvoir d’achat": [
        (
            "Qu’est-ce que le pouvoir d’achat ?",
            "Il correspond à la quantité de biens et services qu’un revenu permet d’acheter. Il dépend donc à la fois des revenus et des prix."
        ),
        (
            "Pourquoi une hausse du salaire nominal ne garantit-elle pas une hausse du pouvoir d’achat ?",
            "Si les prix augmentent plus vite que le salaire nominal, le salaire réel et donc le pouvoir d’achat diminuent."
        ),
        (
            "Comment l’inflation peut-elle modifier la consommation des ménages ?",
            "En réduisant le pouvoir d’achat réel, elle peut conduire les ménages à arbitrer leurs dépenses, réduire certains achats ou puiser dans leur épargne."
        ),
        (
            "Pourquoi l’évolution moyenne du pouvoir d’achat ne décrit-elle pas la situation de chaque ménage ?",
            "Les revenus, les structures de consommation et les situations familiales diffèrent. Une moyenne nationale masque donc des évolutions individuelles très différentes."
        ),
    ],

    "Énergie": [
        (
            "Pourquoi le prix de l’énergie peut-il influencer l’inflation générale ?",
            "L’énergie entre directement dans les dépenses des ménages et indirectement dans de nombreux coûts de production et de transport."
        ),
        (
            "Comment une hausse du coût de l’énergie affecte-t-elle les entreprises ?",
            "Elle augmente directement ou indirectement leurs coûts. Selon leur pouvoir de marché, elles peuvent réduire leurs marges ou augmenter leurs prix."
        ),
        (
            "Pourquoi une baisse du prix du pétrole ne se transmet-elle pas toujours immédiatement et intégralement aux prix payés par les consommateurs ?",
            "Les prix finaux comprennent d’autres coûts et taxes, et les contrats ou stocks peuvent retarder la transmission des variations du pétrole."
        ),
        (
            "Pourquoi un choc énergétique peut-il à la fois augmenter les prix et ralentir l’activité ?",
            "Il augmente les coûts et réduit le pouvoir d’achat, ce qui peut simultanément alimenter l’inflation et freiner la consommation et la production."
        ),
    ],

    # ───────────────────── THÈME 4 ─────────────────────

    "Emploi et chômage": [
        (
            "Comment définit-on généralement un chômeur au sens du BIT ?",
            "Il s’agit d’une personne sans emploi, disponible pour travailler et qui recherche activement un emploi, selon les critères statistiques du BIT."
        ),
        (
            "Pourquoi le taux de chômage ne mesure-t-il pas toutes les difficultés du marché du travail ?",
            "Il ne décrit pas à lui seul le sous-emploi, le temps partiel subi, le découragement ou la qualité des emplois occupés."
        ),
        (
            "Comment une hausse du chômage peut-elle affecter la consommation ?",
            "Elle réduit les revenus de certains ménages et peut accroître l’épargne de précaution des autres, ce qui tend à freiner la consommation."
        ),
        (
            "Pourquoi une croissance économique plus forte peut-elle réduire le chômage ?",
            "Si la demande adressée aux entreprises augmente durablement, elles peuvent accroître leur production et leurs besoins de travail."
        ),
        (
            "Quel lien peut exister entre productivité et salaires à long terme ?",
            "Des gains de productivité augmentent la richesse produite par heure de travail et peuvent créer une marge permettant une progression des salaires réels."
        ),
        (
            "Pourquoi une hausse du salaire minimum peut-elle avoir plusieurs effets économiques possibles ?",
            "Elle augmente le revenu des salariés concernés mais aussi le coût du travail pour les employeurs. L’effet final dépend notamment de la productivité, de la demande et des possibilités d’ajustement."
        ),
    ],

    # ───────────────────── THÈME 5 ─────────────────────

    "Commerce international": [
        (
            "Pourquoi les pays échangent-ils des biens et services entre eux ?",
            "Les échanges permettent de bénéficier de spécialisations, de ressources différentes, d’économies d’échelle et d’une plus grande variété de produits."
        ),
        (
            "Quelle différence existe entre exportations et importations ?",
            "Les exportations sont les biens et services vendus au reste du monde. Les importations sont ceux achetés au reste du monde."
        ),
        (
            "Qu’est-ce que la balance commerciale ?",
            "Elle correspond à la différence entre la valeur des exportations et celle des importations de biens sur une période."
        ),
        (
            "Quelle différence existe entre compétitivité-prix et compétitivité hors-prix ?",
            "La compétitivité-prix repose sur les prix relatifs. La compétitivité hors-prix repose notamment sur la qualité, l’innovation, l’image, les délais ou les services."
        ),
        (
            "Pourquoi une hausse des droits de douane peut-elle affecter les entreprises nationales ?",
            "Elle renchérit certains produits importés, protège éventuellement certains producteurs, mais peut aussi augmenter le coût des intrants et provoquer des mesures de rétorsion."
        ),
        (
            "Un déficit commercial signifie-t-il nécessairement qu’une économie est en mauvaise santé ?",
            "Non. Il peut refléter des faiblesses de compétitivité, mais aussi une forte demande intérieure ou des importations d’équipements préparant la production future."
        ),
    ],

    # ───────────────────── THÈME 6 ─────────────────────

    "Finances publiques": [
        (
            "Quelle différence existe entre déficit public et dette publique ?",
            "Le déficit est un flux annuel lorsque les dépenses dépassent les recettes. La dette est un stock résultant notamment de l’accumulation des déficits passés."
        ),
        (
            "Pourquoi un ralentissement économique peut-il creuser le déficit public sans nouvelle mesure gouvernementale ?",
            "Les recettes fiscales ralentissent tandis que certaines dépenses, comme les allocations chômage, peuvent augmenter automatiquement."
        ),
        (
            "Qu’est-ce qu’une politique budgétaire expansionniste ?",
            "C’est une politique qui cherche à soutenir l’activité par une hausse des dépenses publiques, une baisse des prélèvements ou les deux."
        ),
        (
            "Pourquoi une politique budgétaire expansionniste peut-elle soutenir la croissance ?",
            "Elle augmente directement ou indirectement la demande adressée aux entreprises, ce qui peut stimuler production, revenus et emploi."
        ),
        (
            "Quel est l’objectif principal d’une politique monétaire restrictive ?",
            "Elle vise généralement à ralentir la demande et le crédit afin de réduire les tensions inflationnistes."
        ),
        (
            "Pourquoi une politique économique peut-elle produire des effets différents selon la conjoncture ?",
            "Son efficacité dépend notamment de la confiance, du niveau des taux, des capacités de production, de l’endettement et de la réaction des ménages et des entreprises."
        ),
    ],
}


def theme_pour(notion: str):
    return THEMES.get(notion, ("", ""))


def question_reponse_pour(notion: str, now: datetime):
    """
    Rotation hebdomadaire déterministe :
    - même question pour tous les étudiants pendant une semaine ;
    - question différente la semaine suivante si la notion réapparaît ;
    - aucun stockage externe nécessaire.
    """
    banque = BANQUE_QUESTIONS.get(notion, [])

    if not banque:
        cfg = NOTIONS.get(notion, {})
        return cfg.get("question", ""), cfg.get("reponse", "")

    date_locale = now.astimezone(FUSEAU_PARIS).date()
    semaine_absolue = date_locale.toordinal() // 7

    # Décalage stable pour éviter que toutes les notions utilisent le même rang.
    decalage = sum(ord(c) for c in notion) % len(banque)
    indice = (semaine_absolue + decalage) % len(banque)

    return banque[indice]


def serialiser_repere(x, now: datetime):
    theme, theme_titre = theme_pour(x.notion)
    question, reponse = question_reponse_pour(x.notion, now)

    return {
        "chiffre": x.chiffre,
        "unite": unite_repere(x),
        "titre": titre_repere(x),
        "explication": NOTIONS[x.notion]["explication"],
        "notion": x.notion,
        "theme": theme,
        "theme_titre": theme_titre,
        "question": question,
        "reponse": reponse,
        "source": x.source,
        "date": date_fr(x.date),
        "url": x.url,
    }


def serialiser_breve(x):
    theme, theme_titre = theme_pour(x.notion)

    return {
        "titre": x.titre,
        "resume": x.resume,
        "notion": x.notion,
        "theme": theme,
        "theme_titre": theme_titre,
        "source": x.source,
        "date": date_fr(x.date),
        "url": x.url,
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
        "reperes": [serialiser_repere(x, now) for x in reperes],
        "breves": [serialiser_breve(x) for x in breves],
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
