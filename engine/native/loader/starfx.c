/* star power effects (bsrl-sim issue #47): star power cards whose reader is compiled out of this libg (notes/issue20.md,
 * notes/issue47.md), re-implemented in the host the way gear.c does the gears. Only cards whose whole effect is in their
 * own Value columns (cards.csv Value .. Value6, read here from the card at +0x110 + 4 x (k - 1), libg's 0xaa9568) and
 * whose condition the host can read off the brawler (hp, a kill) are here; the card's Type enum (+0x100, libg's 0xaa9500;
 * the numbers below are what star_audit's "[star] p" lines print for these cards) picks the effect. Each effect's text
 * is the card's TID_SPEC_ABI_..._DESC in localization/texts.csv; a number is a Value column, never a guess.
 *
 *   reduce_all_damage 20 (Driller_unique_2)         V1 % less damage taken, always
 *   low_health_shield 30, 30 (BullDude_unique_2)    below V1 % hp: V2 % less damage taken
 *   reduce_damage_full_health 50 (DoorMan_unique)   at full hp the hit taken is V1 % less (the next one finds hp below full)
 *   prey_on_the_weak 50, 30 (Crow_unique_2)         V1 % more damage dealt to a target at V2 % hp or less (any damage of the
 *                                                   attacker but the storm: [?] poison ticks too, the card says attack and Super)
 *   berserker 60 (BullDude_unique)                  below V1 % hp the reload doubles (+100 in the reload aggregate that
 *                                                   superfix_status.c my_reload_pct returns: T x 100 / (100 + r))
 *   heal_continuous 15, 40 (AssaultShotgun_unique_2) every V2 ticks (the text: ticksasseconds, 40 = 2 s) V1 % of the missing hp
 *   steal_souls 20 (Undertaker_unique)              a brawler this one defeats: V1 % of its max hp back
 *   steal_souls2 15, 12 (HammerDude_unique)         a brawler this one defeats: V1 % more damage dealt for V2 seconds (20 ticks/s)
 * The cards still reach the config (+0x08, offline.c); libg's own readers of other cards run as before. NB_STAR_FX=0 turns
 * these off. State per player: NbeResp star_*. */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <string.h>
#include <stdlib.h>

#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))

/* cards.csv Type enums (what star_audit prints for the cards, 2026-11-25) */
enum { K_NONE = 0, K_REDUCE_ALL, K_LOWHP_SHIELD, K_FULLHP_REDUCE, K_PREY, K_BERSERK, K_HEAL_MISSING, K_STEAL_HEAL, K_STEAL_DMG, K_SPEED_LOWHP };
#define ETYPE_REDUCE_ALL      82   /* Driller_unique_2 */
#define ETYPE_LOWHP_SHIELD    38   /* BullDude_unique_2 */
#define ETYPE_FULLHP_REDUCE   150  /* DoorMan_unique */
#define ETYPE_PREY            2    /* Crow_unique_2 */
#define ETYPE_BERSERK         7    /* BullDude_unique */
#define ETYPE_HEAL_MISSING    115  /* AssaultShotgun_unique_2 */
#define ETYPE_STEAL_HEAL      14   /* Undertaker_unique */
#define ETYPE_STEAL_DMG       25   /* HammerDude_unique */
/* TrickshotDude_unique_2 (cards.csv row 23000156, Type trait_star_power: that Type is shared by every trait card, so the data id picks it):
 * character_components_logic.csv TrickshotDudeStarPowerNormalAndBuddyComponent, Values 40 / 10 / 35 / 60; the card text is "runs
 * Values[2] % faster when his health falls below Values[0] %" */
#define CARD_SPEED_LOWHP 23000156
#define SPEED_LOWHP_BELOW_PCT 40
#define SPEED_LOWHP_PCT 35
#define TPS 20   /* sim ticks per second (the gear TID texts: 10 s = 200 ticks) */

typedef struct {
    int card, etype, kind, v[3];   /* card data id, Type enum, effect, Value1..3 */
    int next_heal;                 /* heal_continuous: the tick of the next heal */
    int buff_until, buff_pct;      /* steal_souls2: damage dealt +buff_pct % until that tick */
    int st[4];                     /* counts: hits reduced, hits boosted, heals / reload answers, kills used */
    int low;                       /* K_SPEED_LOWHP: below the hp line at the last tick */
} SFx;
static SFx g_s[NBE_MAXP];
static int g_on = 1;

