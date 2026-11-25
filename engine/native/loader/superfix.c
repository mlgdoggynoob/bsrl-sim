/* superfix (bsrl-sim issue #6): supers whose effect the shipped client libg does not run, re-implemented with libg's own
 * functions (the way spawnfix.c re-creates the children of explosions).
 *
 * spawnAreaEffect 0xb3970c (character, ...) -> area: compiled out as `mov x0, xzr; ret`, so no skill ever creates its
 * AreaEffectObject: AreaBuff supers (Emz, Max, Jae-Yong), Attack supers whose effect is an area at the brawler (Angelo,
 * Jacky, Maisie, Pearl, Hank) and the other callers (0xb7d534 / 0xb7d570 AreaBuff, 0xb7fd6c / 0xb7f044 Attack area 1 / 2,
 * 0xb786f4, 0xb7ffac, 0xb82aa8, 0xc2f654). Rebuilt from the chain of the shipped helper 0xb35c40 (12 callers, two in the
 * skill execute): create 0xb2aefc(data, owner, x, y, z, kind, extra) -> modifiers 0xb2b2d4(area, mods, 0) -> follow the
 * owner 0xb29350(area, owner) -> add to the object manager 0xb63198(owner+0x20, area) -> start 0xb29494(area) (which runs
 * spawnfix's on_area: a BulletExplosion area gets its children). Arguments from the call sites: x0 owner, w1 extra (the
 * scaled base damage, as 0xb35c40's callers compute it), x3 data, w4 kind, w7 follow, [sp+16] modifiers, [sp+24] start
 * now (0 at 0xb7ffac, whose caller starts it); w2, w5, w6, [sp], [sp+8] are not used here.
 *
 * DelayedDamage areas (type 8; Tara's BlackHoleUltiExplosion): the area apply 0xb29494 runs once at the spawn and its type
 * gate refuses 8; the client only (de)serialises the area's "done" byte +0xfc (0xb28a94 / 0xb28388). From the area tick
 * 0xb28c0c, once CustomValue ms (data +0x13c) have passed since the apply (area +0xd0 = its tick), the apply runs again with
 * the data's type set to Damage (0) for the call: damage, pushback and wall break then come from libg. 0xb29494 rewrites
 * area +0xd0 / +0xd4 / +0xd8 before its gate: saved and restored, as is the shared data's type. Slippery areas (type 20;
 * Lou's IceDudeUltiArea) get the same re-apply once a second while they live (slippery_tick).
 *
 * Ally / own heal of a super projectile (HealOwnPercent, data +0x1f0; Poco's DeadMariachiUltiProjectile): the attack
 * execute calls the getter 0xafaa10 at 0xb4de50 and drops the result (the server block that used it is compiled out),
 * so the projectile's ally-heal amount +0x10c (the hit code 0xb754b8..0xb754f4 heals same-team characters it touches
 * through 0xb41554 when it is >= 1) is never set. The `bl` is redirected: +0x10c = projectile damage (+0xd4) x percent
 * / 100, and the owner is healed the same amount once per attack (DamageOnlyWithOneProj, getter 0xafaa08), only for the
 * owner's super (attack slot [sp+256] == 2 at that point).
 * Max's hypercharged super throws its drinks from here (max_drinks, issue #19 final).
 * NB_SUPERFIX=0 turns every part off. */
#include "nbhost.h"
#include <stdlib.h>
extern Module *g_libg;
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
void hook_bl(Module *m, uint64_t off, void *fn);
#define B(off) ((uint8_t *)g_libg->base + (off))
#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
static int mode(void) { return I32(g_libg->base, 0x12eefb4) == 3; }   /* battle running (spawnfix.c mode()) */

int g_superfix = 1, g_superfix_dbg;
static long g_narea, g_narea_skip;

