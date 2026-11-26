/* superfix_cc.c (bsrl-sim issue #19, see superfix.c / superfix_status.c): stuns, silences and Draco's weapon swap, which the
 * shipped client libg compiles out. The game's own checks are already in the client: 0xb38b54 ("cannot act": the mover
 * 0xb4790c and the fire code return early on it) reads the stun ticks char +0xe1c (counted down by the character update at
 * 0xb39a5c), LosePlayerControl +0x984 and Stasis +0x987; the silence getter 0xb38dec (+0x988) blocks the super. What is
 * missing is every writer, so this file writes them:
 *   - Bo's stun trap (card type 46 stun_trap): the area apply 0xb29d80 and the projectile hit 0xb78054 call 0xb47358(victim,
 *     ticks 40, 0, 0, 0, 0) (`mov w0, wzr; ret`, return unused) and skip their knockback for that victim: replaced, it stuns;
 *   - projectile StunLengthMS (ProjectileData +0x1d0 = ms / 50, no reader in the client: Frank's super, its hypercharged
 *     version, Jester's stunning super, boss Frank): env.c's damage root hook (0xb422d0) calls superfix_cc_hit with the
 *     damage source, and a projectile source with a stun length stuns the victim; an enter hook in one projectile hit path
 *     at 0xb73eb8 (after the hit's status adds and knockback; x27 = the hit character, [sp + 296] = the ProjectileData)
 *     covers hits that path reaches (Frank's super does not reach it in live runs);
 *   - projectile SilenceDurationMS: the hit calls 0xb59038(target, ticks) (a bare `ret`): replaced, it silences;
 *   - Stun (16) and Silence (24) areas (Maisie's dash, Frank-style slams, Sandy's hypercharged silence ...): their StunTicks
 *     column is empty in the tables and the client reads it only for the UI; the duration is CustomValue +0x13c (ticks).
 *     At the area's first tick (superfix_status_area), every enemy character that libg's own target test reaches gets it
 *     (superfix_area_reach: circle, InnerRadius ring, RequireLineOfSight: Fang's sweep); HpBasedStun (43, Meeple's
 *     RageQuit) too, for longer the less HP its owner has; an area of another type with StunTicks (+0x160, stored by the table loader at 0xa959dc; only
 *     LeaperOverchargedUltiAreaExplosion, Damage, 30: Mico's hypercharged landing; libg reads it only at the table load)
 *     stuns the same way for StunTicks ticks, without the path stop below (its own knockback is that path);
 *   - a new stun or loss of control stops the character's current path (stop 0xb4103c), because the mover only refuses new
 *     moves (superfix_cc_tick from the character update hook);
 *   - CcImmunity statuses (superfix_status.c aggregate +0x982) keep stuns and silences off.
 *   - Draco (DragonRider): change-skill 0xb35c3c(ch, slot, SkillData, w3, w4, w5) is a bare `ret` (24 callers). The MountUp
 *     component's mount (call at 0xba02e0) passes his dragon weapon (weapon SkillData +0x158 = DragonRiderDragonWeapon), its
 *     dismount (0xba0178) CharacterData +0x260 (DragonRiderWeapon). Only those two call sites (by return address) swap the
 *     skill instance in slot 0 (char +0x458[0]) for one built with libg's own constructor 0xb7aa98 (new 0x58 at 0x11a4d90),
 *     kept per character and swapped back at the dismount; a swap waits while the old instance is running (+0x30).
 *   - R-T (Splitter): his component tick 0xb9c42c (call at 0xb9c4bc) swaps slot 0 to his legs' weapon (SplitterLegsWeapon, Eat
 *     Static) while the partner getter 0xb392d4 finds the legs (superfix_moves.c split_partner), and back to CharacterData
 *     +0x260 (SplitterWeapon) once they are gone: the same swap, a mount unless the data is his own weapon. The other 21
 *     callers stay a no-op as before.
 *   - Angelo (InsectMan, issue #19 final): his SwitchSkill area swaps slot 0 to his weapon's SecondarySkill while he stands
 *     in it (superfix_cc_switch), the same swap.
 * NB_SUPERFIX=0 turns this off with the rest, NB_SUPERFIX_CC=0 this part alone; NB_SUPERFIX_DBG=1 logs every stun / silence / swap. */
