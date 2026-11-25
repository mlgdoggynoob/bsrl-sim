/* superfix_items.c (bsrl-sim issue #6, see superfix.c): areas that items and areas should leave behind but the shipped
 * client libg never spawns.
 *
 * Item TriggerAreaEffect (ItemData +0x60): the item update 0xb6b8e0 (vtable 0x1209240 slot +0x28) runs the trigger: an
 * enemy within TriggerRangeSubTiles sets +0x90 (triggered) and the fuse +0x9c (Value2 / Value; b6dce0) for the fuse types
 * of the mask 0x4802020200005040 (b6cf0c: 6 Mine, 12, 14, 25, 33, 41, 59, 62); the fuse counts down 50 ms a tick
 * (b6cf30) and at 0 only types 9, 0x42 and 3 have client code (b6ded0..): the item is then removed (slot 6 0xb6e4a4)
 * without its area. +0x60 is read only at b6d020 (type 25's radius): the server's spawn is compiled out. Re-implemented
 * after the update returns: when the fuse ran out in that update, the area is spawned with the sequence libg's own item
 * destroy 0xb6e0b0 uses for DestroyAreaEffect (b6e0f8..b6e1e0): create 0xb29360(data, skin 0xc70e4c(item, 0, 0xb6a718(item)))
 * -> position 0xba7dc8 / 0xb6a61c -> +0x80/+0x84/+0x88 -> owner/kind 0xb29340 -> damage pair +0xe8 = item +0xe0 ->
 * modifiers 0xb2b2d4(area, item +0x150, 0) -> object manager 0xb63198 -> start 0xb29494. Bo's Mine (Bo_def_ulti2_area).
 * Piper's bombs 18000035 / 18000146 (hypercharged) are left to env.c (sf_bomb_state / sf_explode). ConductorSign (type 53,
 * Chuck) has no trigger in the client (its update b6bcf0 only counts +0x9c down while +0x2bc, never set here, is 0): its TriggerAreaEffect
 * ConductorSignArea (Damage) is spawned once, on the sign's first update that runs (the update is skipped while
 * +0xd4 > now), i.e. when the post lands.
 *
 * Area ChainAreaEffect (AreaEffectData +0xe0, getter 0xa97c04): the area expire 0xb28f84 (called from the area tick at
 * b28d08 when shouldExpire 0xb28d4c says so) only sets +0xf4 and runs the listeners; no reader of 0xa97c04 spawns the
 * chain. On entry, for an area that reached its end tick (+0xd8), the chain area is spawned at it with the same sequence
 * (owner +0x108, kind +0xf8, flag +0x2d0, damage pair +0xe8, modifiers +0x168), and the chain's SpawnItem (+0x110) is made
 * with the item factory 0xb55684 as spawnfix.c's make_item does (spawnfix's on_area only does that for type 5).
 * Ruffs' RuffsSupplySpawn -> RuffsSupplyExplosion (+ RuffsBuff).
 *
 * Otis' super projectile deals no damage to the character it attaches its SilencerHugger to (b74c00): see superfix_hugger.
 *
 * NB_SUPERFIX=0 turns this off with the rest of superfix; NB_SUPERFIX_ITEMS=0 only this part. */
#include "nbhost.h"
#include <stdlib.h>
extern Module *g_libg;
extern int g_superfix, g_superfix_dbg;
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
#define B(off) ((uint8_t *)g_libg->base + (off))
#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(uint8_t *)((uint8_t *)(p) + (o)))
#define U64(p, o) (*(uint64_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
static int mode(void) { return I32(g_libg->base, 0x12eefb4) == 3; }   /* battle running (spawnfix.c mode()) */
typedef void *(*getp_t)(void *);
typedef int (*geti_t)(void *);
static void *data_of(void *o) { return ((getp_t)B(0xb6a384))(o); }
static int now_of(void *o) { uint8_t *sim = ((getp_t)B(0xb6a378))(o); return sim ? I32(sim, 0x10) : -1; }   /* 0xc26bd8 = sim +0x10 */