typedef void *(*mkarea_t)(void *data, void *owner, int x, int y, int z, int kind, int extra);
typedef int (*geti_t)(void *);
/* issue #19 final: Max's hypercharged super ("Max throws an energy drink to each team member, increasing their movement
 * speed and granting them 25% Super charge"). SpeedyUlti is the only skill with OverchargedProjectiles (SkillData +0x68,
 * count +0x74; hyper.c) and no Projectiles (+0x58, count +0x64), an AreaBuff: its cast reaches libg's spawnAreaEffect (here)
 * but nothing throws the projectiles. When a hypercharged brawler (Character::isOvercharged 0xb35bf0, hyper.c) spawns an
 * area while its super is such a skill, its first overcharged projectile (SpeedyOverchargedProjectile, TravelType 9) goes
 * from it to every other living brawler of its team, through the projectile spawn 0xb78190 (spawnfix.c's arguments, kind 2);
 * where it lands libg spawns its areas (SpeedyOverchargedArea: speed; SpeedyOverchargedArea2: ChargeSuper, applied in
 * superfix_status.c). One cast spawns one area, so each teammate gets one drink. */
static long g_ndrink;
static void max_drinks(uint8_t *ch) {
    uint8_t **sk = PTR(ch, 0x458); uint8_t *sd = sk && I32(ch, 0x464) >= 2 && sk[1] ? PTR(sk[1], 0) : NULL;
    if (!sd || I32(sd, 0x74) < 1 || I32(sd, 0x64) > 0 || !PTR(sd, 0x68) || !(((geti_t)B(0xb35bf0))(ch) & 1)) return;
    void *pd = ((void **)PTR(sd, 0x68))[0], *sim = ((void *(*)(void *))B(0xb6a378))(ch), *h = sim ? PTR(sim, 0) : NULL;
    int n = h ? I32(h, 0xc) : 0, team = ((geti_t)B(0xb6a820))(ch); void **v = h ? PTR(h, 0) : NULL;
    for (int i = 0; pd && v && i < n && i < 4096; i++) {
        uint8_t *o = v[i];
        if (!o || o == ch || (int)((uint8_t *)PTR(o, 0) - g_libg->base) != 0x1209020 || I32(o, 0x3c4) <= 0) continue;
        if (((geti_t)B(0xb6a820))(o) != team || !(((geti_t)B(0xb34de4))(o) & 1)) continue;   /* teammate brawlers */
        void *p = ((void *(*)(int, int, void *, void *, void *, int, int, int, int, int, int, void *, void *, int, int, void *))B(0xb78190))(
            I32(ch, 0x38), I32(ch, 0x3c), ch, ch, pd, I32(o, 0x38), I32(o, 0x3c), 0, 0, 0, 0, NULL, sim, 0, 2, NULL);
        if (p) g_ndrink++;
        if (g_superfix_dbg) LOG("[superfix] drink from ch %d to ch %d: %p\n", I32(ch, 8), I32(o, 8), p);
    }
}
static void *my_spawn_area(uint8_t *ch, int extra, int w2, void *data, int kind, int w5, int w6, int follow,
                           void *s0, void *s1, void *mods, long start) {
    (void)w2; (void)w5; (void)w6; (void)s0; (void)s1;
    if (!g_superfix || !mode() || !ch || !data || !PTR(ch, 0x20)) { g_narea_skip++; return NULL; }   /* the stub's result */
    int x = ((geti_t)B(0xb6a628))(ch), y = ((geti_t)B(0xb6a630))(ch);
    void *a = ((mkarea_t)B(0xb2aefc))(data, ch, x, y, 0, kind, extra);
    if (!a) { g_narea_skip++; return NULL; }
    if (mods) ((void (*)(void *, void *, int))B(0xb2b2d4))(a, mods, 0);
    if (follow & 1) ((void (*)(void *, void *))B(0xb29350))(a, ch);    /* bools are passed as bytes: low bit only */
    ((void (*)(void *, void *))B(0xb63198))(PTR(ch, 0x20), a);
    if (start & 1) ((void (*)(void *))B(0xb29494))(a);
    g_narea++;
    max_drinks(ch);
    if (g_superfix_dbg) LOG("[superfix] spawnAreaEffect owner %p data %p type %d kind %d extra %d follow %d start %d -> %p\n",
                            ch, data, I32(data, 0x118), kind, extra, follow & 1, (int)(start & 1), a);
    return a;
}