#include "nbhost.h"
#include <stdlib.h>
#include <string.h>
extern Module *g_libg;
extern int g_superfix, g_superfix_dbg;
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
#define B(off) ((uint8_t *)g_libg->base + (off))
#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(uint8_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
#define VT_CHAR 0x1209020
enum { CH_CCIMM = 0x982, CH_LOSECTL = 0x984, CH_STASIS = 0x987, CH_STUN_TICKS = 0xe1c };
static int g_cc_on;
static int mode(void) { return I32(g_libg->base, 0x12eefb4) == 3; }
static int now_tick(void *obj) { uint8_t *sim = ((void *(*)(void *))B(0xb6a378))(obj); return sim ? I32(sim, 0x10) : -1; }
static int is_char(void *o) { return o && (int)((uint8_t *)PTR(o, 0) - g_libg->base) == VT_CHAR; }
static int on(void) { return g_cc_on && g_superfix && mode(); }
static long g_nstun_trap, g_nstun_proj, g_nstun_area, g_nsil, g_nsil_area, g_nimm, g_nstop, g_nswap, g_nswap_wait, g_nlos_block;

/* ------------------------------------------------------------------ stun / silence */
static void stun(uint8_t *ch, int ticks, const char *why) {
    if (!is_char(ch) || ticks <= 0 || I32(ch, 0x3c4) <= 0) return;
    if (U8(ch, CH_CCIMM)) { g_nimm++; return; }
    if (I32(ch, CH_STUN_TICKS) < ticks) I32(ch, CH_STUN_TICKS) = ticks;   /* the longer stun wins (no stacking) */
    if (g_superfix_dbg) LOG("[superfix] cc: stun ch %d for %d ticks (%s), tick %d\n", I32(ch, 8), ticks, why, now_tick(ch));
}
/* superfix_moves.c: Buzz's landing stun, Kit's hypercharged super */
void superfix_cc_stun(uint8_t *ch, int ticks, const char *why) { if (on()) stun(ch, ticks, why); }
typedef struct { uint8_t *ch; int id, until; } Sil;
#define SIL_MAX 64
static Sil g_sil[SIL_MAX]; static int g_nsilrec;
static void silence(uint8_t *ch, int ticks, const char *why) {
    if (!is_char(ch) || ticks <= 0 || I32(ch, 0x3c4) <= 0) return;
    if (U8(ch, CH_CCIMM)) { g_nimm++; return; }
    int t = now_tick(ch), k; if (t < 0) return;
    for (k = 0; k < g_nsilrec && !(g_sil[k].ch == ch && g_sil[k].id == I32(ch, 8)); k++) {}
    if (k == g_nsilrec) {
        for (int i = g_nsilrec - 1; i >= 0; i--) if (g_sil[i].until <= t) g_sil[i] = g_sil[--g_nsilrec];
        if (g_nsilrec >= SIL_MAX) return;
        k = g_nsilrec++; g_sil[k] = (Sil){ch, I32(ch, 8), t};
    }
    if (g_sil[k].until < t + ticks) g_sil[k].until = t + ticks;
    if (g_superfix_dbg) LOG("[superfix] cc: silence ch %d for %d ticks (%s), tick %d\n", I32(ch, 8), ticks, why, t);
}
/* superfix_status.c's aggregate asks every tick */
int superfix_cc_silenced(uint8_t *ch, int t) {
    if (!g_cc_on) return 0;
    for (int i = 0; i < g_nsilrec; i++) if (g_sil[i].ch == ch && g_sil[i].id == I32(ch, 8)) return t < g_sil[i].until;
    return 0;
}
/* 0xb47358(victim, ticks, 0, 0, 0, 0): Bo's stun trap */
static int my_trap_stun(uint8_t *ch, int ticks) { if (on()) { stun(ch, ticks, "stun trap"); g_nstun_trap++; } return 0; }
/* 0xb59038(target, ticks): a projectile's SilenceDurationMS */
static void my_silence(uint8_t *ch, int ticks) { if (on()) { silence(ch, ticks, "projectile"); g_nsil++; } }
/* enter hook in the projectile hit at 0xb73eb8 (ldr w0, [x25, #1300]): x27 = the hit character, [sp + 296] = ProjectileData.
 * x27 is callee-saved and untouched by the enter stub, so it still holds the hit code's value when this function starts.
 * Live runs reach it for some hits only (not for Frank's super), so the damage root below covers the rest; a stun taken
 * twice for one hit keeps the longer one. */
