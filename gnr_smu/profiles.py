#!/usr/bin/env python3
"""Hardware profiles for GNR-SMU telemetry tools.

Telemetry layouts are keyed by PM-table version, byte size and physical
core count. Extracted verbatim from tools/hwgate.py; only the module
header changed.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HardwareProfile:
    name: str
    cpu_model: str
    pm_version: int
    table_size: int
    cores: int
    core_power: int
    core_voltage: int
    core_temp: int
    core_frequency: Optional[int]
    core_fit: Optional[int]
    core_activity: Optional[int]
    core_c0: Optional[int]
    core_cc1: Optional[int]
    core_cc6: int
    core_boost_limit: Optional[int]
    boost_limit_confident: bool
    # CCD-adjacent telemetry.  L3 temperature lanes are exposed only after a
    # cache-thrash-vs-ALU comparison demonstrates cache-specific coupling.
    # 2026-08-25: d[589]/d[590] and d[591]/d[592] were checked for CCD
    # selectivity the same way d[595]/d[596] were (busy-loop load pinned to
    # CCD0 only, then CCD1 only). Unlike d[595]/d[596], both lanes of each
    # pair rose almost identically regardless of which CCD was loaded
    # (+3.68/+3.14 for CCD0 load vs +3.84/+3.69 for CCD1 load) — they are
    # NOT per-CCD values and must not be presented as "CCDx power" in the
    # GUI. Kept here only as raw research fields.
    ccd_power_candidate: Optional[int]
    ccd_vddm_candidate: Optional[int]
    ccd_l3_temperature: Optional[int]
    ccd_candidate_count: int
    ppt_msg: int
    tdc_msg: int
    edc_msg: int
    stock_ppt: int
    stock_tdc: int
    stock_edc: int
    co_mode: str
    # Legacy frontend ceilings for the three power limits, in the same units as
    # stock_*. They are not a validated write envelope. The wire format can represent
    # the much broader uint32 milli-unit range, which is also not a safety claim and is
    # deliberately not modelled as an allowed range. The separate *_write_bounds
    # tuples are the evidence-backed inclusive ranges accepted by the centralized
    # payload gate; None means no power-limit write is established.
    # Raw SMN mailbox addresses, for the research tools that drive the mailbox through
    # setpci instead of the driver. Measured on the 9800X3D; a profile that leaves them
    # empty makes those tools refuse rather than poke the same registers on a part
    # where they may be something else entirely.
    #   (MSG, RSP, ARG0)
    mp1_smn: tuple = ()
    rsmu_smn: tuple = ()
    max_ppt: int = 0
    max_tdc: int = 0
    max_edc: int = 0
    ppt_write_bounds: Optional[tuple] = None
    tdc_write_bounds: Optional[tuple] = None
    edc_write_bounds: Optional[tuple] = None
    co_msg: int = 0
    # Granite Ridge exposes the active per-core Curve Optimizer value through
    # the read-only RSMU GetDldoPsmMargin command.  This is separate from the
    # profile-specific MP1 write path above.
    co_get_msg: int = 0
    # No SMU command of any kind is validated on a profile with this False:
    # neither MP1 writes nor the conceptually-read-only RSMU queries (the
    # query protocol writes smu_args/rsmu_cmd first).  A read-only query and
    # a write are different capabilities; a future revision may split this
    # into allow_smu_writes / allow_rsmu_queries, but today both stay False
    # together and no new logic should assume one implies the other.
    allow_smu_writes: bool = False
    ccd_shared_temperature: Optional[int] = None
    edc_value: Optional[int] = None
    # Per-core blocks are 8-wide SMU slots on every part measured so far, but
    # the active cores are not always slots 0..N-1: the 5600X fuses off slots
    # 2-3, so Linux core 2 lives in SMU slot 4.  `core_slots` maps Linux core
    # index -> SMU slot; empty means the identity mapping (all Granite Ridge
    # parts).  Every `base + core` site must go through slot()/lane() instead.
    core_slots: tuple = ()
    # Effective (sleep-aware) per-core frequency block base, or None when not
    # mapped.  Granite Ridge has no such block; Vermeer 0x380905 has d[220].
    core_eff_frequency: Optional[int] = None
    # Global (non-per-core) telemetry: ((canonical_name, float_index), ...).
    # A name absent from the map is unsupported on that profile and every
    # front-end must hide it rather than read another part's offset.  This
    # replaces the old pm_version branches scattered across the tools.
    globals_map: tuple = ()
    # Blocks whose identification is HIGH (load-response + canonical layout
    # order) but not independently cross-validated against another sensor.
    # Front-ends must present these as high-confidence, not confirmed.
    # Named by HardwareProfile field, e.g. "core_power".
    provisional_blocks: tuple = ()
    # Same, for global names (e.g. "fclk").  A name here is HIGH even when
    # its offset is published for exactly this PM-table version: coherent
    # values alone are not an independent measurement.
    provisional_globals: tuple = ()
    # Display family, e.g. "Granite Ridge (Zen 5)" / "Vermeer (Zen 3)".
    arch: str = "Granite Ridge (Zen 5)"

    @property
    def float_count(self):
        return self.table_size // 4

    def slot(self, core):
        """SMU slot for a Linux physical-core index."""
        if not 0 <= core < self.cores:
            raise ValueError(f"core {core} outside 0..{self.cores - 1}")
        if self.core_slots:
            if len(self.core_slots) != self.cores:
                raise ValueError(
                    f"{self.name}: {len(self.core_slots)} slots for "
                    f"{self.cores} cores")
            return self.core_slots[core]
        return core

    def lane(self, base, core):
        """Float index of `core`'s lane in the per-core block at `base`."""
        if base is None:
            raise ValueError(f"{self.name}: block is not mapped for this profile")
        return base + self.slot(core)

    def lane_values(self, values, base):
        """Per-core values (Linux-core order) from the block at `base`."""
        if base is None:
            raise ValueError(f"{self.name}: block is not mapped for this profile")
        return [values[base + self.slot(core)] for core in range(self.cores)]

    def gidx(self, name):
        """Float index of a global telemetry name, or None when unmapped."""
        for key, idx in self.globals_map:
            if key == name:
                return idx
        return None

    def confidence(self, block):
        """'confirmed', 'high', 'candidate', or None for a block/global."""
        if block.endswith("_candidate"):
            return ("candidate" if getattr(self, block, None) is not None
                    else None)
        if block == "core_boost_limit" and not self.boost_limit_confident:
            return "candidate" if self.core_boost_limit is not None else None
        if block == "edc_value":
            return "candidate" if self.edc_value is not None else None
        if block in self.provisional_blocks or block in self.provisional_globals:
            return "high"
        if block in GLOBAL_FIELD_NAMES:
            return "confirmed" if self.gidx(block) is not None else None
        base = getattr(self, block, None)
        return "confirmed" if base is not None else None

    def fused_slots(self):
        """SMU slots with no Linux core on them (empty when identity-mapped)."""
        if not self.core_slots:
            return ()
        width = max(self.core_slots) + 1
        return tuple(s for s in range(width) if s not in self.core_slots)