int g_superfix_items = 1;
static long g_ntrig, g_nsign, g_nchain, g_nchain_item, g_nchain_early;
static int busy;   /* our own spawns run 0xb29494 / update code again: no nested spawn */
#define BOMB_ITEM 18000035                  /* Piper's bombs (normal, hypercharged OverchargedBomb): env.c */
#define OC_BOMB_ITEM 18000146               /* sf_bomb_state / sf_explode explode them */
#define FUSE_TYPES 0x4802020200005040ULL    /* b6cf0c: item types with a trigger fuse */

static long hp_sum(uint8_t *src) {   /* debug: HP of every character (vtable 0x1209020) in src's object manager */
    uint8_t *mgr = PTR(src, 0x20); void **arr = mgr ? PTR(mgr, 0x28) : NULL; int cnt = mgr ? I32(mgr, 0x34) : 0; long s = 0;
    for (int i = 0; arr && i < cnt && i < 512; i++) { uint8_t *o = arr[i]; if (o && *(uint8_t **)o == B(0x1209020)) s += I32(o, 0x3c4); }
    return s;
}
static long g_last_hit;   /* debug: HP the last spawned area took at its start */
/* the item destroy 0xb6e0b0's area spawn (b6e0f8..b6e1e0) with the source object, owner/kind/flag, damage pair and modifiers
 * as arguments (item: +0xb0, +0xb8, 0, +0xe0, +0x150; area: +0x108, +0xf8, +0x2d0, +0xe8, +0x168) */
static uint8_t *spawn_area_at(uint8_t *src, void *ad, void *owner, int kind, int flag, uint64_t dmg, void *mods) {
    if (!src || !ad || !owner || !PTR(src, 0x20)) return NULL;
    void *skin = ((void *(*)(void *, void *, void *))B(0xc70e4c))(src, NULL, ((getp_t)B(0xb6a718))(src));
    uint8_t *a = ((uint8_t *(*)(void *, void *))B(0xb29360))(ad, skin);
    if (!a) return NULL;
    ((void (*)(void *, void *, int))B(0xba7dc8))(a + 0x48, src + 0x48, 1);
    ((void (*)(void *, int, int, int))B(0xb6a61c))(a, ((geti_t)B(0xb6a628))(src), ((geti_t)B(0xb6a630))(src), ((geti_t)B(0xb6a638))(src));
    I32(a, 0x80) = ((geti_t)B(0xb6a754))(src);
    I32(a, 0x84) = ((geti_t)B(0xb6a820))(src);
    I32(a, 0x88) = ((geti_t)B(0xb6a884))(src);
    ((void (*)(void *, void *, int, int))B(0xb29340))(a, owner, kind, flag);
    U64(a, 0xe8) = dmg;
    ((void (*)(void *, void *, int))B(0xb2b2d4))(a, mods, 0);
    ((void (*)(void *, void *))B(0xb63198))(PTR(src, 0x20), a);
    long h0 = g_superfix_dbg ? hp_sum(src) : 0;
    ((void (*)(void *))B(0xb29494))(a);
    g_last_hit = g_superfix_dbg ? h0 - hp_sum(src) : 0;
    return a;
}