static void on_proj_hit(uint64_t *ctx) {
    uint64_t x27; __asm__ volatile("mov %0, x27" : "=r"(x27));
    if (!on()) return;
    uint8_t *pd = *(uint8_t **)((uint8_t *)ctx + 160 + 296), *ch = (uint8_t *)x27;
    if (!pd || !is_char(ch)) return;
    int ticks = I32(pd, 0x1d0);
    if (ticks > 0) { stun(ch, ticks, "projectile"); g_nstun_proj++; }
}
/* From env.c's damage root hook (0xb422d0, x6 = the damage source): a projectile source with a stun length stuns the
 * victim. The hit code's own path (0xb73eb8 above) does not run for these projectiles' hits in this build. */
#define VT_PROJ 0x1209318
void superfix_cc_hit(uint8_t *victim, void *attacker, void *src, uint64_t lr) {
    (void)lr;
    if (!on() || !src || !is_char(victim)) return;
    int vt = (int)((uint8_t *)PTR(src, 0) - g_libg->base);
    uint8_t *pd = vt == VT_PROJ ? ((uint8_t *(*)(void *))B(0xb6a384))(src) : NULL;
    (void)attacker;
    if (!pd) return;
    int ticks = I32(pd, 0x1d0);
    if (ticks > 0) { stun(victim, ticks, "projectile hit"); g_nstun_proj++; }
}
/* libg's own target test of the area apply 0xb29494 (0xb29e8c..0xb29fcc), for the areas the host applies itself (issue #19
 * final): the character must be within r = 0xb2b298(data, ch) (Radius + the character's radius - 50) of the area, both
 * axes first, then the circle; with InnerRadius +0x1b8 > 0 and InnerRadiusDamagePercent +0x1bc == 0 a character closer
 * than InnerRadius is out (a ring); with RequireLineOfSight +0x17d the tile map (sim +0x68, 0xc2a588) must have a line
 * from the area to the character: 0xa56dc0(map, ax, ay, cx, cy), or 0xa56398 for the data byte +0x201 (BooleanAttributes
 * StrictLineOfSight, the byte the apply tests at 0xb29f38), both 1 = clear. -> distance squared, or -1 = not reached. */
