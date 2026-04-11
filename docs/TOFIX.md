# Liste des tâches à accomplir (TOFIX)

## 1. Driver `gnr_smu.c`
- [ ] **IOCTL Implementation:** Remplacer l'écriture par `echo` par des `ioctl` dédiés pour plus de sécurité.
- [ ] **Automatic Refresh:** Implémenter un système de cache dans le driver pour éviter les transferts mémoire (`MSG 0x05`) à chaque lecture.
- [ ] **Safety Guard:** Ajouter une liste blanche (whitelist) de messages SMU autorisés pour éviter d'envoyer des commandes comme `0x10`.
- [ ] **Data Integrity:** Implémenter le "Double-Read" au niveau du driver pour garantir des données coherentes.

## 2. Outils (Tools)
- [ ] **GUI Refinement:** Finir le parsing des données dans `monitor_gui.py` en le faisant pointer vers `/sys/kernel/debug/ryzen_smu/pm_table`.
- [ ] **Frequency Mapping:** Valider le format de fréquence stocké dans la table (les valeurs actuelles sont en GHz, vérifier si besoin de conversion MHz exacte).

## 3. Recherche
- [ ] **HSMP Discovery:** Explorer l'interface HSMP (High-Speed Management Port) pour voir si elle offre un meilleur accès à la télémétrie que la PM Table.
- [ ] **Curve Optimizer:** Valider la portée des offsets du Curve Optimizer (-30 à +30).
EOF
,file_path: