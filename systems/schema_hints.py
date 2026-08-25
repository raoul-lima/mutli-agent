"""Règles métier SQL partagées par l'agent SQL et le fast path."""

SQL_COLUMN_GLOSSARY = """\
Correspondances obligatoires (n'inventez pas d'autres noms) :
- Nom du client → `customers.nom_societe` ou `customers.nom_contact` ; \
PAS `nom`, `prenom`, `nom_client`, `name` sur `customers`.
- `nom` et `prenom` existent sur `employees` uniquement, pas sur `customers`.
- Montant d'une commande → `orders.montant_ttc_mga` (TTC) ou `orders.montant_total_ht_mga` (HT) ; \
PAS `montant_total`, `total`, `amount`.
- Produit commandé → `orders.produit` (libellé catégorie) ; détail produit → table `products`."""

SQL_BUSINESS_HINTS = f"""\
{SQL_COLUMN_GLOSSARY}
- `orders.produit` contient le libellé de **catégorie** (« Haricot Sec », « Riz Local », \
« Niébé »), pas l'`id_produit`. Ne filtrez jamais `orders.produit = 'PRD-…'`.
  Pour un produit par id (ex. `PRD-HAR-004`), joignez `products` : \
`JOIN products p ON p.categorie = o.produit WHERE p.id_produit = 'PRD-HAR-004'`.
- Les identifiants sont textuels (« CLI-001 », « PRD-RIZ-001 »). Montants en ariary (MGA).
- `sales.id_commande` n'a pas de FK vers `orders` : jointure risquée, préférez filtrer \
chaque table séparément.
- Statuts commande courants : « Livrée », « En cours de livraison », « Confirmée », \
« En attente de paiement ».
- Une seule requête SELECT ; copiez les identifiants de colonnes **à l'identique** depuis \
le schéma."""
