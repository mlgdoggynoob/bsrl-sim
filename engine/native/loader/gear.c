/* gears (bsrl-sim issue #51): the two gears of a power-11 brawler, gear_boosts.csv (data type 62, global ids 62xxxxxx).
 *
 * What the shipped libg v68.279 still has (notes/issue51.md): the player config holds the two gears at +0x18 / +0x20
 * (GearBoostData), a character keeps gear instances in char+0xd68 (count +0xd74; ctor 0xb6a8ec: +0 data, +8 LogicType),
 * and the battle logic reads them through 0xb565b8(char, LogicType) (the instance when 0xae2aa4 allows the gear for the
 * character) or the config lookups 0xc34ebc / 0xc34fc8. Live readers: HealthRegen 1 (0xb46900: regen x (100 + v) / 100),
 * SuperChargeRate 6 (0xb4f928), SuperHealth 7, SuperRange 8, SuperShield 12, PetDamage 14 (0xb565b8 callers),
 * ExtraSpawnling 15 and GadgetCooldown 17 (config: the accessory's cooldown +0xc4 x (100 - v) / 100 at 0xc401e0, which
 * gadget.c then uses). The server code that fills char+0xd68 is compiled out: nirkt's battle_fix.c ensure() fills it from
 * the config at character init, for every LogicType here (it took only 0 and 1 before).
 *
 * Compiled out, re-implemented here (no reader in the battle logic):
 *   ForestSpeed 0       +v % move speed while the brawler stands on a bush tile (env.c rec_move; a bush change re-sends the
 *                       move, gear_tick)
 *   LowHealthDamage 2   +v % damage dealt while the attacker's hp is below 50 % of its max (env.c my_root)
 *   ConsumableShield 4  a v hp shield (900) in front of the hp: damage from another object takes the shield first (env.c
 *                       my_root, after every other modifier; the storm skips it); full at the start, and back to full once
 *                       the brawler has been at full hp, untouched, for SHIELD_REGEN ticks (10 s, the TID text) [?] whether a
 *                       hit on the shield alone restarts the 10 s in the real game: here it does
 *   ReloadSpeed 5       +v to the reload aggregate superfix_status.c my_reload_pct returns (libg: T x 100 / (100 + r)), so
 *                       the reload takes 100 / 115 of the time
 * Not done: Vision 3 (an effect on what each observer sees: per-observer reveal state in the encoder, nbpc.fair and
 * fast_obs, an observation change), PetrolSlows 13 (Amber's oil spills: no slow area to attach to), SuperTurret 16 (Pam's
 * turret heal: superfix.c TURRET_HEAL_PCT would take it, not measured). Gears 9 / 10 / 11 / 18 reach no brawler (every
 * hero of theirs is HeroDeprecated).
 *
 * Equip: offline.c my_player_ctor calls gear_equip(slot, cfg, chardata) with the RESET's div.gear[slot] (two ids, 0 =
 * none); a gear must be in table 62 and allowed for that character (libg's 0xae2aa4), else the slot is rejected
 * (NbeResp.div_err). State per player in NbeResp gear_* (every response). NB_GEARS=0: no host re-implementation (the
 * cards still reach the config; libg's own readers still run). */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <string.h>
#include <stdlib.h>

#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
extern Module *g_libg;
#define B(off) ((uint8_t *)g_libg->base + (off))
void *div_data(int id); void div_reject(int i);

#define T_GEAR 62             /* gear_boosts.csv data type (libg registers the table with 0x3e at 0xb05020) */
#define SHIELD_REGEN 200      /* ticks at full hp before the shield is back (TID_GEAR_SHIELD_INFO: 10 s at 20 ticks/s) */
#define LOW_HP_PCT 50         /* LowHealthDamage: below 50 % of max hp (TID_GEAR_LOW_HEALTH_DAMAGE_INFO) */
enum { G_FOREST = 0, G_REGEN = 1, G_LOWHP = 2, G_VISION = 3, G_SHIELD = 4, G_RELOAD = 5 };

int32_t g_div_gear[NBE_MAXP][2];   /* RESET div.gear (env.c div_reset) */
typedef struct {
    int id[2], type[2], val[2];     /* data id, LogicType, ModifierValue per gear slot (0 / -1 / 0 = none) */
    int shield, full_ticks;         /* ConsumableShield: hp left, ticks at full hp since the last hit */
    int bush;                       /* ForestSpeed: on a bush at the last move */
    int st[4];                      /* effect counts: low-hp hits boosted, shield hp absorbed, moves sped up, reload answers */
} Gear;
static Gear g_g[NBE_MAXP];
static int g_on = 1;

static int gtype(void *g) { return ((int (*)(void *))B(0xae2b14))(g); }
static int gval(void *g) { return ((int (*)(void *))B(0xae2b24))(g); }
static int gval_of(int i, int type) {   /* the ModifierValue of player i's gear of that LogicType, 0 if it has none */
    if (i < 0 || i >= NBE_MAXP) return 0;
    for (int k = 0; k < 2; k++) if (g_g[i].id[k] && g_g[i].type[k] == type) return g_g[i].val[k];
    return 0;
}