/* ---- item TriggerAreaEffect */
typedef void (*upd_t)(void *, void *, void *, void *);
static upd_t o_item_update;
static int g_sign_ring[64], g_sign_pos, g_sign_last = -1;
static int seen(int *ring, int n, int *pos, int id) {
    for (int i = 0; i < n; i++) if (ring[i] == id) return 1;
    ring[*pos] = id; *pos = (*pos + 1) % n; return 0;
}
static void my_item_update(uint8_t *it, void *x1, void *x2, void *x3) {
    uint8_t *d = it ? data_of(it) : NULL;
    int on = g_superfix && g_superfix_items && d && !busy && mode();
    int fuse = on && U8(it, 0x90) && I32(it, 0x9c) > 0;   /* triggered, fuse still running */
    o_item_update(it, x1, x2, x3);
    if (!on) return;
    int type = I32(d, 0x54), id = I32(d, 0x20); void *trig = PTR(d, 0x60);
    if (!trig || id == BOMB_ITEM || id == OC_BOMB_ITEM) return;
    static int ring2[64], pos2;   /* debug: where each trap lies once armed (the audit's target stands still) */
    if (g_superfix_dbg && type >= 0 && type < 64 && ((FUSE_TYPES >> type) & 1) && I32(it, 0x94) <= 0 && !seen(ring2, 64, &pos2, I32(it, 8))) {
        uint8_t *mgr = PTR(it, 0x20); void **arr = mgr ? PTR(mgr, 0x28) : NULL; int cnt = mgr ? I32(mgr, 0x34) : 0; long best = -1;
        for (int i = 0; arr && i < cnt && i < 512; i++) { uint8_t *o = arr[i];
            if (!o || *(uint8_t **)o != B(0x1209020) || o == PTR(it, 0xb0) || I32(o, 0x3c4) <= 0) continue;
            long dx = I32(o, 0x38) - I32(it, 0x38), dy = I32(o, 0x3c) - I32(it, 0x3c), d2 = dx * dx + dy * dy; if (best < 0 || d2 < best) best = d2; }
        LOG("[superfix] trap %d armed at %d,%d tick %d, nearest other character %ld u\n", I32(it, 8), I32(it, 0x38), I32(it, 0x3c),
            now_of(it), best < 0 ? -1L : (long)__builtin_sqrt((double)best));
    }
    int fire = 0;
    if (type >= 0 && type < 64 && ((FUSE_TYPES >> type) & 1) && fuse && I32(it, 0x9c) <= 0) { fire = 1; g_ntrig++; }
    if (type == 53) {   /* object ids restart in every battle: the ring is cleared when the tick goes back */
        int t = now_of(it);
        if (t < g_sign_last) { for (int i = 0; i < 64; i++) g_sign_ring[i] = 0; }
        g_sign_last = t;
        if (I32(it, 0xd4) <= t && !seen(g_sign_ring, 64, &g_sign_pos, I32(it, 8))) { fire = 2; g_nsign++; }
    }
    if (!fire) return;
    busy = 1;
    uint8_t *a = spawn_area_at(it, trig, PTR(it, 0xb0), I32(it, 0xb8), 0, U64(it, 0xe0), it + 0x150);
    busy = 0;
    if (g_superfix_dbg) LOG("[superfix] item %d (data %d type %d) %s -> area %p (type %d) at %d,%d dmg %d/%d tick %d, HP taken %ld\n", I32(it, 8), id,
                            type, fire == 2 ? "landed" : "fuse out", a, I32(trig, 0x118), I32(it, 0x38), I32(it, 0x3c), I32(it, 0xe0), I32(it, 0xe4), now_of(it), g_last_hit);
}

/* ---- area ChainAreaEffect */
typedef long (*mkitem_t)(void *, int, int, int, int, int, int, int, int, int, void *, void *, void *, int);
static void on_area_expire(uint64_t *c) {
    uint8_t *a = (uint8_t *)c[0]; uint8_t *d = a ? data_of(a) : NULL;
    if (!g_superfix || !g_superfix_items || !d || busy || !mode() || U8(a, 0xf4)) return;   /* +0xf4: already expired */
    uint8_t *chain = ((getp_t)B(0xa97c04))(d);
    if (!chain) return;
    if (now_of(a) < I32(a, 0xd8)) { g_nchain_early++; return; }   /* removed before its end tick (owner died, ...): no chain */
    busy = 1;
    uint8_t *a2 = spawn_area_at(a, chain, PTR(a, 0x108), I32(a, 0xf8), U8(a, 0x2d0), U64(a, 0xe8), a + 0x168);
    void *idata = PTR(chain, 0x110); long it = 0;
    if (a2 && idata && PTR(a, 0x108)) {   /* the chain's SpawnItem, as spawnfix.c make_item */
        void *owner = PTR(a, 0x108);
        it = ((mkitem_t)B(0xb55684))(idata, I32(a2, 0x38), I32(a2, 0x3c), 1, 99, I32(a2, 0xe8), I32(a2, 0xec), I32(a2, 0x80), I32(a2, 0x84),
                                     I32(a2, 0x88), owner, a2, ((getp_t)B(0xb6a378))(owner), I32(a2, 0xf8));
        if (it) g_nchain_item++;
    }
    busy = 0;
    if (a2) g_nchain++;
    if (g_superfix_dbg) LOG("[superfix] area %p (data %d type %d) expired at tick %d (end %d) -> chain area %p (type %d) dmg %d at %d,%d item %p, HP taken %ld\n", a,
                            I32(d, 0x20), I32(d, 0x118), now_of(a), I32(a, 0xd8), a2, I32(chain, 0x118), a2 ? I32(a2, 0xe8) : 0, I32(a, 0x38), I32(a, 0x3c), (void *)it, g_last_hit);
}

