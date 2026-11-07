# Analyse Comparative de Marché 

**Projet Python .**

##  Contexte du projet
Un client souhaite acheter de l'électronique et de l'électroménager à Abidjan. Il hésite entre trois enseignes : **Marché Lagune**, **Baobab Shop** et **Comptoir Ivoire**. 
L'objectif de ce projet est de collecter les données de ces trois sources hétérogènes (CSV, JSON, Excel), de les nettoyer, de les rapprocher d'un catalogue commun de 30 produits, et de fournir une analyse comparative afin d'aider le client à prendre la meilleure décision d'achat.

##  Sources de données
Le projet s'appuie sur 5 fichiers sources situés dans le dossier `data/` :
1. `catalogue_reference.csv` : Référentiel commun (30 produits, P01 à P30).
2. `marche_lagune.csv` : Export CSV (séparateur `;`, encodage Excel FR, prix en texte).
3. `baobab_shop.json` : API JSON de l'application mobile (prix + frais de livraison).
4. `comptoir_ivoire.xlsx` : Classeur Excel (prix catalogue avec remises, stock en rayon).
5. `historique_prix.csv` : 20 876 lignes de prix quotidiens du 01/11/2025 au 31/10/2026.

## Fonctionnalités et Résultats (Les 8 étapes du projet)

1. **Chargement** : Lecture unifiée des formats CSV, JSON et Excel via `pandas` et le module natif `json`.
2. **Nettoyage & Journalisation** : 
   - Gestion des fichiers "sales" (BOM, doublons, prix en texte `"102 900 FCFA"`, prix `null` ou aberrants comme le Tecno Spark 20 à 779 000 FCFA).
   - Génération d'un fichier `journal_nettoyage.txt` listant toutes les anomalies rencontrées.
3. **Rapprochement (Fuzzy Matching)** : Les noms variant d'une enseigne à l'autre (ex: *SAMSUNG GALAXY A15* vs *Galaxy A15 128GB - Samsung*), un algorithme de correspondance floue (`difflib`) et une normalisation (minuscules, sans accents, unités harmonisées) sont utilisés pour associer chaque article à son `produit_id`.
4. **Comparatif** : Pour chaque produit disponible dans au moins 2 enseignes, génération d'un fichier `comparatif.csv` (avec calcul du prix payé, de l'enseigne la moins chère, et de l'écart en FCFA et en %).
5. **Synthèse** : Calcul du nombre de victoires par enseigne (moins cher), de l'écart moyen par rapport au prix le plus bas, et extraction du Top 3 des produits où comparer rapporte le plus.
6. **Panier** : Calcul du coût du panier de rentrée (Tecno Spark 20, Lenovo IdeaPad 3, 2x Clés USB SanDisk, Disque dur Seagate, Micro-ondes Samsung) enseigne par enseigne, et calcul du prix en achetant chaque article au moins cher.
7. **Historique** : Comparaison des prix moyens de la semaine du Black Friday (24 au 30 nov 2025) avec la moyenne annuelle.
8. **Complexité (Big O)** : Mesure des performances et optimisation de la recherche dans l'historique (20k+ lignes) via une indexation en dictionnaire, passant d'une recherche linéaire `O(n)` à un accès direct `O(1)`.

##  Stack Technique & Approche Big O
- **Langages & Librairies** : Python 3, Pandas, OpenPyXL.
- **Recherche & Normalisation** : Expressions régulières (`re`), normalisation Unicode, `difflib`.
- **Optimisation** : Utilisation massive de dictionnaires Python `{clé: valeur}` pour stocker les prix. Au lieu de scanner tout le DataFrame à chaque requête (complexité `O(N)`), le dictionnaire permet de retrouver un prix en temps constant `O(1)`.

## Installation et Exécution

1. Cloner le dépôt ou télécharger le dossier.
2. Créer un environnement virtuel (recommandé) :
```bash
python -m venv .venv
# Sur Windows :
.venv\Scripts\activate
# Sur Mac/Linux :
source .venv/bin/activat