static int kind_of(int etype, int card) {
    if (card == CARD_SPEED_LOWHP) return K_SPEED_LOWHP;
    struct { int e, k; } t[] = { {ETYPE_REDUCE_ALL, K_REDUCE_ALL}, {ETYPE_LOWHP_SHIELD, K_LOWHP_SHIELD}, {ETYPE_FULLHP_REDUCE, K_FULLHP_REDUCE},
        {ETYPE_PREY, K_PREY}, {ETYPE_BERSERK, K_BERSERK}, {ETYPE_HEAL_MISSING, K_HEAL_MISSING}, {ETYPE_STEAL_HEAL, K_STEAL_HEAL},
        {ETYPE_STEAL_DMG, K_STEAL_DMG} };
    for (unsigned k = 0; k < sizeof t / sizeof *t; k++) if (t[k].e == etype && etype >= 0) return t[k].k;
    return K_NONE;
}

void starfx_clear(void) { memset(g_s, 0, sizeof g_s); }
/* RESET response (env.c div_publish): the card in the player's config (+0x08) */
void starfx_reset_player(int i, void *cfg) {
    if (i < 0 || i >= NBE_MAXP) return;
    SFx *S = &g_s[i]; memset(S, 0, sizeof *S);
    void *card = cfg ? PTR(cfg, 0x08) : NULL; if (!card) return;
    S->card = I32(card, 0x20); S->etype = I32(card, 0x100); S->kind = kind_of(S->etype, S->card);
    for (int k = 0; k < 3; k++) S->v[k] = I32(card, 0x110 + 4 * k);
    S->next_heal = S->v[1] > 0 ? S->v[1] : 0;
    static int nlog; if (nlog++ < 40)
        LOG("[starfx] player %d: card %d type %d -> effect %d, values %d %d %d\n", i, S->card, S->etype, S->kind, S->v[0], S->v[1], S->v[2]);
}

/* damage d > 0 through the root 0xb422d0 from player ai's brawler (ach, ai = -1: not a player's) to player vi's (vch, vi = -1),
 * before the gear round's shield; storm = the storm's own hit */
int starfx_damage(uint8_t *ach, int ai, uint8_t *vch, int vi, int d, int storm, int tick) {
    if (!g_on || d <= 0 || storm) return d;
    long nd = d;
    if (ach && ai >= 0 && ai < NBE_MAXP && ai != vi && vch) {   /* the attacker's card: damage dealt */
        SFx *A = &g_s[ai]; int hp = I32(vch, 0x3c4), mx = I32(vch, 0x3c8);
        if (A->kind == K_PREY && mx > 0 && hp * 100 <= A->v[1] * mx) { nd = nd * (100 + A->v[0]) / 100; A->st[1]++; }
        if (A->kind == K_STEAL_DMG && tick < A->buff_until) { nd = nd * (100 + A->buff_pct) / 100; A->st[1]++; }
    }
    if (vch && vi >= 0 && vi < NBE_MAXP && ai != vi) {   /* the victim's card: damage taken */
        SFx *V = &g_s[vi]; int hp = I32(vch, 0x3c4), mx = I32(vch, 0x3c8), red = 0;
        if (V->kind == K_REDUCE_ALL) red = V->v[0];
        else if (V->kind == K_LOWHP_SHIELD && mx > 0 && hp * 100 < V->v[0] * mx) red = V->v[1];
        else if (V->kind == K_FULLHP_REDUCE && hp >= mx) red = V->v[0];
        if (red > 0) { nd = nd * (100 - (red > 100 ? 100 : red)) / 100; V->st[0]++; }
    }
    return (int)nd;
}

/* superfix_status.c my_reload_pct: this card's part of the reload aggregate r for the brawler ch of player i */
int starfx_reload_pct(int i, uint8_t *ch) {
    if (!g_on || i < 0 || i >= NBE_MAXP || !ch) return 0;
    SFx *S = &g_s[i];
    if (S->kind == K_BERSERK && I32(ch, 0x3c8) > 0 && I32(ch, 0x3c4) * 100 < S->v[0] * I32(ch, 0x3c8)) { S->st[2]++; return 100; }
    return 0;
}

