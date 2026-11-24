/* showdown_mods (issue #21): two Showdown event modifiers as env tick jobs. The client libg passes the StartLoading
 * modifier list through and never acts on it (the server spawns the events), so nothing happens without this file.
 *
 * NB_SD_MODIFIERS="3,5" turns them on (event_modifiers.csv Id: 3 Meteors, 5 HealingMushrooms); unset = off, the battle
 * is unchanged. NB_SD_DBG=1 logs every event. Effects are applied by env (damage root / hp), not by a native area: an area
 * needs an owner and then only hits that owner's enemies or heals its team, while the events hit / heal everyone. So the
 * observation does not show the warning circle or the mushroom (no contract change).
 *
 * Meteors: one at a time. A red circle at the spot of the brawler with the most others within the blast radius ("meteors
 * prioritize Brawlers that are closer together"), impact 2.5 s later: 2000 damage to every brawler within 1200 u, knockback,
 * and the obstacles in that circle break. Healing mushrooms: next to the most isolated brawler ("spawn on players who are by
 * themselves"); after growing, a ring of 1000 u heals every brawler in it by 1000 per second for 5 s; rings may overlap.
 * Sources: area_effects_logic.csv EventExplosion (Damage 2000, Radius 1200, PushbackStrength 150, DestroysEnvironment),
 * EventHealing (Hot, Damage -1000, Radius 1000, TimeMs 5000), ExplosionSpawn and HealingSpawn (TimeMs 2500: the meteor's
 * warning and the mushroom's growth, issue #22); the fandom wiki's Modifiers page (2000 damage, knockback, breaks
 * obstacles, one meteor at a time, 1000 heal per second, both more frequent as the match goes on).
 * [?] guessed (no source found): every first-spawn tick, interval and its shrink, and the spot offset. Event damage is a
 * flat 2000 (the data's value, not level-scaled: env's x2 applies to character attackers only). */
#include "nbhost.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
extern Module *g_libg;
#define B(off) ((uint8_t *)g_libg->base + (off))
#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))

int env_sd_chars(void *sim, uint8_t **out, int *pidx, int max);
int env_sd_in_gas_xy(void *sim, int x, int y);
int env_sd_seed(void);
void env_sd_knockback(uint8_t *v, int sx, int sy, int strength);
void env_sd_break(void *sim, int x, int y, int r);

#define MOD_METEORS 3            /* event_modifiers.csv Id */
#define MOD_MUSHROOMS 5
#define MET_DMG 2000             /* EventExplosion Damage */
#define MET_R 1200               /* EventExplosion Radius */
#define MET_PUSH 150             /* EventExplosion PushbackStrength */
#define MET_WARN 50              /* the red circle, 2.5 s before impact: area_effects_logic ExplosionSpawn TimeMs 2500 (its
                                  * skin row is the meteor_area_effect with meteor_ball_animation; the wiki rounds to 3 s) */
#define MET_FIRST 600            /* [?] first circle at 30 s (the intro is 182 ticks) */
#define MET_GAP0 200             /* [?] 10 s from one impact to the next circle, */
#define MET_GAP_STEP 10          /* [?] 0.5 s shorter after every meteor ("increasing frequency"), */
#define MET_GAP_MIN 60           /* [?] down to 3 s */
#define MUSH_HEAL 1000           /* EventHealing Damage -1000, per second (wiki: 1000 per second) */
#define MUSH_R 1000              /* EventHealing Radius */
#define MUSH_TICKS 100           /* EventHealing TimeMs 5000 */
#define MUSH_GROW 50             /* 2.5 s from sprouting to the first heal: area_effects_logic HealingSpawn TimeMs 2500 (skin
                                  * healing_mushroom_area_effect; [?] no chain column links it to EventHealing, only the names) */
#define MUSH_FIRST 400           /* [?] first mushroom at 20 s */
#define MUSH_GAP0 300            /* [?] 15 s between mushrooms, */
#define MUSH_GAP_STEP 20         /* [?] 1 s shorter after each, */
#define MUSH_GAP_MIN 120         /* [?] down to 6 s */
#define MUSH_OFF 400             /* [?] sprouts up to this far from the lone brawler */
#define MUSH_MAX 4

