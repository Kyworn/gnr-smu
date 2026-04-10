# Snapshot Complet — État BIOS Default Post-Reboot

**Date :** 2026-04-11 00:26 CEST | Uptime : 7 min (fresh reboot)  
**Kernel :** 6.19.11-1-cachyos | **BIOS :** ASRock B65IRW v4.10  

---

## Identification CPU

| Champ | Valeur |
|-------|--------|
| Modèle | AMD Ryzen 7 9800X3D 8-Core Processor |
| Family/Model | 26 / 68 (0x1A / 0x44) — Zen 5 Granite Ridge |
| Cores / Threads | 8 cores / 16 threads (SMT) |
| Min freq | 624.476 MHz |
| Max freq | 5455.945 MHz |
| L1d / L1i | 384 KiB / 256 KiB (8 instances) |
| L2 | 8 MiB (8 instances) |
| L3 (V-Cache) | **96 MiB** (1 instance) |
| NUMA | 1 node (0-15) |
| Virtualisation | AMD-V |
| ISA notable | AVX512F/DQ/BW/VL, AVX512_BF16, SHA_NI, VAES |

## RAM

| Slot | Modèle | Type | Speed | Configured | Voltage |
|------|--------|------|-------|------------|---------|
| DIMM A | G.Skill F5-6000J3038F16G | DDR5 Unbuffered | 4800 MT/s | **6000 MT/s** (XMP) | 1.1V |
| DIMM B | G.Skill F5-6000J3038F16G | DDR5 Unbuffered | 4800 MT/s | **6000 MT/s** (XMP) | 1.1V |
| Total | 32 GiB | | | | |

## PCI Root Complex (tunnel SMN)

```
00:00.0  AMD Raphael/Granite Ridge Root Complex [1022:14d8]
         → SMN addr : offset PCI 0xB8 (DWORD)
         → SMN data : offset PCI 0xBC (DWORD)
```

## amd-pstate-epp (CPUFreq)

| Paramètre | Valeur |
|-----------|--------|
| governor | performance |
| energy_performance_preference | performance |
| scaling_min_freq | 2 990 910 Hz (2990 MHz) |
| scaling_max_freq | 5 455 945 Hz (5455 MHz) |
| amd_pstate_highest_perf | 166 (CPPC max abstract perf) |
| amd_pstate_lowest_nonlinear_freq | 2 990 910 Hz |
| hw_prefcore | enabled |
| prefcore_ranking cpu0 | 181 |
| prefcore_ranking cpu4 | 191 ← preferred core |
| boost | 1 (activé) |

## MSR P-States

| P-state | Raw | Enabled | Note |
|---------|-----|---------|------|
| P0 (MSR C0010064) | 0x800000004BF243AC | oui | Boost |
| P1 (MSR C0010065) | 0x80000000479E4258 | oui | Base |
| P2–P7 | 0x0 | non | Inutilisés |
| MSR_PSTATE_CUR_LIM | 0x10 | — | MaxPstate=1, HwLimit=P0 |
| MSR_PSTATE_CTL | 0x0 | — | P-state cible = P0 |

## RAPL (Energy Reporting)

| Registre | Valeur |
|----------|--------|
| RAPL_PWR_UNIT (0xC0010299) | 0xA1000 |
| PowerUnit | 2^0 = 1 W/LSB (1000 mW/LSB) |
| EnergyUnit | 2^-16 J = 15.259 µJ/LSB |
| TimeUnit | 2^-10 s |
| PKG_ENERGY au reboot+7min | 0x466E603F → **18 030 J** (~43W avg) |
| RAPL powercap package-0 | **disabled** (enabled=0) |

Note : RAPL désactivé via powercap → ne pas utiliser `/sys/class/powercap` pour mesurer.  
Utiliser `turbostat` (APERF/MPERF) à la place.

## Températures (idle, Brave fermé)

| Capteur | Valeur | Source |
|---------|--------|--------|
| Tctl (CPU dié) | 50.0°C | k10temp |
| Tccd1 | 38.8–42.5°C | k10temp |
| RAM slot A | 44.0°C | spd5118 |
| RAM slot B | 42.75°C | spd5118 |
| NVMe 0 (6b00) | 62.9°C | nvme |
| NVMe 1 (6e00) | 55.9°C | nvme |
| GPU edge (iGPU) | 46.0°C | amdgpu |
| WiFi (MT7921) | 54.0°C | mt7921 |

## Tensions (hwmon)

| Rail | Valeur | Source |
|------|--------|--------|
| vddgfx (iGPU) | **1209 mV** | amdgpu hwmon |
| vddnb (NorthBridge/SoC) | **945 mV** | amdgpu hwmon |
| GPU sclk | 600 MHz (idle) | amdgpu hwmon |

Note : VCC core CPU (SVI3 VDDCR_CPU) non exposé via hwmon sur Zen 5.  
Les adresses SMN SVI3 classiques (0xE0080, 0xE00A0) retournent 0xFFFFFFFF → pas mappées.

## iGPU

| Param | Valeur |
|-------|--------|
| sclk | 600 MHz (idle) |
| PPT GPU | 10 mW (idle) |

## SMU MP1

| Info | Valeur |
|------|--------|
| Version | **98.75.0** (raw 0x00624B00) |
| Mailbox MSG | 0x3B10530 |
| Mailbox RSP | 0x3B1057C |
| Mailbox ARG0 | 0x3B109C4 |
| ARG1-4 | 0x3B109C8 / CC / D0 / D4 |

