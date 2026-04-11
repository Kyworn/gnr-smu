# Liste des tâches — GNR-SMU

## Driver `gnr_smu.c`

- [x] **IOCTL Implementation** — `GNR_SMU_IOCTL_SEND` implémenté (`_IOWR('G', 0x01, struct gnr_smu_msg)`)
- [x] **Safety Guard** — Whitelist MP1 : seuls les IDs confirmés sont acceptés (0x01, 0x02, 0x3C-0x3F, 0x4E-0x4F, 0x5F-0x61, 0x50-0x57)
- [x] **Data Integrity** — Double-read : `refresh_pm_table()` avant chaque lecture, `kmalloc` au lieu de VLA stack
- [x] **dram_base 64-bit** — `addr_lo | (addr_hi << 32)` (ARG0 + ARG1), plus de troncature
- [x] **RSP polling** — `usleep_range` + timeout `jiffies` au lieu de `msleep(20)` aveugle
- [x] **RSP clear** — `smn_write(rsp_reg, 0)` avant chaque envoi
- [ ] **Automatic Refresh Cache** — Ajouter un `kthread` ou `timer` pour refresh périodique toutes les Ns sans attendre une lecture

## Outils

- [x] **GUI double-read** — Réouverture du fichier entre les deux lectures (plus de `ppos` bloqué)
- [x] **GUI struct size** — `<457f` / `data1[:1828]` (était `466f`/1864 qui débordait)
- [ ] **Frequency Mapping** — Valider que `CORE_FREQ[i] * 1000.0` donne bien des MHz (table en GHz → ×1000 = MHz ✓ à confirmer live)
- [ ] **GUI PPT Slider** — Ajouter un slider pour régler le PPT via l'ioctl depuis la GUI

## Recherche

- [ ] **Curve Optimizer (0x50-0x57)** — Valider le format de l'argument (int32 signé ? plage -30/+30 ?)
- [ ] **IDs 0x58-0x5D** — Identifier ce que font ces 6 IDs séquentiels après les 8 cores
- [ ] **MSG 0x6B** — Tester avec différents ARG (0, 1, 2…) pour voir si c'est GetTableDramAddress sur MP1
- [ ] **HSMP** — Explorer si l'interface HSMP offre des données supplémentaires (GetSocketPowerLimit, etc.)
- [ ] **PM Table taille réelle** — 0x724 est estimé. Vérifier si la table continue au-delà (version 0x620105)

## Compilation après fix

```bash
cd ~/gnr-smu/driver
make clean && make
sudo rmmod gnr_smu
sudo insmod gnr_smu.ko
dmesg | tail -5
```