# Every canonical global-telemetry name a front-end may request.  A profile
# map key outside this set is a typo, not an unsupported field; a front-end
# request outside it would silently become "--".  validate_profile_globals()
# (run by the self-test and the unit tests) tells the two apart.
GLOBAL_FIELD_NAMES = frozenset({
    "ppt_limit", "ppt_value",
    "tdc_limit", "tdc_value",
    "thm_limit", "tctl",
    "edc_limit",
    "fclk", "uclk", "mclk",
    "vid_limit", "vid",
    "vcore_telemetry_peak", "vcore_telemetry_average",
    "vdd_misc", "vsoc",
    "vddio_mem_voltage", "vddcr_cpu_vid",
    "vddg_iod", "vddg_ccd", "vddp",
    "socket_power", "cpu_power", "pkg_power",
    "soc_power", "vddio_power", "vdd18_power",
    "hotspot_temp",
    "soc_telemetry", "soc_telemetry_metric",
    "igpu_power", "igpu_clock",
    "slow_temp_0", "slow_temp_1",
    "pkg_energy",
    "fit_metric",
})


def validate_profile_globals(profile):
    """Return globals_map keys that are not canonical names (typos)."""
    return [key for key, _ in profile.globals_map
            if key not in GLOBAL_FIELD_NAMES]