/* ---- DelayedDamage (type 8) */
typedef void *(*getp_t)(void *);
static long g_ndelayed, g_nslip;

/* ---- Slippery (type 20; Lou's IceDudeUltiArea): the apply's type gate refuses 20 and the server's slippery logic is
 * compiled out, so the area spawns and hits no one. Its damage (area +0xe8: the projectile's scaled Damage, written by the
 * projectile area spawn at 0xb771ec) is dealt once a second while the area lives, by re-running the apply as a Damage
 * area, as for DelayedDamage. Areas with no damage (Lumi's ice gadget) are left alone. The slide and the freeze build-up
 * (CustomValue / CustomValue2) are not re-implemented. */
#define SLIP_EVERY 20   /* [?] ticks between hits: the row has no interval; 1 s like the SameAreaEffectCanNotDamageMs 1000 of other lingering areas */
static void slippery_tick(uint8_t *a, uint8_t *d, uint8_t *sim) {
    int now = I32(sim, 0x10), d0 = I32(a, 0xd0), d4 = I32(a, 0xd4), d8 = I32(a, 0xd8), el = now - d0;
    if (I32(a, 0xe8) <= 0 || el <= 0 || el % SLIP_EVERY || now > d8) return;
    I32(d, 0x118) = 0; ((void (*)(void *))B(0xb29494))(a); I32(d, 0x118) = 20;
    I32(a, 0xd0) = d0; I32(a, 0xd4) = d4; I32(a, 0xd8) = d8;
    g_nslip++;
    if (g_superfix_dbg) LOG("[superfix] slippery area %p hit after %d ticks, dmg %d\n", a, el, I32(a, 0xe8));
}
static void on_area_tick(uint64_t *ctx) {   /* enter hook on 0xb28c0c, ctx[0] = area */
    uint8_t *a = (uint8_t *)ctx[0];
    if (!g_superfix || !mode() || !a) return;
    extern void superfix_status_area(uint8_t *) __attribute__((weak)); if (superfix_status_area) superfix_status_area(a);   /* type 36 */
    extern void superfix_moves_area(uint8_t *) __attribute__((weak)); if (superfix_moves_area) superfix_moves_area(a);     /* type 38 */
    uint8_t *d = ((getp_t)B(0xb6a384))(a), *sim = ((getp_t)B(0xb6a378))(a);
    if (d && sim && I32(d, 0x118) == 20) { slippery_tick(a, d, sim); return; }
    if (!d || !sim || I32(d, 0x118) != 8 || a[0xfc]) return;
    int el = I32(sim, 0x10) - I32(a, 0xd0);                 /* ticks since the spawn apply (0xc26bd8 = sim +0x10) */
    if (el < I32(d, 0x13c) / 50) return;                    /* CustomValue in ms, 50 ms ticks (BlackHole 700 -> 14) */
    a[0xfc] = 1;
    int d0 = I32(a, 0xd0), d4 = I32(a, 0xd4), d8 = I32(a, 0xd8);
    I32(d, 0x118) = 0; ((void (*)(void *))B(0xb29494))(a); I32(d, 0x118) = 8;
    I32(a, 0xd0) = d0; I32(a, 0xd4) = d4; I32(a, 0xd8) = d8;
    g_ndelayed++;
    if (g_superfix_dbg) LOG("[superfix] delayed damage area %p after %d ticks, dmg %d\n", a, el, I32(a, 0xe8));
}