long superfix_area_reach(uint8_t *a, uint8_t *d, uint8_t *o) {
    long dx = I32(o, 0x38) - I32(a, 0x38), dy = I32(o, 0x3c) - I32(a, 0x3c), r = ((int (*)(void *, void *))B(0xb2b298))(d, o);
    if (dx > r || dx < -r || dy > r || dy < -r || dx * dx + dy * dy > r * r) return -1;
    long inner = I32(d, 0x1b8);
    if (inner > 0 && I32(d, 0x1bc) == 0 && dx * dx + dy * dy < inner * inner) return -1;
    if (U8(d, 0x17d)) {
        uint8_t *sim = ((uint8_t *(*)(void *))B(0xb6a378))(a); void *map = sim ? PTR(sim, 0x68) : NULL;
        if (!map) return -1;
        int clear = ((int (*)(void *, int, int, int, int))B(U8(d, 0x201) ? 0xa56398 : 0xa56dc0))(map, I32(a, 0x38), I32(a, 0x3c),
                                                                                                    I32(o, 0x38), I32(o, 0x3c)) & 1;
        if (!clear) { g_nlos_block++; return -1; }
    }
    return dx * dx + dy * dy;
}
/* Stun (16), Silence (24) and HpBasedStun (43) areas, and other areas with StunTicks (+0x160, ticks; a stun), from
 * superfix_status_area at every tick of an area: once per area, at
 * its first tick, every enemy character libg's target test above reaches. HpBasedStun (Meeple's RageQuit gadget: "the less
 * hitpoints Meeple has, the stun and knockback effects increase"): CustomValue2 + (CustomValue - CustomValue2) x the
 * owner's missing HP fraction ticks (5 .. 30) [?] the formula is server code, the two values read as the stun's bounds;
 * its knockback (PushbackStrength +0x154, 120) away from the area's centre at the same share of its full strength as the stun
 * has of CustomValue (issue #55; the scaling is ours, the server's is not in this build); the stun starts with it, and
 * superfix_cc_tick lets the knockback run out rather than stopping it. */
static void blk_mark(uint8_t *ch);   /* below: a stun whose path is not stopped */
void env_sd_knockback(uint8_t *v, int sx, int sy, int strength) __attribute__((weak));
/* knocked back by an HpBasedStun area: superfix_cc_tick lets the knockback's path run (10 ticks) instead of stopping it at the
 * stun, as it does for a charge or dash */
typedef struct { uint8_t *ch; int id, until; } Kb;
#define KB_MAX 32
static Kb g_kb[KB_MAX]; static int g_nkb;
static void kb_mark(uint8_t *ch) { if (g_nkb >= KB_MAX) g_nkb = 0; g_kb[g_nkb++] = (Kb){ch, I32(ch, 8), now_tick(ch) + 10}; }
static int kb_on(uint8_t *ch) {
    int t = now_tick(ch);
    for (int i = 0; i < g_nkb; i++) if (g_kb[i].ch == ch && g_kb[i].id == I32(ch, 8) && t <= g_kb[i].until) return 1;
    return 0;
}
typedef struct { void *a; int start; } CcArea;
#define CA_MAX 64
static CcArea g_ca[CA_MAX]; static int g_nca;
void superfix_cc_area(uint8_t *a, uint8_t *d) {
    if (!on() || !a || !d) return;
    int type = I32(d, 0x118), cc = type == 16 || type == 24 || type == 43, ticks = cc ? I32(d, 0x13c) : I32(d, 0x160);   /* StunTicks */
    int full = ticks, push = 0; uint8_t *owner = PTR(a, 0x108);
    if (ticks <= 0 || !owner) return;
    for (int i = 0; i < g_nca; i++) if (g_ca[i].a == a && g_ca[i].start == I32(a, 0xd0)) return;
    if (g_nca >= CA_MAX) g_nca = 0;
    g_ca[g_nca++] = (CcArea){a, I32(a, 0xd0)};
    if (type == 43) {
        int lo = I32(d, 0x140), mx = I32(owner, 0x3c8), hp = I32(owner, 0x3c4);
        if (lo > ticks) lo = ticks;
        ticks = mx > 0 ? lo + (int)((long)(ticks - lo) * (mx - (hp < mx ? hp : mx)) / mx) : lo;
        push = (int)((long)I32(d, 0x154) * ticks / full);
        if (g_superfix_dbg) LOG("[superfix] cc: hp stun area, owner hp %d / %d -> %d ticks, knockback %d\n", hp, mx, ticks, push);
    }
    uint8_t *mgr = PTR(owner, 0x20); if (!mgr) return;
    int n = I32(mgr, 0x34); void **v = PTR(mgr, 0x28); if (!v || n < 0 || n > 4096) return;
    int team = ((int (*)(void *))B(0xb6a820))(a);
    for (int i = 0; i < n; i++) {
        uint8_t *o = v[i];
        if (!is_char(o) || I32(o, 0x3c4) <= 0 || ((int (*)(void *))B(0xb6a820))(o) == team) continue;
        if (superfix_area_reach(a, d, o) < 0) continue;
        if (push > 0 && env_sd_knockback) { env_sd_knockback(o, I32(a, 0x38), I32(a, 0x3c), push); kb_mark(o); }
        if (type == 24) { silence(o, ticks, "area"); g_nsil_area++; } else { stun(o, ticks, type == 43 ? "hp area" : "area"); g_nstun_area++; }
        if (!cc) blk_mark(o);   /* StunTicks of a Damage area: the area's own knockback (its apply runs after this hook) is the path
                                 * the victim is on; stopping it (superfix_cc_tick) would cancel the push the landing also deals */
    }
}

