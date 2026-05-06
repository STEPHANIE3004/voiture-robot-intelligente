/*
 * main.c - Simulation de la voiture robot intelligente
 * Auteure : Vanelle Stephanie MANGOUA DJOUSSEU
 */
#include "../include/robot.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int main(void) {
    srand((unsigned)time(NULL));
    Robot robot;
    robot_init(&robot);

    printf("\n=== SIMULATION VOITURE ROBOT (20 cycles) ===\n\n");
    for (int i = 0; i < 20; i++) {
        printf("--- Cycle %02d ---\n", i + 1);
        loop_principal(&robot);
        printf("  Etat courant : %d | Distance : %d cm | Evitements : %u\n\n",
               robot.etat, robot.distance_obstacle, robot.nb_evitements);
    }

    printf("=== FIN SIMULATION ===\n");
    printf("Total evitements : %u\n", robot.nb_evitements);
    return 0;
}