int g_sd_mods, g_sd_dbg;         /* bit k = modifier Id k on */
static void *g_last_sim; static int g_last_tick;
static uint32_t g_rng;
static struct { int at, x, y, n, gap; } g_met;                    /* at: impact tick (0 = no circle up) */
static struct { int start, x, y; } g_mush[MUSH_MAX]; static int g_mush_next, g_mush_gap;
long g_sd_meteors, g_sd_met_hits, g_sd_mush, g_sd_mush_heal;

static uint32_t rnd(void) { g_rng = g_rng * 1664525u + 1013904223u; return g_rng >> 8; }
static long d2(uint8_t *c, int x, int y) { long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; return dx * dx + dy * dy; }

typedef uint64_t (*root_t)(void *, int, int, int, int, void *, void *, int, int, int, void *, int, int, int, int, int, int, int);
static void event_hit(uint8_t *v, int dmg) {   /* no attacker: no damage model, no kill credit (as the storm's gas_hit) */
    if (dmg >= I32(v, 0x3c4) && I32(v, 0xaa0) != -1) I32(v, 0xaa0) = -1;
    ((root_t)B(0xb422d0))(v, -1, dmg, 0, 0, NULL, NULL, 1, I32(v, 0x38), I32(v, 0x3c), NULL, 0, 0, 0, 1, 0, 0, 0);
}

static void battle_reset(int tick) {
    g_rng = (uint32_t)env_sd_seed() * 2654435761u + 17;
    memset(&g_met, 0, sizeof g_met); memset(g_mush, 0, sizeof g_mush);
    g_mush_next = MUSH_FIRST; g_mush_gap = MUSH_GAP0;
    if (g_sd_dbg) LOG("[sdmod] battle start tick %d: modifiers %#x\n", tick, g_sd_mods);
}

static void meteors(void *sim, int tick, uint8_t **ch, int n) {
    if (!g_met.at) {
        int start = g_met.n ? g_met.gap : MET_FIRST;   /* g_met.gap: tick of the next circle after an impact */
        if (tick < start || n < 1) return;
        int best = -1, bk = -1;
        for (int i = 0; i < n; i++) {
            int k = 0; for (int j = 0; j < n; j++) k += j != i && d2(ch[j], I32(ch[i], 0x38), I32(ch[i], 0x3c)) <= (long)MET_R * MET_R;
            if (k > bk || (k == bk && (rnd() & 1))) { bk = k; best = i; }
        }
        g_met.x = I32(ch[best], 0x38); g_met.y = I32(ch[best], 0x3c); g_met.at = tick + MET_WARN;
        if (g_sd_dbg) LOG("[sdmod] meteor circle tick %d at %d,%d (%d others near), impact %d\n", tick, g_met.x, g_met.y, bk, g_met.at);
        return;
    }
    if (tick < g_met.at) return;
    int hits = 0;
    for (int i = 0; i < n; i++) {
        if (d2(ch[i], g_met.x, g_met.y) > (long)MET_R * MET_R) continue;
        int hp0 = I32(ch[i], 0x3c4); event_hit(ch[i], MET_DMG);
        if (I32(ch[i], 0x3c4) > 0) env_sd_knockback(ch[i], g_met.x, g_met.y, MET_PUSH);
        hits++; if (g_sd_dbg) LOG("[sdmod] meteor hit ch %d hp %d -> %d\n", I32(ch[i], 8), hp0, I32(ch[i], 0x3c4));
    }
    env_sd_break(sim, g_met.x, g_met.y, MET_R);
    g_sd_meteors++; g_sd_met_hits += hits; g_met.n++;
    int gap = MET_GAP0 - MET_GAP_STEP * (g_met.n - 1); if (gap < MET_GAP_MIN) gap = MET_GAP_MIN;
    if (g_sd_dbg) LOG("[sdmod] meteor impact tick %d at %d,%d: %d hit, next circle in %d\n", tick, g_met.x, g_met.y, hits, gap);
    g_met.at = 0; g_met.gap = tick + gap;
}