/* ------------------------------------------------------------------ Draco's weapon swap */
/* spare: the instance slot 0 had before the mount (the character's own weapon instance); want: pending data; mount: 1 at the
 * mount (a new instance for the dragon weapon, the old one kept as spare), 0 at the dismount (the spare back). A mount always
 * replaces the spare, so a record left from an earlier battle (same address and id) never hands out a freed instance. The
 * dragon weapon's instance is dropped at the dismount (0x58 bytes per mount, not freed: libg may still point at it). */
typedef struct { uint8_t *ch; int id; void *spare; void *want; int mount; } Swap;
#define SW_MAX 16
static Swap g_sw[SW_MAX]; static int g_nsw;
static Swap *swap_rec(uint8_t *ch) {
    for (int i = 0; i < g_nsw; i++) if (g_sw[i].ch == ch) { if (g_sw[i].id != I32(ch, 8)) g_sw[i] = (Swap){ch, I32(ch, 8)}; return &g_sw[i]; }
    if (g_nsw >= SW_MAX) {   /* full (records are never dropped): reuse one round robin; a lost spare is rebuilt from the data */
        static int next; Swap *w = &g_sw[next++ % SW_MAX]; *w = (Swap){ch, I32(ch, 8)}; return w;
    }
    g_sw[g_nsw] = (Swap){ch, I32(ch, 8)}; return &g_sw[g_nsw++];
}
static void do_swap(uint8_t *ch, Swap *w) {
    uint8_t **sk = PTR(ch, 0x458); int n = I32(ch, 0x464);
    if (!sk || n < 1 || n > 16 || !sk[0] || !w->want || PTR(sk[0], 0) == w->want) { w->want = NULL; return; }
    if (I32(sk[0], 0x30)) { g_nswap_wait++; return; }   /* the old weapon is still running: next tick */
    void *inst;
    if (!w->mount && w->spare && PTR(w->spare, 0) == w->want) inst = w->spare;
    else {
        inst = ((void *(*)(size_t))B(0x11a4d90))(0x58);   /* libg's operator new, as the skill-instance builder 0xb34560 */
        if (!inst) { w->want = NULL; return; }
        ((void (*)(void *, void *))B(0xb7aa98))(inst, w->want);
    }
    w->spare = w->mount ? sk[0] : NULL; sk[0] = inst; g_nswap++;
    if (g_superfix_dbg) LOG("[superfix] cc: weapon %s ch %d -> skill %d, tick %d\n", w->mount ? "mount" : "dismount", I32(ch, 8),
                            I32(w->want, 0x20), now_tick(ch));
    w->want = NULL;
}
/* 0xb35c3c(ch, slot, SkillData, w3, w4, w5) */
static void my_change_skill(uint8_t *ch, int slot, void *data) {
    void *ret = __builtin_return_address(0);
    if (!on() || slot != 0 || !data || !is_char(ch)) return;
    int rt = ret == (void *)B(0xb9c4c0);                 /* R-T's split (see the header) */
    uint8_t *cd = rt ? ((uint8_t *(*)(void *))B(0xb6a384))(ch) : NULL;
    int mount = ret == (void *)B(0xba02e4) || (rt && cd && data != PTR(cd, 0x260));
    if (!mount && ret != (void *)B(0xba017c) && !rt) return;   /* MountUp mount / dismount, R-T's split / rejoin only */
    Swap *w = swap_rec(ch); if (!w) return;
    if (mount) w->spare = NULL;
    w->want = data; w->mount = mount; do_swap(ch, w);
}

