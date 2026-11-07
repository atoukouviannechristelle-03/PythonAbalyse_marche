import pandas as pd
import json
import time
import re
import unicodedata
import difflib
import os

# Création du dossier output s'il n'existe pas
os.makedirs("output", exist_ok=True)

# Liste globale pour le journal de nettoyage (Question 2)
journal_nettoyage = []


def log_anomalie(source, message):
    journal_nettoyage.append(f"[{source}] {message}")


# ==========================================
# FONCTIONS UTILITAIRES (Rapprochement)
# ==========================================

def normaliser_nom(texte):
    """
    Normalise les noms pour le rapprochement flou (Big O).
    Gère les accents, la casse, et harmonise les unités (Go -> GB, To -> TB).
    """
    if not isinstance(texte, str): return ""
    # Passage en minuscules et suppression des accents
    texte = unicodedata.normalize('NFD', texte).encode('ascii', 'ignore').decode('utf-8').lower()
    # Remplacement des unités
    texte = texte.replace('go', 'gb').replace('to', 'tb')
    # Suppression de tout ce qui n'est pas lettre ou chiffre
    return re.sub(r'[^a-z0-9]', '', texte)


def rapprocher_catalogue(df_cat, df_source, nom_colonne):
    """Associe chaque article à un produit_id via fuzzy matching (difflib)"""
    correspondances = []
    noms_catalogue_norm = {normaliser_nom(nom): pid for nom, pid in zip(df_cat['nom'], df_cat['produit_id'])}
    liste_noms_norm = list(noms_catalogue_norm.keys())

    for nom in df_source[nom_colonne]:
        nom_norm = normaliser_nom(nom)
        # Trouver la meilleure correspondance (seuil de 50% de similarité)
        match = difflib.get_close_matches(nom_norm, liste_noms_norm, n=1, cutoff=0.5)
        if match:
            correspondances.append(noms_catalogue_norm[match[0]])
        else:
            log_anomalie("Rapprochement", f"Impossible d'associer : {nom}")
            correspondances.append(None)
    return correspondances


# ==========================================
# 1. & 2. CHARGEMENT ET NETTOYAGE
# ==========================================

def charger_donnees():
    print("--- 1. & 2. CHARGEMENT ET NETTOYAGE ---")

    # 1.1 Catalogue
    df_cat = pd.read_csv("data/catalogue_reference.csv")

    # 1.2 Marché Lagune
    df_ml = pd.read_csv("data/marche_lagune.csv", sep=";", encoding="utf-8-sig")

    # Doublons
    if df_ml.duplicated(subset=['reference']).any():
        log_anomalie("Marché Lagune", "Lignes dupliquées détectées et supprimées.")
        df_ml = df_ml.drop_duplicates(subset=['reference'], keep='first')

    def clean_prix_ml(val):
        if pd.isna(val) or "demande" in str(val).lower():
            log_anomalie("Marché Lagune", f"Prix invalide ou manquant : {val}")
            return None
        val_str = str(val).replace('\xa0', '').replace('FCFA', '').replace(' ', '')
        try:
            p = float(val_str)
            # Détection aberrant (Tecno Spark 20 à 779 000 au lieu de ~80 000)
            if p > 500000:
                log_anomalie("Marché Lagune", f"Prix aberrant ignoré : {p} FCFA")
                return None
            return p
        except:
            return None

    df_ml['prix_clean'] = df_ml['prix'].apply(clean_prix_ml)
    df_ml['dispo'] = df_ml['disponibilite'] != 'Rupture'

    # 1.3 Baobab Shop (Intégration de ton vrai fichier JSON)
    with open("data/baobab_shop.json", "r", encoding="utf-8") as f:
        data_baobab = json.load(f)

    baobab_items = []
    for item in data_baobab['items']:
        amount = item['pricing']['amount']
        if amount is None:
            log_anomalie("Baobab Shop", f"Prix null pour l'article : {item['title']}")
            prix_total = None
        else:
            prix_total = amount + item['pricing']['delivery_fee']

        baobab_items.append({
            'nom': item['title'],
            'prix_clean': prix_total,
            'dispo': item['stock'] > 0
        })
    df_baobab = pd.DataFrame(baobab_items)

    # 1.4 Comptoir Ivoire (Excel)
    # Sauter le titre et les entêtes vides
    df_ci = pd.read_excel("data/comptoir_ivoire.xlsx", skiprows=2)
    df_ci = df_ci.dropna(subset=['Code'])

    def clean_prix_ci(val):
        if isinstance(val, str):
            val = val.replace(' ', '')
        try:
            return float(val)
        except:
            return None

    df_ci['prix_cat'] = df_ci['Prix catalogue (FCFA)'].apply(clean_prix_ci)
    df_ci['remise'] = df_ci['Remise (%)'].fillna(0)
    df_ci['prix_clean'] = df_ci['prix_cat'] * (1 - df_ci['remise'] / 100)
    df_ci['dispo'] = df_ci['Quantité en rayon'] > 0
    df_ci['nom'] = df_ci['Article']

    # Sauvegarde du journal
    with open("output/journal_nettoyage.txt", "w", encoding="utf-8") as f:
        f.write("JOURNAL DE NETTOYAGE\n====================\n")
        for log in journal_nettoyage:
            f.write(log + "\n")

    return df_cat, df_ml, df_baobab, df_ci


