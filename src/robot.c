/*
 * robot.c - Firmware voiture robot intelligente (evitement obstacles + suivi ligne)
 * Cible : Arduino Uno / STM32 (simulation via GCC)
 * Auteure : Vanelle Stephanie MANGOUA DJOUSSEU
 */

#include "../include/robot.h"
#include <stdio.h>
#include <stdlib.h>

/* ══ Simulation HAL (remplacement analogWrite/digitalRead pour PC) ══════ */
static uint8_t  pwm_g = 0, pwm_d = 0;
static bool     dir_g_fwd = true, dir_d_fwd = true;
static uint16_t sim_distance = 80;   /* cm */


void analogWrite(uint8_t pin, uint8_t val)  { (void)pin; (void)val; }
void digitalWrite(uint8_t pin, bool val)    { (void)pin; (void)val; }
uint16_t analogRead(uint8_t pin)            { (void)pin; return 600; }
void delay_ms(uint32_t ms)                  { (void)ms; }

/* ══ Initialisation ═════════════════════════════════════════════════════ */
void robot_init(Robot *r) {
    r->etat                   = ETAT_STOP;
    r->vitesse_g              = 0;
    r->vitesse_d              = 0;
    r->distance_obstacle      = 999;
    r->ligne_gauche           = false;
    r->ligne_droite           = false;
    r->temps_dernier_obstacle = 0;
    r->nb_evitements          = 0;
    printf("[INIT] Robot initialise\n");
}

/* ══ Commandes moteurs ══════════════════════════════════════════════════ */
void robot_avancer(Robot *r, uint8_t vitesse) {
    r->etat     = ETAT_AVANCER;
    r->vitesse_g = r->vitesse_d = vitesse;
    dir_g_fwd = dir_d_fwd = true;
    pwm_g = pwm_d = vitesse;
    digitalWrite(PIN_MOTEUR_G_FWD, true);  digitalWrite(PIN_MOTEUR_G_BWD, false);
    digitalWrite(PIN_MOTEUR_D_FWD, true);  digitalWrite(PIN_MOTEUR_D_BWD, false);
    analogWrite(PIN_PWM_G, vitesse);       analogWrite(PIN_PWM_D, vitesse);
    printf("[MOTEUR] AVANCER   | V=%d | PWM_G=%d PWM_D=%d\n", vitesse, pwm_g, pwm_d);
}

void robot_reculer(Robot *r, uint8_t vitesse) {
    r->etat     = ETAT_RECULER;
    r->vitesse_g = r->vitesse_d = vitesse;
    dir_g_fwd = dir_d_fwd = false;
    digitalWrite(PIN_MOTEUR_G_FWD, false); digitalWrite(PIN_MOTEUR_G_BWD, true);
    digitalWrite(PIN_MOTEUR_D_FWD, false); digitalWrite(PIN_MOTEUR_D_BWD, true);
    analogWrite(PIN_PWM_G, vitesse);       analogWrite(PIN_PWM_D, vitesse);
    printf("[MOTEUR] RECULER   | V=%d\n", vitesse);
}

void robot_tourner_gauche(Robot *r) {
    r->etat = ETAT_TOURNER_GAUCHE;
    digitalWrite(PIN_MOTEUR_G_FWD, false); digitalWrite(PIN_MOTEUR_G_BWD, true);
    digitalWrite(PIN_MOTEUR_D_FWD, true);  digitalWrite(PIN_MOTEUR_D_BWD, false);
    analogWrite(PIN_PWM_G, VITESSE_ROTATION);
    analogWrite(PIN_PWM_D, VITESSE_ROTATION);
    printf("[MOTEUR] TOURNER GAUCHE | V=%d\n", VITESSE_ROTATION);
}

void robot_tourner_droite(Robot *r) {
    r->etat = ETAT_TOURNER_DROITE;
    digitalWrite(PIN_MOTEUR_G_FWD, true);  digitalWrite(PIN_MOTEUR_G_BWD, false);
    digitalWrite(PIN_MOTEUR_D_FWD, false); digitalWrite(PIN_MOTEUR_D_BWD, true);
    analogWrite(PIN_PWM_G, VITESSE_ROTATION);
    analogWrite(PIN_PWM_D, VITESSE_ROTATION);
    printf("[MOTEUR] TOURNER DROITE | V=%d\n", VITESSE_ROTATION);
}

void robot_stop(Robot *r) {
    r->etat     = ETAT_STOP;
    r->vitesse_g = r->vitesse_d = 0;
    digitalWrite(PIN_MOTEUR_G_FWD, false); digitalWrite(PIN_MOTEUR_G_BWD, false);
    digitalWrite(PIN_MOTEUR_D_FWD, false); digitalWrite(PIN_MOTEUR_D_BWD, false);
    analogWrite(PIN_PWM_G, 0);             analogWrite(PIN_PWM_D, 0);
    printf("[MOTEUR] STOP\n");
}

/* ══ Capteurs ══════════════════════════════════════════════════════════ */
uint16_t capteur_ultrason_cm(void) {
    /* Simulation : distance variable */
    sim_distance = (uint16_t)(20 + rand() % 80);
    return sim_distance;
}

bool capteur_ir_gauche(void)  { return analogRead(PIN_IR_LEFT)  < SEUIL_IR; }
bool capteur_ir_droite(void) { return analogRead(PIN_IR_RIGHT) < SEUIL_IR; }

/* ══ Evitement d'obstacles ════════════════════════════════════════════ */
void eviter_obstacle(Robot *r) {
    r->etat = ETAT_URGENCE;
    r->nb_evitements++;
    printf("[EVIT] Obstacle detecte a %d cm ! Evitement #%u\n",
           r->distance_obstacle, r->nb_evitements);

    robot_stop(r);         delay_ms(200);
    robot_reculer(r, VITESSE_LENTE); delay_ms(400);
    robot_stop(r);         delay_ms(100);

    /* Choisir la direction (simple : alterner gauche/droite) */
    if (r->nb_evitements % 2 == 0) {
        robot_tourner_gauche(r);
    } else {
        robot_tourner_droite(r);
    }
    delay_ms(DELAI_ROTATION_MS);
    robot_stop(r); delay_ms(100);
}

/* ══ Suivi de ligne (capteurs IR sol) ═════════════════════════════════ */
void suivre_ligne(Robot *r) {
    bool ig = capteur_ir_gauche();
    bool id = capteur_ir_droite();
    r->ligne_gauche = ig;
    r->ligne_droite = id;

    if (ig && id) {
        robot_avancer(r, VITESSE_NORMALE);
    } else if (!ig && id) {
        robot_tourner_gauche(r);
        printf("[LIGNE] Correction GAUCHE\n");
    } else if (ig && !id) {
        robot_tourner_droite(r);
        printf("[LIGNE] Correction DROITE\n");
    } else {
        robot_stop(r);
        printf("[LIGNE] Ligne perdue - STOP\n");
    }
}

/* ══ Boucle principale (mode evitement) ═══════════════════════════════ */
void loop_principal(Robot *r) {
    r->distance_obstacle = capteur_ultrason_cm();

    if (r->distance_obstacle <= DIST_URGENCE_CM) {
        r->etat = ETAT_URGENCE;
        eviter_obstacle(r);
    } else if (r->distance_obstacle <= DIST_OBSTACLE_CM) {
        eviter_obstacle(r);
    } else {
        robot_avancer(r, VITESSE_NORMALE);
    }
}