/* ---- Otis (Silencer) super hit: at b74b2c the projectile hit code sees a character hit by a projectile whose SpawnedItem is
 * type 0x28 (SilencerHugger), makes the hugger with the factory (b74bf4, damage pair = projectile +0xd4/+0xd8) and attaches
 * it to the character with 0xb6e5b4 (b74c00); the character's HP is never touched on this path (host run: hugger attached
 * to the target with pair 340/340, target HP unchanged for 100 ticks). The `bl` at b74c00 is redirected: the attach runs,
 * then the projectile damage goes through the damage root 0xb422d0 with the arguments of the hit code's own call at b7327c
 * (victim, owner index, damage, 0, 0, owner +0xe0, projectile, 1, +0xfc, +0x100, data, 0, +0x418, 0, 1, 0, 0xb779a0 & 1, 0). */
static long g_nhug;
typedef uint64_t (*root_t)(void *, int, int, int, int, void *, void *, int, int, int, void *, int, int, int, int, int, int, int);
void superfix_hugger(uint8_t *it, uint8_t *ch, uint8_t *pr) {   /* in place of `bl 0xb6e5b4` at 0xb74c00; x2 = x25 = projectile */
    ((void (*)(void *, void *))B(0xb6e5b4))(it, ch);
    if (!g_superfix || !g_superfix_items || !mode() || !ch || !pr || busy) return;
    int dmg = I32(pr, 0xd4), hp0 = I32(ch, 0x3c4);
    if (dmg <= 0 || hp0 <= 0) return;
    busy = 1;
    ((root_t)B(0xb422d0))(ch, ((geti_t)B(0xb6a754))(pr), dmg, 0, 0, PTR(pr, 0xe0), pr, 1, I32(pr, 0xfc), I32(pr, 0x100), data_of(pr), 0,
                          I32(pr, 0x418), 0, 1, 0, ((geti_t)B(0xb779a0))(pr) & 1, 0);
    busy = 0;
    g_nhug++;
    if (g_superfix_dbg) LOG("[superfix] hugger %d on %d: damage %d, hp %d -> %d tick %d\n", I32(it, 8), I32(ch, 8), dmg, hp0, I32(ch, 0x3c4), now_of(ch));
}
void superfix_hugger_thunk(void);
__asm__(".text\n.global superfix_hugger_thunk\nsuperfix_hugger_thunk:\n\tmov x2, x25\n\tb superfix_hugger\n");

void superfix_items_install(void) {
    const char *e = getenv("NB_SUPERFIX_ITEMS"); if (e) g_superfix_items = atoi(e);
    if (!g_superfix_items) { LOG("[superfix] items: disabled\n"); return; }
    if (*(uint32_t *)B(0xb6b8e0) == 0xd105c3ff) o_item_update = (upd_t)hook_replace(g_libg, 0xb6b8e0, (void *)my_item_update);   /* sub sp, sp, #0x170 */
    else LOG("[superfix] items: 0xb6b8e0 is not the item update: trigger areas off\n");
    if (*(uint32_t *)B(0xb28f84) == 0xd101c3ff) hook_enter(g_libg, 0xb28f84, on_area_expire);   /* sub sp, sp, #0x70 */
    else LOG("[superfix] items: 0xb28f84 is not the area expire: chain areas off\n");
    void hook_bl(Module *m, uint64_t off, void *fn);
    if (*(uint32_t *)B(0xb74bfc) == 0xaa0003f4 && *(uint32_t *)B(0xb74c00) == 0x97ffe66d)   /* mov x20, x0; bl 0xb6e5b4 */
        hook_bl(g_libg, 0xb74c00, (void *)superfix_hugger_thunk);
    else LOG("[superfix] items: 0xb74c00 is not the hugger attach: Otis' super damage off\n");
    LOG("[superfix] items installed (item trigger areas, area chains, hugger hit)\n");
}
void superfix_items_status(void) { LOG("[superfix] items: trigger areas %ld (fuse) + %ld (sign); chain areas %ld (items %ld, %ld expired early); hugger hits %ld\n",
                                       g_ntrig, g_nsign, g_nchain, g_nchain_item, g_nchain_early, g_nhug); }
