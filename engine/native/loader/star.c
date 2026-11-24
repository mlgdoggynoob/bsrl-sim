/* star power probe (bsrl-sim issue #20, step 1): which star power card types the shipped libg v68.279 still reads.
 *
 * Every star power read in libg goes through three loadout-config lookups (the player wrappers 0xc42838 / 0xc42874 /
 * 0xc428b0 and the projectile / area owner wrappers 0xb6a75c / 0xb6a7b0 tail-call them with the same arguments):
 *   0xc34be0(cfg, type)       -> the config's card of that type (cfg+0x08 star power, then the cfg+0x50 list, count +0x5c),
 *                                NULL if none
 *   0xc34c6c(cfg, type, idx)  -> that card's Value<idx> (0xaa9568), -1 if none
 *   0xc34d10(cfg, type)       -> an int of that card (its first skill's +0xc0), -1 if none
 * The type is the card's Type enum (cards.csv Type, read by 0xaa9500 from the card). With NB_STAR_PROBE=1 this file
 * hooks the three, counts calls and hits (a card of that type was found) per type with the first caller's libg offset,
 * and logs the counts once per battle ("[star] q ..." lines, at the next build and at star_dump). A type that is never
 * asked for while a player carries its card has no reader left in this build (likely compiled out with the server code).
 * 40 ticks into each battle it also logs every player's star power card ("[star] p ..."): data id, Type enum, the "cards off" byte
 * (player+0x238: the wrappers return nothing while it is set). Python: star_audit.py. Without NB_STAR_PROBE nothing is hooked.
 *
 * Per-card hits ("[star] h ..."): a hit only says the config held SOME card of the asked type. Two cards can share a Type
 * (Gale's and Damian's star powers are both stun_wall_push), and the config's +0x50 list holds the gadget and gear cards
 * too. So each hit also records the card that answered (0xc34be0's result; for the other two lookups 0xc34be0 is asked
 * again with the same config and type, a plain read) and the player slot whose config it was (-1: not a player's config, or
 * a lookup while the battle is being built, before star_built). Counted per (card, slot) with the first caller, logged
 * with the per-type counts. star_audit counts a card as read only when it answered itself. */
#include "nbhost.h"
#include <stdlib.h>
#include <string.h>

#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(uint8_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
extern Module *g_libg;
#define B(off) ((uint8_t *)g_libg->base + (off))
void *hook_replace(Module *m, uint64_t off, void *repl);

#define NT 4096   /* Type enum values seen so far are < 1000 (the enum map 0xaa3000-0xaa8860); larger ones share the last slot */
static int g_on;
static uint32_t q_n[NT], q_hit[NT], q_lr[NT];
static long g_battle;

static void *(*o_card)(void *, int);
static int (*o_val)(void *, int, int);
static int (*o_int)(void *, int);
static void *player_cfg(void *p) {   /* what the player wrappers use: player+0x348, else the active loadout's config */
    void *c = PTR(p, 0x348); if (c) return c;
    void **lo = PTR(p, 0x30); int li = I32(p, 0x40); void **ld = lo && li >= 0 && li < 8 ? lo[li] : NULL;
    return ld ? ld[1] : NULL;
}
static void *g_ssim; static int g_sticks;

/* the players' configs, cached when the battle is built (star_built) and again at star_tick: a hit is matched against these
 * pointers only, so the sim is never read from a lookup (the sim-only reset frees the old sim before the build starts) */
#define MAXS 16
static void *g_cfg[MAXS]; static int g_ncfg;
static void cache_cfgs(void *sim) {
    int np = I32(sim, 0x7c); void **ps = PTR(sim, 0x70);
    if (np < 0 || np > MAXS || !ps) np = 0;
    for (int i = 0; i < np; i++) g_cfg[i] = ps[i] ? player_cfg(ps[i]) : NULL;
    g_ncfg = np;
}
static int cfg_slot(void *cfg) {   /* the player whose config this is, -1 if none (or before star_built) */
    for (int i = 0; cfg && i < g_ncfg; i++) if (g_cfg[i] == cfg) return i;
    return -1;
}