# ==========================================
# 3., 4. & 5. COMPARATIF ET SYNTHÈSE
# ==========================================

def analyser_marche(df_cat, df_ml, df_baobab, df_ci):
    print("\n--- 3. RAPPROCHEMENT ---")
    df_ml['produit_id'] = rapprocher_catalogue(df_cat, df_ml, 'designation')
    df_baobab['produit_id'] = rapprocher_catalogue(df_cat, df_baobab, 'nom')
    df_ci['produit_id'] = rapprocher_catalogue(df_cat, df_ci, 'nom')

    # Dictionnaire de prix : {produit_id: {enseigne: prix}}
    prix_par_produit = {}

    # Remplissage (on ignore les produits non dispos ou sans prix)
    for _, row in df_ml.iterrows():
        if row['produit_id'] and row['dispo'] and row['prix_clean']:
            prix_par_produit.setdefault(row['produit_id'], {})['Marché Lagune'] = row['prix_clean']

    for _, row in df_baobab.iterrows():
        if row['produit_id'] and row['dispo'] and row['prix_clean']:
            prix_par_produit.setdefault(row['produit_id'], {})['Baobab Shop'] = row['prix_clean']

    for _, row in df_ci.iterrows():
        if row['produit_id'] and row['dispo'] and row['prix_clean']:
            prix_par_produit.setdefault(row['produit_id'], {})['Comptoir Ivoire'] = row['prix_clean']

    print("\n--- 4. COMPARATIF ---")
    resultats = []
    stats_enseignes = {'Marché Lagune': {'gagne': 0, 'ecarts': []},
                       'Baobab Shop': {'gagne': 0, 'ecarts': []},
                       'Comptoir Ivoire': {'gagne': 0, 'ecarts': []}}

    for pid, prix in prix_par_produit.items():
        if len(prix) >= 2:  # Au moins 2 enseignes
            nom_prod = df_cat[df_cat['produit_id'] == pid]['nom'].iloc[0]
            min_prix = min(prix.values())
            best_shop = [k for k, v in prix.items() if v == min_prix][0]

            max_prix = max(prix.values())
            ecart_fcfa = max_prix - min_prix
            ecart_pct = (ecart_fcfa / max_prix) * 100

            # On prépare la ligne pour le CSV
            ligne = {'produit_id': pid, 'nom': nom_prod, 'moins_cher': best_shop,
                     'prix_min': min_prix, 'ecart_max_fcfa': ecart_fcfa, 'ecart_max_pct': round(ecart_pct, 2)}
            ligne.update(prix)  # Ajoute les colonnes Marché Lagune, Baobab, Comptoir
            resultats.append(ligne)

            # Statistiques pour la synthèse
            stats_enseignes[best_shop]['gagne'] += 1
            for shop, p in prix.items():
                stats_enseignes[shop]['ecarts'].append(p - min_prix)

    df_comp = pd.DataFrame(resultats).sort_values('ecart_max_fcfa', ascending=False)
    df_comp.to_csv("output/comparatif.csv", index=False, sep=";")

    print("\n--- 5. SYNTHÈSE ---")
    for shop, data in stats_enseignes.items():
        moy_ecart = sum(data['ecarts']) / len(data['ecarts']) if data['ecarts'] else 0
        print(f"{shop:<18} | Gagne {data['gagne']:>2} fois | Écart moyen : {moy_ecart:>8.2f} FCFA")

    print("\nTop 3 des produits où il y a le plus à gagner (Écart en FCFA) :")
    print(df_comp[['nom', 'ecart_max_fcfa', 'ecart_max_pct']].head(3).to_string(index=False))


# ==========================================
# 6. PANIER
# ==========================================