### Registres SMN non-nuls au repos (zone 0x3B10500-0x3B10600)

| Adresse | Valeur | Interprétation |
|---------|--------|----------------|
| 0x3B10504 | 0x08 | SMU version major (8) |
| 0x3B10508 | 0x16 | SMU version minor (22) |
| 0x3B1050C | 0x06 | SMU version patch (6) → **8.22.6** via registres statiques |
| 0x3B10530 | 0x01 | MSG = 1 (dernière cmd TestMessage) |
| 0x3B1054C | 0x01 | autre RSP ? |
| 0x3B10564 | 0x01 | autre RSP ? |
| 0x3B10570 | 0x01 | status |
| 0x3B10574 | 0x01 | RSP mailbox alternatif (rejette les cmds power) |
| 0x3B1057C | 0x01 | RSP mailbox principal ✓ |
| 0x3B10994 | **0x258 = 600** | Fréq min CPU en MHz ? |
| 0x3B10998 | 0x01 | status |
| 0x3B1099C | 0x01 | status |

### Découverte MSG IDs 0x00–0x0D

| MSG | RSP | ARG0_ret | Interprétation |
|-----|-----|----------|----------------|
| 0x01 | 0x01 ✓ | 0x01 | TestMessage |
| 0x02 | 0x01 ✓ | 0x00624B00 | GetSmuVersion → 98.75.0 |
| 0x03 | 0x01 ✓ | 0x00 | ? |
| 0x04 | 0xFD ✗ | 0x00 | Rejeté |
| 0x05 | 0x01 ✓ | 0x00 | ? |
| 0x06 | 0x01 ✓ | 0x00 | ? |
| 0x07 | 0x01 ✓ | 0x00 | ? |
| 0x08 | 0x01 ✓ | 0x00 | ? |
| 0x09 | 0xFD ✗ | 0x00 | Rejeté |
| 0x0A | 0x01 ✓ | 0x00 | ? |
| 0x0B | 0xFF  | 0x00 | Erreur inconnue |
| 0x0C | 0x01 ✓ | 0x00 | ? (GetPMTableVersion ?) |
| 0x0D | 0x01 ✓ | **0x20444D41 = "AMD "** | Signature ? |
| 0x3C | 0x01 ✓ | — | SetTDCLimit (mA) |
| 0x3D | 0x01 ✓ | — | SetEDCLimit (mA) |
| 0x3E | 0x01 ✓ | — | SetPPTLimit (mW) |
| 0x3F | 0x01 ✓ | — | SetTjMax (°C) |
| 0x4F | 0x01 ✓ | — | SetSustainedPwrLimit (mW) |
| 0x5F | 0x01 ✓ | — | SetSlowPPTLimit (mW) |

## Turbostat (idle système, Brave actif ~73% CPU)

| Métrique | Valeur |
|----------|--------|
| Bzy_MHz avg | 5220–5392 MHz |
| PkgWatt | 31–103 W (variable selon charge Brave) |
| LLC%hit | ~77–81% |
| IPC | ~0.84–0.94 |
| C3% (idle) | ~70–80% au repos |

## Throttle Reason MSR (0xC0010292)

Raw = 0x104004189 — **registre sticky** (historique depuis boot) :
- bit0: PROCHOT_VID
- bit3: VRM_HOT  
- bit7: PROCHOT_CPUPWR
- bit8: PROCHOT_SOCPWR

⚠ Ces bits sont probablement des résidus de l'épisode PPT=0mW de la session précédente (avant le reboot). À surveiller en conditions normales.

## Restore / Recovery

```bash
# Restore limites BIOS estimées
sudo python3 ~/gnr-smu/smu_send.py reset
# = PPT 162W + TDC 160A + EDC 220A

# Si CPU reste à 606 MHz après reset → reboot (tout est 100% volatile)
sudo reboot
```

## Valeurs BIOS par défaut (estimées)

| Limite | Valeur | Base de calcul |
|--------|--------|----------------|
| PPT | ~162W | 1.35 × TDP 120W |
| TDC | ~160A | Typique ASRock B650I + PBO |
| EDC | ~220A | Typique Zen 5 |
| TjMax | 85°C | PBO configuré manuellement (BIOS) |
| SlowPPT | ~88W | ~0.55 × PPT (typique STAPM) |

⚠ Ces valeurs ne sont **pas lisibles** via mailbox (pas de GetPPTLimit connu).

## ⚠ Pièges documentés

1. **`ppt 0` = 0 mW = throttle total** → CPU bloqué à 606 MHz. NE PAS FAIRE.
2. **`/proc/cpuinfo "cpu MHz"` est FAUX** sur amd-pstate-epp (affiche 606 même à 5 GHz).
3. **`turbostat Bzy_MHz` = VRAI** (APERF/MPERF hardware).
4. **7z est cache-bound** sur 9800X3D (96MB V-Cache) → pas sensible au PPT.
5. **stress-ng matrixprod aussi cache-bound** sur ce CPU.
6. **RAPL powercap désactivé** → ne pas utiliser `/sys/class/powercap`.
7. **Reboot = récupération totale** (SMU 100% volatile).
8. **Brave en fond** fausse les mesures (jusqu'à 73% CPU / 103W).