# Global telemetry whose identities are established on both Granite Ridge
# profiles. Part-specific rails remain separate: equal indices do not prove
# equal meanings across different PM-table versions.
_GNR_COMMON_GLOBALS = (
    ("ppt_limit", 2), ("ppt_value", 3),
    ("tdc_limit", 8), ("tdc_value", 9),
    ("thm_limit", 10), ("tctl", 11),
    ("edc_limit", 63),
    ("fclk", 71), ("uclk", 75), ("mclk", 79),
)

_GNR_9950X3D_GLOBALS = _GNR_COMMON_GLOBALS + (
    ("vid_limit", 18), ("vid", 19),
    ("vdd_misc", 58),
    ("vsoc", 83),
    ("vddg_iod", 259), ("vddg_ccd", 261), ("vddp", 269),
)

_GNR_9800X3D_GLOBALS = _GNR_COMMON_GLOBALS + (
    ("vcore_telemetry_peak", 18),
    ("vcore_telemetry_average", 19),
    ("pkg_power", 20),
    ("soc_power", 21),
    ("vddio_mem_voltage", 58),
    ("vsoc", 83),
    ("vddcr_cpu_vid", 269),
    ("hotspot_temp", 270),
    ("igpu_power", 107),
    ("igpu_clock", 108),
)

