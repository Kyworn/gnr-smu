#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include "gnr_pm_table.h"

int main() {
    int fd = open("/sys/kernel/ryzen_smu_drv/pm_table", O_RDONLY);
    if (fd < 0) {
        perror("Failed to open pm_table");
        return 1;
    }

    PMTable_GNR_t table;
    if (read(fd, &table, sizeof(table)) < 0) {
        perror("Failed to read pm_table");
        close(fd);
        return 1;
    }

    printf("--- AMD Granite Ridge Telemetry (9800X3D) ---\n");
    printf("PPT Limit: %.2f W | Package Power: %.2f W\n", table.PPT_LIMIT, table.PACKAGE_POWER);
    printf("Vcore Peak: %.3f V | Avg: %.3f V\n", table.VCORE_PEAK, table.VCORE_AVG);
    printf("\n--- Core Telemetry ---\n");
    for (int i = 0; i < 8; i++) {
        printf("Core %d: %7.2f MHz (Limit: %7.2f MHz) | %5.3f V | %5.2f C\n", 
               i, table.CORE_FREQ[i] * 1000.0, table.CORE_BOOST_LIMIT[i] * 1000.0, 
               table.CORE_VOLTAGE[i], table.CORE_TEMP[i]);
    }

    close(fd);
    return 0;
}
