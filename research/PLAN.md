# Plan de décodage — suite 2026-07-30

Exécution autonome. Chaque phase finit par `python3 research/audit_map.py` (doit
sortir 0) puis un commit. Une phase qui ne conclut pas est écrite dans TOFIX.md
avec ce qui a été éliminé, pas abandonnée en silence.

## Phase 1 — EDC_VALUE
`d[63]` = limite EDC (180 A), aucune valeur live trouvée. `stress-ng --cpu` est
une charge entière : elle ne tire pas assez de courant. Sweep à 3 points —
idle / entier / AVX-512 (`--vecfp`) — et scorer chaque float sur la signature
attendue : bas au repos, monte avec la charge, monte **plus** en AVX qu'en
entier, ne dépasse jamais 180.

## Phase 2 — d[212], d[397-404], d[453]
Confirmés non-accumulateurs (plateau sous charge stable). Tester s'ils sont
proportionnels à la puissance instantanée : corréler contre d[20] (Package
Power) et d[17] (Core Power) à plusieurs niveaux de charge (1, 4, 8, 16
threads). Un ratio constant identifie l'unité.

## Phase 3 — les 90 index non documentés
Classer mécaniquement : zéro permanent / statique non-zéro / dynamique. Seuls
les dynamiques valent un décodage. Écrire des lignes pour tous, même "inconnu",
pour que la couverture soit honnête à 457.

## Phase 4 — offsets démentis
`d[220]`, `0x100`, `0x348`, `0x458`, `0x4A8/4AC`, `0x700/704`, `0x710`. On sait
ce qu'ils ne sont pas. Les profiler contre les axes connus (puissance, courant,
température, fréquence, résidence) pour trouver l'axe.

## Hors scope
- MSG 0x58-0x6F : MP1 gèle, RSMU refuse. Mort sur ce firmware, pas de sweep. C'est la plage que docs/FINDINGS.md a testée, et celle que tools/hwgate.py bloque — ne pas la rétrécir.
- HSMP : demande une bascule BIOS, pas faisable sans reboot utilisateur.
