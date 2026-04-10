#ifndef GNR_PM_TABLE_H
#define GNR_PM_TABLE_H

#include <stdint.h>

typedef struct {
    uint32_t reserve0[2];           // 0x000
    float PPT_LIMIT;                // 0x008
    float PACKAGE_TEMP;             // 0x00C
    uint32_t reserve1[4];           // 0x010
    float EDC_LIMIT;                // 0x020
    float SOC_TEMP;                 // 0x024
    float TDC_LIMIT;                // 0x028
    float reserve2;                 // 0x02C
    uint32_t reserve3[4];           // 0x030
    float reserve4;                 // 0x040
    float reserve5;                 // 0x044
    float VCORE_PEAK;               // 0x048
    float VCORE_AVG;                // 0x04C
    float PACKAGE_POWER;            // 0x050
    // ... padding jusqu'au coeur ...
    uint32_t reserve_mid[288];      // 0x054 -> 0x4D4
    
    float CORE_VOLTAGE[8];          // 0x4D4
    float CORE_TEMP[8];             // 0x4F4
    float CORE_FREQ[8];             // 0x514 (en GHz)
    uint32_t reserve_end[40];
    float CORE_BOOST_LIMIT[8];      // 0x5D4 (en GHz)
} __attribute__((packed)) PMTable_GNR_t;

#endif