def calculer_panier(df_cat, df_ml, df_baobab, df_ci):
    print("\n--- 6. PANIER DE RENTRÉE ---")
    # Panier imposé : P04(x1), P12(x1), P14(x2), P15(x1), P28(x1)
    panier = {'P04': 1, 'P12': 1, 'P14': 2, 'P15': 1, 'P28': 1}

    prix_total_enseigne = {'Marché Lagune': 0, 'Baobab Shop': 0, 'Comptoir Ivoire': 0}
    panier_optimal = 0
    details_panier = []

    for pid, qte in panier.items():
        prix_dispo = {}
        for df, shop in [(df_ml, 'Marché Lagune'), (df_baobab, 'Baobab Shop'), (df_ci, 'Comptoir Ivoire')]:
            row = df[df['produit_id'] == pid]
            if not row.empty and row['dispo'].iloc[0] and pd.notna(row['prix_clean'].iloc[0]):
                prix_dispo[shop] = row['prix_clean'].iloc[0]

        if prix_dispo:
            for shop, p in prix_dispo.items():
                prix_total_enseigne[shop] += p * qte

            best_price = min(prix_dispo.values())
            panier_optimal += best_price * qte

            # Pour l'affichage détaillé
            nom = df_cat[df_cat['produit_id'] == pid]['nom'].iloc[0]
            details_panier.append(
                f"{qte}x {nom} : acheté chez {[k for k, v in prix_dispo.items() if v == best_price][0]}")
        else:
            print(f"⚠️ Attention : Le produit {pid} est indisponible partout.")

    print("Coût total du panier par enseigne (si tout acheté dans la même boutique) :")
    for shop, total in prix_total_enseigne.items():
        print(f" - {shop:<18} : {total:>10,.0f} FCFA")
    print(f"\nPrix du panier en achetant chaque article au moins cher : {panier_optimal:,.0f} FCFA")


# ==========================================
# 7. HISTORIQUE
# ==========================================

def analyser_historique():
    print("\n--- 7. HISTORIQUE (BLACK FRIDAY) ---")
    df_hist = pd.read_csv("data/historique_prix.csv")
    df_hist['date'] = pd.to_datetime(df_hist['date'])

    # Prix moyen de l'année
    moy_annee = df_hist.groupby('source')['prix_fcfa'].mean()

    # Prix moyen Black Friday (24 au 30 nov 2025)
    df_bf = df_hist[(df_hist['date'] >= '2025-11-24') & (df_hist['date'] <= '2025-11-30')]
    moy_bf = df_bf.groupby('source')['prix_fcfa'].mean()

    print(f"{'Enseigne':<20} | {'Moyenne BF':<12} | {'Moyenne Année':<12} | {'Économie %':<10}")
    print("-" * 65)
    for source in moy_annee.index:
        if source in moy_bf:
            eco = ((moy_annee[source] - moy_bf[source]) / moy_annee[source]) * 100
            print(f"{source:<20} | {moy_bf[source]:<12,.0f} | {moy_annee[source]:<12,.0f} | {eco:>8.2f}%")


# ==========================================
# 8. COMPLEXITÉ
# ==========================================

def mesurer_complexite():
    print("\n--- 8. COMPLEXITÉ ---")
    df_hist = pd.read_csv("data/historique_prix.csv")

    # Méthode 1 : Dictionnaire O(1)
    start = time.perf_counter()
    index_prix = {}
    for _, row in df_hist.iterrows():
        index_prix[(row['source'], row['produit_id'])] = row['prix_fcfa']
    for _ in range(1000):
        _ = index_prix.get(('Marché Lagune', 'P04'), 0)
    temps_dict = time.perf_counter() - start

    # Méthode 2 : Recherche linéaire DataFrame O(n)
    start = time.perf_counter()
    for _ in range(1000):
        _ = df_hist[(df_hist['source'] == 'Marché Lagune') & (df_hist['produit_id'] == 'P04')]['prix_fcfa'].values
    temps_lin = time.perf_counter() - start

    print(f"Temps de recherche avec Dictionnaire (O(1)) : {temps_dict * 1000:.4f} ms")
    print(f"Temps de recherche avec DataFrame (O(n))    : {temps_lin * 1000:.4f} ms")
    print("Choix : L'indexation dans un dictionnaire évite de parcourir les 20 000 lignes à chaque requête.")


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    start_time = time.perf_counter()

    df_cat, df_ml, df_baobab, df_ci = charger_donnees()
    analyser_marche(df_cat, df_ml, df_baobab, df_ci)
    calculer_panier(df_cat, df_ml, df_baobab, df_ci)
    analyser_historique()
    mesurer_complexite()

    end_time = time.perf_counter()
    print(f"\n✅ Exécution terminée en {end_time - start_time:.2f} secondes.")
    print("📁 Résultats sauvegardés dans le dossier 'output/'")