/* offline.c my_player_ctor: the RESET's two gears for this slot into the player's config (+0x18, +0x20) */
void gear_equip(int slot, void *cfg, void *chardata) {
    if (slot < 0 || slot >= NBE_MAXP || !cfg) return;
    for (int k = 0; k < 2; k++) {
        int id = g_div_gear[slot][k]; if (!id) continue;
        void *g = id / 1000000 == T_GEAR ? div_data(id) : NULL;
        int ok = g && ((int (*)(void *, void *))B(0xae2aa4))(g, chardata) & 1;
        if (ok && k == 1 && PTR(cfg, 0x18) && gtype(PTR(cfg, 0x18)) == gtype(g)) ok = 0;   /* two of one kind: the second is refused */
        if (ok) PTR(cfg, 0x18 + 8 * k) = g;
        else { div_reject(slot); LOG("[gear] slot %d gear %d rejected (not a gear, or not for character %d)\n", slot, id, chardata ? I32(chardata, 0x20) : 0); }
    }
}

void gear_clear(void) { memset(g_g, 0, sizeof g_g); }
/* RESET response (env.c div_publish): what the config holds, the shield full */
void gear_reset_player(int i, void *cfg) {
    if (i < 0 || i >= NBE_MAXP) return;
    Gear *G = &g_g[i]; memset(G, 0, sizeof *G);
    for (int k = 0; k < 2; k++) {
        void *g = cfg ? PTR(cfg, 0x18 + 8 * k) : NULL; G->type[k] = -1;
        if (!g) continue;
        G->id[k] = I32(g, 0x20); G->type[k] = gtype(g); G->val[k] = gval(g);
    }
    G->shield = gval_of(i, G_SHIELD);
    static int nlog; if ((G->id[0] || G->id[1]) && nlog++ < 40)
        LOG("[gear] player %d: gear %d (type %d, value %d), gear %d (type %d, value %d)\n", i, G->id[0], G->type[0], G->val[0],
            G->id[1], G->type[1], G->val[1]);
}

/* damage d > 0 through the root 0xb422d0 from player ai's brawler to player vi's (-1 = not a player's brawler), after the
 * other modifiers; storm = the storm's own hit */
int gear_damage(uint8_t *ach, int ai, uint8_t *vch, int vi, int d, int storm) {
    if (!g_on || d <= 0) return d;
    int v = ach && ai != vi ? gval_of(ai, G_LOWHP) : 0;
    if (v && I32(ach, 0x3c4) * 100 < I32(ach, 0x3c8) * LOW_HP_PCT) { d = d * (100 + v) / 100; g_g[ai].st[0]++; }
    if (vi >= 0 && vi < NBE_MAXP && vch && !storm && ai != vi && gval_of(vi, G_SHIELD)) {
        Gear *G = &g_g[vi]; G->full_ticks = 0;
        int a = d < G->shield ? d : G->shield;
        if (a > 0) { G->shield -= a; d -= a; G->st[1] += a; }
    }
    return d;
}

/* the move speed (units/s) for player i's brawler ch from base (the speed it would move with), 0 = unchanged; bush = it
 * stands on a bush tile */
int gear_speed(int i, uint8_t *ch, int base, int bush) {
    if (!g_on || i < 0 || i >= NBE_MAXP || !ch || base <= 0) return 0;
    int v = gval_of(i, G_FOREST); if (!v) return 0;
    g_g[i].bush = bush;
    if (!bush) return 0;
    g_g[i].st[2]++;
    return base * (100 + v) / 100;
}

/* superfix_status.c my_reload_pct: the gear's part of the reload aggregate r for player i's brawler (0 = none) */
int gear_reload_pct(int i) {
    if (!g_on) return 0;
    int v = gval_of(i, G_RELOAD); if (v > 0) g_g[i].st[3]++;
    return v;
}

/* after every tick, per player i (ch = its brawler or NULL, alive): the shield's regeneration; -> 1 if the move should be
 * re-sent (the bush state of a ForestSpeed brawler changed) */
int gear_tick_player(int i, uint8_t *ch, int alive, int bush) {
    if (!g_on || i < 0 || i >= NBE_MAXP) return 0;
    Gear *G = &g_g[i]; int sv = gval_of(i, G_SHIELD), resend = 0;
    if (sv && ch && alive) {
        if (I32(ch, 0x3c4) >= I32(ch, 0x3c8)) { if (G->shield < sv && ++G->full_ticks >= SHIELD_REGEN) { G->shield = sv; G->full_ticks = 0; } }
        else G->full_ticks = 0;
    }
    if (gval_of(i, G_FOREST) && ch && alive && bush != G->bush) { G->bush = bush; resend = 1; }
    return resend;
}
int gear_has(int i, int type) { return gval_of(i, type) != 0; }

void gear_publish(NbeResp *r) {   /* every response */
    r->gear_valid = 1;
    for (int i = 0; i < NBE_MAXP; i++) {
        const Gear *G = &g_g[i];
        for (int k = 0; k < 2; k++) r->gear_id[i][k] = G->id[k];
        r->gear_shield[i] = G->shield;
        for (int k = 0; k < 4; k++) r->gear_stat[i][k] = G->st[k];
    }
}
void gear_install(void) {
    const char *e = getenv("NB_GEARS"); g_on = !e || atoi(e) != 0;
    LOG("[gear] gears: config +0x18 / +0x20, host effects %s (ForestSpeed, LowHealthDamage, ConsumableShield, ReloadSpeed)\n", g_on ? "on" : "off");
}