/* env.c my_root, after the root: the brawler vch (player vi) went from alive to dead; attacker ach (player ai or -1) */
void starfx_kill(uint8_t *ach, int ai, int vi, int tick) {
    if (!g_on || !ach || ai < 0 || ai >= NBE_MAXP || ai == vi || vi < 0) return;
    SFx *A = &g_s[ai];
    static int nlog; if (A->kind && nlog++ < 30) LOG("[starfx] kill: player %d (effect %d) defeated player %d at tick %d\n", ai, A->kind, vi, tick);
    if (A->kind == K_STEAL_HEAL) {
        int mx = I32(ach, 0x3c8), hp = I32(ach, 0x3c4);
        if (hp > 0 && mx > 0) { hp += mx * A->v[0] / 100; I32(ach, 0x3c4) = hp < mx ? hp : mx; A->st[3]++; }
    } else if (A->kind == K_STEAL_DMG) { A->buff_until = tick + A->v[1] * TPS; A->buff_pct = A->v[0]; A->st[3]++; }
}

/* env.c rec_move: the move speed (units/s) for player i's brawler from base (the speed it would move with), 0 = unchanged */
int starfx_speed(int i, uint8_t *ch, int base) {
    if (!g_on || i < 0 || i >= NBE_MAXP || !ch || base <= 0) return 0;
    SFx *S = &g_s[i];
    if (S->kind == K_SPEED_LOWHP && I32(ch, 0x3c8) > 0 && I32(ch, 0x3c4) * 100 < SPEED_LOWHP_BELOW_PCT * I32(ch, 0x3c8)) {
        S->st[2]++; return base * (100 + SPEED_LOWHP_PCT) / 100;
    }
    return 0;
}

/* after every tick, per player i (ch = its brawler or NULL, alive) -> 1 if the move should be re-sent (the hp crossed a speed line) */
int starfx_tick_player(int i, uint8_t *ch, int alive, int tick) {
    if (!g_on || i < 0 || i >= NBE_MAXP || !ch || !alive) return 0;
    SFx *S = &g_s[i]; int resend = 0;
    if (S->kind == K_SPEED_LOWHP) {
        int low = I32(ch, 0x3c8) > 0 && I32(ch, 0x3c4) * 100 < SPEED_LOWHP_BELOW_PCT * I32(ch, 0x3c8);
        if (low != S->low) { S->low = low; resend = 1; }
    }
    if (S->kind == K_HEAL_MISSING && S->v[1] > 0 && tick >= S->next_heal) {
        int hp = I32(ch, 0x3c4), mx = I32(ch, 0x3c8);
        if (hp > 0 && hp < mx) {
            I32(ch, 0x3c4) = hp + (mx - hp) * S->v[0] / 100; S->st[2]++;
            static int nlog; if (nlog++ < 12) LOG("[starfx] heal: player %d tick %d hp %d -> %d of %d\n", i, tick, hp, I32(ch, 0x3c4), mx);
        }
        S->next_heal = tick + S->v[1];
    }
    return resend;
}

void starfx_publish(NbeResp *r) {   /* every response */
    r->star_valid = 1;
    for (int i = 0; i < NBE_MAXP; i++) {
        const SFx *S = &g_s[i];
        r->star_card[i] = S->card; r->star_kind[i] = S->kind;
        for (int k = 0; k < 4; k++) r->star_stat[i][k] = S->st[k];
    }
}
/* NB_STAR_VT=1 (a probe for notes/issue47.md): count the calls of 0xb2fe44 (the lazy init that calls the star power helper family at
 * 0xb3020c-0xb30620 with the player in x1) and how many had a player */
extern Module *g_libg;
void *hook_replace(Module *m, uint64_t off, void *repl);
static void (*o_init)(void *, void *); static long g_vt_n, g_vt_pl;
static void my_init(void *obj, void *player) {
    g_vt_n++; if (player) g_vt_pl++;
    if (g_vt_n <= 12 || g_vt_n % 500 == 0) LOG("[starfx] vt init #%ld obj %p player %p (with player %ld) lr %p\n", g_vt_n, obj, player, g_vt_pl, __builtin_return_address(0));
    o_init(obj, player);
}
void starfx_install(void) {
    int vt = getenv("NB_STAR_VT") ? atoi(getenv("NB_STAR_VT")) : 0;
    if (vt) o_init = hook_replace(g_libg, 0xb2fe44, (void *)my_init);
    const char *e = getenv("NB_STAR_FX"); g_on = !e || atoi(e) != 0;
    LOG("[starfx] star power effects: host effects %s\n", g_on ? "on" : "off");
}
