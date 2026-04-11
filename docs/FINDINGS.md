# Reverse Engineering SMU Granite Ridge — Résultats

**Plateforme :** AMD Ryzen 9 9800X3D (Zen 5, family 0x1A model 0x44)  
**Noyau :** 6.19.11-1-cachyos | **SMU version :** 98.75.0

---

## 1. Mailbox — Adresses (source : SSDT1)

| Mailbox | MSG (Cmd) | RSP (Statut) | ARG0 (Données) | Usage |
|---------|-----------|--------------|----------------|-------|
| **MP1** | 0x3B10530 | 0x3B1057C    | 0x3B109C4      | Power Limits (PPT, TDC, EDC) |
| **RSMU**| 0x3B10524 | 0x3B10570    | 0x3B10A40      | Tables & Telemetry |

---

## 2. Driver `gnr-smu` (Maison)

Driver noyau natif développé pour Granite Ridge :
- **Exclusivité :** Mutex garantissant un accès unique pour éviter les crashs bus SMN.
- **Rafraîchissement :** Automatique via `smn_write(0x05)` à chaque lecture sur `/dev/gnr_smu`.
- **Accès Mémoire :** Mapping via `memremap` de la zone DRAM dédiée à la PM Table.

---

## 3. PM Table — Cartographie (v0x620105)

Accès via RSMU MSG `0x04` (adresse) et `0x05` (transfert).  
Taille : `0x724` octets.

| Offset (Hex) | Signification | Unité |
|--------------|---------------|-------|
| 0x008        | PPT Limit     | Watt  |
| 0x050        | Package Power | Watt  |
| 0x4D4 - 0x4F0| Vcore (C0-C7) | Volt  |
| 0x4F4 - 0x510| Temp (C0-C7)  | °C    |
| 0x514 - 0x530| Freq (C0-C7)  | GHz   |
| 0x5D4 - 0x5F0| Boost Limit   | GHz   |

---

## 4. Message IDs — Table de commande

### 4a. Power Limits (MP1)
- **0x3E :** Set PPT Limit (mW)
- **0x3C :** Set TDC Limit (mA)
- **0x3D :** Set EDC Limit (mA)

### 4b. Curve Optimizer (MP1)
- **0x50 à 0x57 :** Contrôle par cœur (C0 à C7).
- **Format ARG0 :** Entier 32-bit signé (ex: -30 = `0xFFFFFFE2`).

---

## 5. ⚠ Pièges documentés

1.  **MSG 0x10 (MP1) :** Provoque une **perte immédiate d'affichage** (GPU Power Gate).
2.  **`monitor_cpu -f` :** Incompatible avec Granite Ridge. Provoque un **crash GFX** (écran vert/noir).
3.  **Probing aveugle :** Ne jamais tester les IDs 0x03-0x0D sur MP1 (risque de crash DMA).
EOF
,file_path: