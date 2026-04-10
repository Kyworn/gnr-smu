# Cartographie de la PM Table — AMD Granite Ridge (v0x620105)

D'après le dump float32 brut du 11 avril 2026.

| Offset (Hex) | Valeur Typique | Signification Probable |
|--------------|----------------|-------------------------|
| 0x008        | 162.0          | **PPT Limit (W)**       |
| 0x00C        | 35.8           | Package Temperature (°C)|
| 0x020        | 120.0          | **EDC Limit (A)**       |
| 0x024        | 17.2           | SoC Temperature (°C)    |
| 0x028        | 85.0           | **TDC Limit (A)**       |
| 0x048        | 1.37           | Vcore Peak (V)          |
| 0x04C        | 1.21           | Vcore Average (V)       |
| 0x050        | 20.8           | Package Power (W)       |
| 0x0FC        | 180.0          | EDC Max ?               |
| 0x100        | 90.5           | TjMax Limit (°C)        |

### Données par Cœur (8 cœurs détectés) :

- **Températures par cœur :** Débutent à **0x4F4**
  - C0: 39.3°C, C1: 36.3°C, C2: 46.4°C, C3: 37.5°C...
- **Tensions par cœur :** Débutent à **0x4D4** (autour de 1.17V - 1.20V)
- **Fréquences (C0 Residency / Boost) :** Débutent à **0x514** (5.16 GHz, 5.05 GHz...)

*Note : Cette table est la clé pour le monitoring temps réel sans passer par des outils propriétaires.*