/* issue #19 final: Angelo's SwitchSkill area (superfix_status.c area_extra marks its owner while he stands in it): inside, slot
 * 0 becomes his weapon's SecondarySkill (weapon SkillData +0x158: InsectManWeaponPoison), outside his own weapon
 * (CharacterData +0x260) again, through the swap above (a swap waits while the weapon is running). Only characters whose
 * own weapon has a SecondarySkill are touched, and only after the area marked them (Draco's and Starr Nova's own swaps of
 * their secondary skills are left alone). */
typedef struct { uint8_t *ch; int id; } Sw33;
static Sw33 g_s33[16]; static int g_ns33;   /* characters this switch put on their SecondarySkill */
void superfix_cc_switch(uint8_t *ch, int inside) {
    if (!on() || !is_char(ch)) return;
    int k; for (k = 0; k < g_ns33 && !(g_s33[k].ch == ch && g_s33[k].id == I32(ch, 8)); k++) {}
    if (!inside && k == g_ns33) return;   /* never switched here: Draco's / Starr Nova's own secondary skills stay theirs */
    uint8_t *cd = ((uint8_t *(*)(void *))B(0xb6a384))(ch), *own = cd ? PTR(cd, 0x260) : NULL, *sec = own ? PTR(own, 0x158) : NULL;
    uint8_t **sk = PTR(ch, 0x458);
    if (!sec || !sk || I32(ch, 0x464) < 1 || !sk[0]) return;
    void *cur = PTR(sk[0], 0), *want = inside ? sec : own;
    if (cur != own && cur != sec) return;   /* another swap (Draco, R-T) owns slot 0 */
    if (inside && k == g_ns33) { if (g_ns33 >= 16) return; g_s33[g_ns33++] = (Sw33){ch, I32(ch, 8)}; }
    Swap *w = NULL;
    for (int i = 0; i < g_nsw; i++) if (g_sw[i].ch == ch && g_sw[i].id == I32(ch, 8)) w = &g_sw[i];
    if (cur == want) {
        if (w && w->want && w->want != want) w->want = NULL;
        if (!inside) g_s33[k] = g_s33[--g_ns33];   /* back on its own weapon: done */
        return;
    }
    if (w && w->want == want) return;   /* pending */
    if (!w) w = swap_rec(ch);
    if (inside) w->spare = NULL;
    w->want = want; w->mount = inside; do_swap(ch, w);
}

/* superfix_moves.c: Kit attached to a teammate throws his weapon's SecondarySkill (AttacherWeaponAlternate, the yarn balls;
 * hypercharged: SecondarySkill2), back on his own weapon (want NULL) once he lets go; the same swap (waits while it runs) */
void superfix_cc_weapon(uint8_t *ch, void *want) {
    if (!on() || !is_char(ch)) return;
    uint8_t *cd = ((uint8_t *(*)(void *))B(0xb6a384))(ch), *own = cd ? PTR(cd, 0x260) : NULL;
    uint8_t **sk = PTR(ch, 0x458);
    if (!own || !sk || I32(ch, 0x464) < 1 || !sk[0]) return;
    if (!want) want = own;
    Swap *w = NULL;
    for (int i = 0; i < g_nsw; i++) if (g_sw[i].ch == ch && g_sw[i].id == I32(ch, 8)) w = &g_sw[i];
    if (PTR(sk[0], 0) == want) { if (w) w->want = NULL; return; }
    if (!w) w = swap_rec(ch);
    if (!w) return;
    if (want != own) w->spare = NULL;
    w->want = want; w->mount = want != own; do_swap(ch, w);
}

