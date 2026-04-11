#include <stdio.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>

// Granite Ridge SMN Addresses
#define SMN_ADDR_REG 0xB8
#define SMN_DATA_REG 0xBC

// Pour simplifier, on utilise /dev/port pour accéder aux registres I/O 
// (plus simple que UIO pour un premier test, mais nécessite root)
// Si c'est trop restrictif, on basculera sur UIO.

int main() {
    int fd = open("/dev/port", O_RDWR);
    if (fd < 0) {
        perror("Ouvrir /dev/port a échoué. Es-tu root ?");
        return 1;
    }

    // Exemple : Lire la version SMU (ID 0x02) via les registres SMN
    // Cette partie nécessite de manipuler les ports PCI de manière précise.
    // Pour l'instant, on se contente de valider l'accès.
    printf("Accès aux registres I/O opérationnel.\n");
    
    close(fd);
    return 0;
}