/* ---- ally / own heal (HealOwnPercent) */
static long g_nheal, g_nheal_self;
int superfix_heal_own(void *pdata, uint8_t *p, uint8_t *owner, int slot) {   /* in place of `bl 0xafaa10` at 0xb4de50 */
    int pct = ((geti_t)B(0xafaa10))(pdata);
    if (!g_superfix || !mode() || pct <= 0 || !p || slot != 2) return pct;
    int amount = (int)((long)I32(p, 0xd4) * pct / 100);
    if (amount < 1) return pct;
    if (I32(p, 0x10c) == 0) { I32(p, 0x10c) = amount; g_nheal++; }
    static void *last_owner; static int last_tick = -1;
    uint8_t *sim = owner ? ((getp_t)B(0xb6a378))(owner) : NULL; int t = sim ? I32(sim, 0x10) : -1;
    if (owner && (!((geti_t)B(0xafaa08))(pdata) || owner != last_owner || t != last_tick)) {
        last_owner = owner; last_tick = t;
        int hp_a = I32(owner, 0x3c4);
        ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(owner, ((geti_t)B(0xb6a754))(p), amount, 1, pdata, I32(p, 0x418), 0, 0, 0, 0);
        g_nheal_self++;
        if (g_superfix_dbg) LOG("[superfix] heal own: owner hp %d -> %d (max %d)\n", hp_a, I32(owner, 0x3c4), I32(owner, 0x3c8));
    }
    if (g_superfix_dbg) LOG("[superfix] heal own: projectile %p %d %% of %d -> %d, owner %p\n", p, pct, I32(p, 0xd4), amount, owner);
    return pct;
}
/* hook_bl lands here with lr = 0xb4de54: x26 = the projectile just spawned (0xb4dc4c), x19 = owner, [sp+256] = attack slot */
void superfix_heal_thunk(void);
__asm__(".text\n.global superfix_heal_thunk\nsuperfix_heal_thunk:\n\tmov x1, x26\n\tmov x2, x19\n\tldr w3, [sp, #256]\n\tb superfix_heal_own\n");

void superfix_install(void) {
    const char *e = getenv("NB_SUPERFIX"); if (e) g_superfix = atoi(e);
    if (getenv("NB_SUPERFIX_DBG")) g_superfix_dbg = 1;
    if (!g_superfix) { LOG("[superfix] disabled\n"); return; }
    if (*(uint32_t *)B(0xb3970c) == 0xaa1f03e0 && *(uint32_t *)B(0xb39710) == 0xd65f03c0)   /* mov x0, xzr; ret */
        hook_replace(g_libg, 0xb3970c, (void *)my_spawn_area);
    else LOG("[superfix] 0xb3970c is not the spawnAreaEffect stub: left as it is\n");
    if (*(uint32_t *)B(0xb28c0c) == 0xa9be7bfd) hook_enter(g_libg, 0xb28c0c, on_area_tick);   /* stp x29, x30, [sp, #-32]! */
    if (*(uint32_t *)B(0xb4de4c) == 0xaa1503e0 && (*(uint32_t *)B(0xb4de50) & 0xfc000000) == 0x94000000)   /* mov x0, x21; bl */
        hook_bl(g_libg, 0xb4de50, (void *)superfix_heal_thunk);
    LOG("[superfix] installed (spawnAreaEffect, delayed damage, heal own)\n");
    extern void superfix_items_install(void) __attribute__((weak)); if (superfix_items_install) superfix_items_install();
    extern void superfix_moves_install(void) __attribute__((weak)); if (superfix_moves_install) superfix_moves_install();
    extern void superfix_status_install(void) __attribute__((weak)); if (superfix_status_install) superfix_status_install();
    extern void superfix_cc_install(void) __attribute__((weak)); if (superfix_cc_install) superfix_cc_install();   /* issue #19 */
}
void superfix_status(void) { LOG("[superfix] areas spawned %ld, skipped %ld; delayed damage %ld; slippery hits %ld; heal own %ld projectiles, %ld owners; "
                                 "Max's drinks %ld\n", g_narea, g_narea_skip, g_ndelayed, g_nslip, g_nheal, g_nheal_self, g_ndrink);
    extern void superfix_items_status(void) __attribute__((weak)); if (superfix_items_status) superfix_items_status();
    extern void superfix_moves_status(void) __attribute__((weak)); if (superfix_moves_status) superfix_moves_status();
    extern void superfix_status_status(void) __attribute__((weak)); if (superfix_status_status) superfix_status_status();
    extern void superfix_cc_status(void) __attribute__((weak)); if (superfix_cc_status) superfix_cc_status(); }
