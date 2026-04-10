# Reverse Engineering SMU Granite Ridge — Résultats

**Plateforme :** AMD Ryzen 9 9800X3D (Zen 5, family 0x1A model 0x44)  
**Carte mère :** ASRock B650I Lightning WiFi  
**BIOS analysé :** v4.10 (février 2026, 32MB) — `B65IRW_4.10.ROM`  
**Noyau :** 6.19.11-1-cachyos | **SMU version :** 98.75.0

---

## 1. Mailbox — Adresses (source : SSDT1 + ryzen_smu)

| Mailbox | MSG (Cmd) | RSP (Statut) | ARG0 (Données) | Usage |
|---------|-----------|--------------|----------------|-------|
| **MP1** | 0x3B10530 | 0x3B1057C    | 0x3B109C4      | Power Limits (PPT, TDC, EDC) |
| **RSMU**| 0x3B10524 | 0x3B10570    | 0x3B10A40      | Tables & Telemetry |

---

## 2. PM Table — Cartographie (v0x620105)

Accès via RSMU MSG `0x04` (adresse) et `0x05` (transfert).  
Taille : `0x724` octets. Format : `float32` Little Endian.

| Offset (Hex) | Signification | Unité |
|--------------|---------------|-------|
| 0x008        | PPT Limit     | Watt  |
| 0x00C        | Package Temp  | °C    |
| 0x020        | EDC Limit     | Ampère|
| 0x028        | TDC Limit     | Ampère|
| 0x048        | Vcore Peak    | Volt  |
| 0x04C        | Vcore Average | Volt  |
| 0x050        | Package Power | Watt  |
| 0x4D4 - 0x4F0| Vcore (C0-C7) | Volt  |
| 0x4F4 - 0x510| Temp (C0-C7)  | °C    |
| 0x514 - 0x530| Freq (C0-C7)  | GHz   |
| 0x5D4 - 0x5F0| Boost Limit   | GHz   |

---

## 3. Message IDs — Table de commande

### 3a. Power Limits (Mailbox MP1)
- **0x3E :** Set PPT Limit (mW)
- **0x3C :** Set TDC Limit (mA)
- **0x3D :** Set EDC Limit (mA)
- **0x3F :** Set TjMax (°C)

### 3b. Curve Optimizer (Mailbox MP1 - Suspicion forte)
- **0x50 à 0x57 :** Contrôle par cœur (C0 à C7).
- **Format ARG0 :** Entier 32-bit signé (ex: -30 = `0xFFFFFFE2`).
- **Statut :** Commandes acceptées (RSP=1), effets en cours de validation.

---

## 4. ⚠ Pièges et Dangers

1.  **MSG 0x10 (MP1) :** Provoque une **perte immédiate d'affichage** (GPU Power Gate). Reboot requis.
2.  **`monitor_cpu -f` :** Incompatible avec Granite Ridge. Provoque un **crash GFX** (écran vert/noir) dû à une structure mémoire erronée.
3.  **Probing aveugle :** Ne jamais tester les IDs 0x03-0x0D sur MP1 (risque de crash DMA).

---

## 5. Outils développés

- `smu_advanced.py` : Utilitaire Python pour envoyer des messages aux deux mailboxes.
- `gnr_monitor` : Moniteur C natif utilisant le driver `ryzen_smu` pour lire la télémétrie en temps réel.

---

## 6. Utilisation rapide

```bash
# Voir la télémétrie (Tensions, Watts, Freq, Temps)
sudo ./gnr_monitor

# Modifier le PPT à 85W
sudo python3 smu_advanced.py ppt 85

# Tester un undervolt de -20 sur le Coeur 0
sudo python3 smu_advanced.py raw --mb mp1 --msg 0x50 --arg 0xFFFFFFEC
```