static void mushrooms(void *sim, int tick, uint8_t **ch, int n) {
    if (tick >= g_mush_next && n > 0) {
        int best = -1; long bd = -1;
        for (int i = 0; i < n; i++) {
            long m = 1L << 40; for (int j = 0; j < n; j++) if (j != i) { long d = d2(ch[j], I32(ch[i], 0x38), I32(ch[i], 0x3c)); if (d < m) m = d; }
            if (m > bd) { bd = m; best = i; }
        }
        int k; for (k = 0; k < MUSH_MAX && g_mush[k].start; k++) {}
        if (k < MUSH_MAX) {
            double a = (rnd() % 3600) * M_PI / 1800; int r = rnd() % (MUSH_OFF + 1);
            int x = I32(ch[best], 0x38) + (int)(r * cos(a)), y = I32(ch[best], 0x3c) + (int)(r * sin(a));
            if (env_sd_in_gas_xy(sim, x, y)) { x = I32(ch[best], 0x38); y = I32(ch[best], 0x3c); }
            g_mush[k].start = tick + MUSH_GROW; g_mush[k].x = x; g_mush[k].y = y; g_sd_mush++;
            if (g_sd_dbg) LOG("[sdmod] mushroom tick %d at %d,%d (next to ch %d), heals from %d\n", tick, x, y, I32(ch[best], 8), g_mush[k].start);
        }
        g_mush_next = tick + g_mush_gap; g_mush_gap -= MUSH_GAP_STEP; if (g_mush_gap < MUSH_GAP_MIN) g_mush_gap = MUSH_GAP_MIN;
    }
    for (int k = 0; k < MUSH_MAX; k++) {
        if (!g_mush[k].start || tick < g_mush[k].start) continue;
        int age = tick - g_mush[k].start;
        if (age >= MUSH_TICKS) { g_mush[k].start = 0; continue; }
        if (age % 20) continue;                       /* one heal per second */
        for (int i = 0; i < n; i++) {
            if (d2(ch[i], g_mush[k].x, g_mush[k].y) > (long)MUSH_R * MUSH_R) continue;
            int hp = I32(ch[i], 0x3c4), mx = I32(ch[i], 0x3c8), nh = hp + MUSH_HEAL > mx ? mx : hp + MUSH_HEAL;
            if (nh > hp) { I32(ch[i], 0x3c4) = nh; g_sd_mush_heal += nh - hp; }
            if (g_sd_dbg) LOG("[sdmod] mushroom heal ch %d hp %d -> %d\n", I32(ch[i], 8), hp, nh);
        }
    }
}

void sd_mods_tick(void *sim) {
    if (!g_sd_mods || !sim || I32(g_libg->base, 0x12eefb4) != 3) return;   /* battle running */
    int tick = I32(sim, 0x10);
    if (sim != g_last_sim || tick < g_last_tick) battle_reset(tick);
    g_last_sim = sim; g_last_tick = tick;
    uint8_t *ch[64]; int pi[64], n = env_sd_chars(sim, ch, pi, 64);
    if (g_sd_mods >> MOD_METEORS & 1) meteors(sim, tick, ch, n);
    if (g_sd_mods >> MOD_MUSHROOMS & 1) mushrooms(sim, tick, ch, n);
}

void sd_mods_install(void) {
    const char *e = getenv("NB_SD_MODIFIERS"); g_sd_dbg = getenv("NB_SD_DBG") != NULL;
    for (const char *p = e; p && *p; ) {
        int id = atoi(p); if (id == MOD_METEORS || id == MOD_MUSHROOMS) g_sd_mods |= 1 << id;
        while (*p && *p != ',') p++;
        if (*p) p++;
    }
    if (g_sd_mods) LOG("[sdmod] event modifiers on: %#x (meteors %d, healing mushrooms %d)\n", g_sd_mods, g_sd_mods >> MOD_METEORS & 1, g_sd_mods >> MOD_MUSHROOMS & 1);
}