PROFILES = {
    (0x620105, 1828, 8): HardwareProfile(
        "AMD Ryzen 7 9800X3D", "AMD Ryzen 7 9800X3D", 0x620105, 1828, 8,
        core_power=333, core_voltage=309, core_temp=317, core_frequency=325,
        core_fit=None, core_activity=None, core_c0=341, core_cc1=349,
        core_cc6=357, core_boost_limit=373, boost_limit_confident=True,
        ccd_power_candidate=None, ccd_vddm_candidate=None,
        # 2026-09-10: a shared 64 MiB working set (fits the 96 MiB L3, exceeds
        # private L2) raised d[448] +6.97 K while core average rose +4.83 K.
        # At nearly the same final core/Tccd temperatures, an ALU-only control
        # raised d[448] only +1.05 K.  This isolates real L3-traffic coupling.
        ccd_l3_temperature=448, ccd_candidate_count=1,
        # Measured by read-back: 0x3C moves d[8] (TDC), while 0x3D moves d[63] (EDC).
        ppt_msg=0x3E, tdc_msg=0x3C, edc_msg=0x3D,
        stock_ppt=162, stock_tdc=120, stock_edc=180,
        mp1_smn=(0x3B10530, 0x3B1057C, 0x3B109C4),
        rsmu_smn=(0x3B10524, 0x3B10570, 0x3B10A40),
        max_ppt=250, max_tdc=200, max_edc=250,
        # probe_tdc_edc.py recorded successful writes at 151 W / 111 A and
        # restoration to the measured stock limits.  No broader range is claimed.
        ppt_write_bounds=(151, 162),
        tdc_write_bounds=(111, 120),
        edc_write_bounds=(111, 180),
        co_mode="legacy_per_message",
        co_get_msg=0xD5,
        allow_smu_writes=True,
        globals_map=_GNR_9800X3D_GLOBALS,
        provisional_blocks=("core_power", "core_cc6", "ccd_l3_temperature"),
        provisional_globals=("soc_power", "vddio_mem_voltage", "vsoc",
                             "vddcr_cpu_vid"),
    ),
    (0x620205, 2452, 16): HardwareProfile(
        "AMD Ryzen 9 9950X3D", "AMD Ryzen 9 9950X3D", 0x620205, 2452, 16,
        core_power=301, core_voltage=317, core_temp=333, core_frequency=None,
        core_fit=349, core_activity=365, core_c0=381, core_cc1=397,
        core_cc6=413, core_boost_limit=445, boost_limit_confident=False,
        # Low-confidence candidates from the 0x620205 table.  Keep these
        # explicitly separate from validated fields until correlated traces
        # establish their identities.
        #
        # 2026-08-25, research/granite_ridge/l3/recheck_l3.py: loading CCD0 only raises d[595]
        # (+13.8 K over baseline) far more than d[596] (+6.5 K), and loading
        # CCD1 only reverses that — d[595]/d[596] are CCD-selective. d[611]/
        # d[612] move together almost identically regardless of which CCD is
        # loaded (shared/non-selective).
        #
        # 2026-08-25, research/granite_ridge/l3/l3_specificity.py: an ALU-only load and an
        # L3-cache-thrash load pinned to the same CCD were compared. Per K of
        # CCD-avg core-temp rise, the cache-thrash load moved every one of
        # these lanes 3-6x more than the ALU load did (e.g. d[595] rose x1.54
        # of the core-temp rise under cache-thrash vs only x0.43 under ALU
        # load) — suggestive of L3 coupling, but it was a single uncontrolled
        # run confounded by very different absolute core temperatures between
        # the two loads (ALU hit ~69 °C avg, cache-thrash only ~41 °C), and
        # cache-thrash also broke the earlier CCD-selectivity (d[596] rose
        # almost as much as d[595] despite only CCD0 being loaded). Not proof.
        #
        # 2026-08-25, research/granite_ridge/l3/l3_specificity_controlled.py: repeated the test
        # with the confound removed by throttling the ALU load (--cpu-load
        # duty cycling) until its CCD0-avg core-temp rise matched the
        # cache-thrash run's rise to within 0.44 K. At *matched* core-temp
        # rise, d[595]/d[596] still rose an extra +4.2 K / +7.9 K under
        # cache-thrash vs ALU — that excess cannot be explained by core
        # heating, and is real evidence of L3-traffic coupling for this pair.
        # d[611]/d[612] did the *opposite* (-2.7 K vs ALU at matched core
        # temp), ruling out an L3-cache identity for that pair; it tracks
        # something else (fabric/package-level heat, not cache traffic).
        # Single run so far; kept named for what is confirmed either way.
        ccd_shared_temperature=611,
        ccd_power_candidate=589, ccd_vddm_candidate=591,
        ccd_l3_temperature=595, ccd_candidate_count=2,
        # ZenStates-Core's Granite Ridge profile inherits the Zen 4 MP1 command
        # table: Fast/PPT=0x3E, TDC=0x3C, EDC=0x3D, per-core DLDO margin=0x35.
        ppt_msg=0x3E, tdc_msg=0x3C, edc_msg=0x3D,
        stock_ppt=200, stock_tdc=160, stock_edc=225,
        max_ppt=300, max_tdc=250, max_edc=300,
        # The repository records real-machine validation of these controls but no
        # exact altered values.  Only the exact measured stock/reset values form a
        # defensible envelope until the write/readback evidence is published.
        ppt_write_bounds=(200, 200),
        tdc_write_bounds=(160, 160),
        edc_write_bounds=(225, 225),
        co_mode="packed_core_mask", co_msg=0x35,
        co_get_msg=0xD5,
        allow_smu_writes=True,
        globals_map=_GNR_9950X3D_GLOBALS + (
            ("fit_metric", 16),
            ("cpu_power", 20), ("soc_power", 21),
            ("vddio_power", 22), ("vdd18_power", 23),
            ("socket_power", 26),
        ),
        # d[64] sits right after EDC_LIMIT (d[63]) and behaves like the
        # missing EDC_VALUE: idle ~7 A, rises to ~128 A under all-core load,
        # and stays above the same run's TDC current (d[9], ~108 A) as a
        # real peak-current reading should (research/granite_ridge/edc/recheck_edc.py).
        edc_value=64,
    ),
    # AMD Ryzen 5 9600X / Granite Ridge (Zen 5).  Shares PM table 0x620105 /
    # 1828 bytes with the 9800X3D, but only has 6 physical cores. A dump
    # (my_9600x/, 2026-09-12) shows detect_active_slots() reading SMU slots
    # (0,1,2,3,6,7) live and (4,5) fused off, identically at idle and under
    # all-core load — hence core_slots below, verified against the live table
    # at detection time the same way the 5600X's is (_fused_layout_matches).
    #
    # Telemetry-only for now: the per-core/global offsets are inherited from
    # the 9800X3D map on the strength of the identical (version, size), which
    # this project's own philosophy treats as one source, not independent
    # confirmation — hence provisional_blocks/provisional_globals cover
    # everything until cross-validated against k10temp/amdgpu/cpufreq on this
    # machine specifically (see docs/architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md).
    # No SMU write is validated on this part: stock PPT/TDC/EDC and message
    # IDs are intentionally left at 0 rather than assumed from the 9800X3D or
    # a published spec sheet, so every write path stays blocked.
    (0x620105, 1828, 6): HardwareProfile(
        "AMD Ryzen 5 9600X", "AMD Ryzen 5 9600X", 0x620105, 1828, 6,
        core_power=333, core_voltage=309, core_temp=317, core_frequency=325,
        core_fit=None, core_activity=None, core_c0=341, core_cc1=349,
        core_cc6=357, core_boost_limit=373, boost_limit_confident=False,
        ccd_power_candidate=None, ccd_vddm_candidate=None,
        # d[448] reads 49.7 C on the live machine, in the same range as
        # k10temp Tccd1 (52.5 C) and the per-core temps — same offset the
        # 9800X3D uses, inherited on the strength of the identical table
        # version/size. Not independently re-run here (no cache-thrash-vs-ALU
        # differential test on this chip yet), hence still provisional.
        ccd_l3_temperature=448, ccd_candidate_count=1,
        ppt_msg=0, tdc_msg=0, edc_msg=0,
        stock_ppt=0, stock_tdc=0, stock_edc=0,
        co_mode="unsupported",
        co_get_msg=0,
        allow_smu_writes=False,
        core_slots=(0, 1, 2, 3, 6, 7),
        globals_map=_GNR_9800X3D_GLOBALS,
        provisional_blocks=("core_power", "core_voltage", "core_temp",
                            "core_frequency", "core_c0", "core_cc1",
                            "core_cc6", "core_boost_limit",
                            "ccd_l3_temperature"),
        provisional_globals=tuple(k for k, _ in _GNR_9800X3D_GLOBALS),
    ),
    # AMD Ryzen 5 5600X / Vermeer (Zen 3).  Read-only: no SMU command is
    # validated on this part, so every write path stays blocked (see
    # docs/architectures/vermeer/VERMEER_5600X.md for the evidence behind each mapped block).
    #
    # Per-core blocks are 8 SMU slots wide with slots 2-3 fused off on the
    # validated machine, hence core_slots=(0, 1, 4, 5, 6, 7): Linux core 2
    # lives in SMU slot 4.  Which cores a 5600X fuses off depends on binning,
    # so the tuple is verified against the live table at detection time
    # (_fused_layout_matches) and any other layout refuses the profile.
    # The fused slots read 0.0 everywhere except CC6, where they read 100.0.
    # That looks like the firmware representation for inactive/non-present
    # core slots; it is not interpreted as a sleeping physical core.
    (0x380905, 1488, 6): HardwareProfile(
        "AMD Ryzen 5 5600X", "AMD Ryzen 5 5600X", 0x380905, 1488, 6,
        core_power=172, core_voltage=180, core_temp=188, core_frequency=212,
        core_fit=None, core_activity=None, core_c0=228, core_cc1=236,
        core_cc6=244, core_boost_limit=None, boost_limit_confident=False,
        ccd_power_candidate=None, ccd_vddm_candidate=None,
        ccd_l3_temperature=None, ccd_candidate_count=0,
        # No validated message IDs on Vermeer: 0 keeps the allowlist empty
        # (smu_message_supported() additionally refuses write-blocked
        # profiles outright).
        ppt_msg=0, tdc_msg=0, edc_msg=0,
        stock_ppt=0, stock_tdc=0, stock_edc=0,
        co_mode="unsupported",
        co_get_msg=0,
        allow_smu_writes=False,
        core_slots=(0, 1, 4, 5, 6, 7),
        core_eff_frequency=220,
        provisional_blocks=("core_power", "core_voltage"),
        # Phase 2: clocks/rails published for exactly 0x380905
        # (ZenStates-Core PowerTable.cs) with coherent values, plus package
        # power validated against RAPL.  Clocks/rails stay HIGH (no
        # independent Linux reference); socket power is CONFIRMED.
        # Tctl deliberately absent: no field shows sample-level coherence
        # with k10temp (see docs/architectures/vermeer/VERMEER_5600X.md).
        globals_map=(
            ("fclk", 48), ("uclk", 50), ("mclk", 51),
            ("vsoc", 45),
            ("vddp", 137), ("vddg_iod", 138), ("vddg_ccd", 139),
            ("socket_power", 1),
        ),
        provisional_globals=("fclk", "uclk", "mclk", "vsoc",
                             "vddp", "vddg_iod", "vddg_ccd"),
        arch="Vermeer (Zen 3)",
    ),
}
