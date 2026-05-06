#ifndef ROBOT_H
#define ROBOT_H

#include <stdint.h>
#include <stdbool.h>

/* ─── Pinout Arduino/STM32 ──────────────────────────────────────────── */
#define PIN_MOTEUR_G_FWD   5
#define PIN_MOTEUR_G_BWD   6
#define PIN_MOTEUR_D_FWD   9
#define PIN_MOTEUR_D_BWD   10
#define PIN_PWM_G          11
#define PIN_PWM_D          3
#define PIN_TRIG_US        7
#define PIN_ECHO_US        8
#define PIN_SERVO          4
#define PIN_IR_LEFT        14
#define PIN_IR_RIGHT       15
#define PIN_LIGNE_LEFT     16
#define PIN_LIGNE_RIGHT    17

/* ─── Configuration ─────────────────────────────────────────────────── */
#define VITESSE_NORMALE    180   /* 0-255 PWM */
#define VITESSE_LENTE      120
#define VITESSE_ROTATION   150
#define DIST_OBSTACLE_CM   25
#define DIST_URGENCE_CM    10
#define DELAI_ROTATION_MS  400
#define SEUIL_IR           500   /* valeur ADC seuil */

/* ─── Etats machine ──────────────────────────────────────────────────── */
typedef enum {
    ETAT_AVANCER = 0,
    ETAT_RECULER,
    ETAT_TOURNER_GAUCHE,
    ETAT_TOURNER_DROITE,
    ETAT_STOP,
    ETAT_SUIVI_LIGNE,
    ETAT_URGENCE
} EtatRobot;

/* ─── Structure robot ────────────────────────────────────────────────── */
typedef struct {
    EtatRobot   etat;
    uint16_t    vitesse_g;
    uint16_t    vitesse_d;
    uint16_t    distance_obstacle;
    bool        ligne_gauche;
    bool        ligne_droite;
    uint32_t    temps_dernier_obstacle;
    uint32_t    nb_evitements;
} Robot;

/* ─── Prototypes ─────────────────────────────────────────────────────── */
void    robot_init(Robot *r);
void    robot_avancer(Robot *r, uint8_t vitesse);
void    robot_reculer(Robot *r, uint8_t vitesse);
void    robot_tourner_gauche(Robot *r);
void    robot_tourner_droite(Robot *r);
void    robot_stop(Robot *r);
uint16_t capteur_ultrason_cm(void);
bool    capteur_ir_gauche(void);
bool    capteur_ir_droite(void);
void    eviter_obstacle(Robot *r);
void    suivre_ligne(Robot *r);
void    loop_principal(Robot *r);

#endif /* ROBOT_H */