#define NH 512   /* (card, slot) pairs per battle: a 10-player battle answers for a few dozen */
static struct { int32_t card, slot; uint32_t n, lr; } g_h[NH];
static int g_nh; static uint32_t g_h_lost;
static void note_hit(void *cfg, void *card, uint32_t lr) {
    int id = card ? I32(card, 0x20) : 0, s = cfg_slot(cfg);
    for (int k = 0; k < g_nh; k++) if (g_h[k].card == id && g_h[k].slot == s) { g_h[k].n++; return; }
    if (g_nh >= NH) { g_h_lost++; return; }
    g_h[g_nh].card = id; g_h[g_nh].slot = s; g_h[g_nh].n = 1; g_h[g_nh].lr = lr; g_nh++;
}

static int slot(int t) { return t < 0 ? NT - 1 : t >= NT ? NT - 1 : t; }
static void note(void *cfg, int t, void *card, int hit, void *lr) {
    int s = slot(t); uint32_t off = (uint32_t)((uint8_t *)lr - (uint8_t *)g_libg->base);
    q_n[s]++; if (!q_lr[s]) q_lr[s] = off;
    if (!hit) return;
    q_hit[s]++;
    note_hit(cfg, card ? card : o_card(cfg, t), off);   /* which card answered (a plain read of the same lookup) */
}
/* __builtin_return_address(0): the hook stub is a plain branch, so this is the libg call site (the wrappers tail-call) */
static void *my_card(void *cfg, int t) { void *r = o_card(cfg, t); note(cfg, t, r, r != NULL, __builtin_return_address(0)); return r; }
static int my_val(void *cfg, int t, int i) { int r = o_val(cfg, t, i); note(cfg, t, NULL, r != -1, __builtin_return_address(0)); return r; }
static int my_int(void *cfg, int t) { int r = o_int(cfg, t); note(cfg, t, NULL, r != -1, __builtin_return_address(0)); return r; }

void star_dump(void) {   /* the counts since the last dump, then zero; offline.c calls it when a build starts */
    if (!g_on) return;
    g_ncfg = 0;   /* a build starts: lookups until star_built are not attributed to a slot */
    int k = 0;
    for (int t = 0; t < NT; t++) if (q_n[t]) {
        LOG("[star] q battle=%ld type=%d n=%u hit=%u lr=0x%x\n", g_battle, t, q_n[t], q_hit[t], q_lr[t]); k++;
    }
    for (int i = 0; i < g_nh; i++)
        LOG("[star] h battle=%ld card=%d slot=%d n=%u lr=0x%x\n", g_battle, g_h[i].card, g_h[i].slot, g_h[i].n, g_h[i].lr);
    LOG("[star] dump battle=%ld types=%d cards=%d lost=%u\n", g_battle, k, g_nh, g_h_lost);
    memset(q_n, 0, sizeof q_n); memset(q_hit, 0, sizeof q_hit); memset(q_lr, 0, sizeof q_lr); g_nh = 0; g_h_lost = 0;
}
void star_built(void *sim) { if (g_on && sim) { g_battle++; g_ssim = sim; g_sticks = 0; cache_cfgs(sim); } }   /* after a build */
void star_tick(void *sim) {   /* 40 ticks (2 s) into the battle, once the players have spawned: their star power cards */
    if (!g_on || sim != g_ssim || ++g_sticks != 40) return;
    cache_cfgs(sim);   /* again once the players have spawned (a config set after the build, player+0x348) */
    int np = I32(sim, 0x7c); void **ps = PTR(sim, 0x70); if (np < 0 || np > 64 || !ps) np = 0;
    for (int i = 0; i < np; i++) {
        void *p = ps[i]; if (!p) continue;
        void *cfg = player_cfg(p), *card = cfg ? PTR(cfg, 0x08) : NULL;
        int t = card ? ((int (*)(void *))B(0xaa9500))(card) : -1;
        LOG("[star] p battle=%ld slot=%d card=%d type=%d off=%d\n", g_battle, i, card ? I32(card, 0x20) : 0, t, U8(p, 0x238));
    }
}
void star_install(void) {
    const char *e = getenv("NB_STAR_PROBE"); g_on = e && atoi(e);
    if (!g_on) return;
    o_card = hook_replace(g_libg, 0xc34be0, (void *)my_card);
    o_val = hook_replace(g_libg, 0xc34c6c, (void *)my_val);
    o_int = hook_replace(g_libg, 0xc34d10, (void *)my_int);
    LOG("[star] probe on: 0xc34be0 / 0xc34c6c / 0xc34d10 counted per card type\n");
}