/* ------------------------------------------------------------------ per character tick (superfix_status.c's update hook) */
typedef struct { uint8_t *ch; int id; } Blk;
#define BLK_MAX 64
static Blk g_blk[BLK_MAX]; static int g_nblk;
static void blk_mark(uint8_t *ch) {
    for (int k = 0; k < g_nblk; k++) if (g_blk[k].ch == ch && g_blk[k].id == I32(ch, 8)) return;
    if (g_nblk < BLK_MAX) g_blk[g_nblk++] = (Blk){ch, I32(ch, 8)};
}
void superfix_cc_tick(uint8_t *ch) {
    if (!on() || !is_char(ch)) return;
    for (int i = 0; i < g_nsw; i++) if (g_sw[i].ch == ch && g_sw[i].want) do_swap(ch, &g_sw[i]);
    int blocked = I32(ch, 0x3c4) > 0 && (U8(ch, CH_LOSECTL) || U8(ch, CH_STASIS) || I32(ch, CH_STUN_TICKS) > 0), k;
    for (k = 0; k < g_nblk && !(g_blk[k].ch == ch && g_blk[k].id == I32(ch, 8)); k++) {}
    if (blocked && k == g_nblk) {   /* a new stun: stop the path the character is on (the mover only refuses new moves) */
        if (g_nblk < BLK_MAX) g_blk[g_nblk++] = (Blk){ch, I32(ch, 8)};
        if (!U8(ch, 0x490) && !kb_on(ch)) { ((void (*)(void *))B(0xb4103c))(ch); g_nstop++; }   /* not in a charge / dash (+0x490) or knockback */
    } else if (!blocked && k < g_nblk) g_blk[k] = g_blk[--g_nblk];
}

void superfix_cc_install(void) {
    const char *e = getenv("NB_SUPERFIX_CC");
    if (e && !atoi(e)) { LOG("[superfix] stuns / silences / weapon swap off (NB_SUPERFIX_CC=0)\n"); return; }
    if (*(uint32_t *)B(0xb47358) != 0x2a1f03e0 || *(uint32_t *)B(0xb4735c) != 0xd65f03c0 ||   /* mov w0, wzr; ret */
        *(uint32_t *)B(0xb59038) != 0xd65f03c0 || *(uint32_t *)B(0xb35c3c) != 0xd65f03c0 ||   /* ret; ret */
        *(uint32_t *)B(0xb73eb8) != 0xb9451720 ||                                              /* ldr w0, [x25, #1300] */
        *(uint32_t *)B(0xb38b54) == 0xd65f03c0) {
        LOG("[superfix] cc: libg bytes differ from v68.279, stuns / silences / weapon swap left out\n"); return;
    }
    hook_replace(g_libg, 0xb47358, (void *)my_trap_stun);
    hook_replace(g_libg, 0xb59038, (void *)my_silence);
    hook_replace(g_libg, 0xb35c3c, (void *)my_change_skill);
    hook_enter(g_libg, 0xb73eb8, on_proj_hit);
    g_cc_on = 1;
    LOG("[superfix] stuns, silences and the weapon swaps (Draco, R-T) installed\n");
}
void env_status_counts(long o[7]) __attribute__((weak));
void superfix_cc_status(void) {
    if (env_status_counts) { long o[7]; env_status_counts(o);
        LOG("[superfix] env (this battle): moves re-timed by statuses %ld, rooted %ld; hits scaled %ld; inputs refused %ld; "
            "moves re-sent %ld; taunted / feared steps %ld, native moves %ld\n", o[0], o[1], o[2], o[3], o[4], o[5], o[6]); }
    LOG("[superfix] cc: stuns trap %ld, projectile %ld, area %ld; silences projectile %ld, area %ld; immune %ld; out of sight %ld; "
        "paths stopped %ld; weapon swaps %ld (waited %ld)\n", g_nstun_trap, g_nstun_proj, g_nstun_area, g_nsil, g_nsil_area, g_nimm,
        g_nlos_block, g_nstop, g_nswap, g_nswap_wait);
}
