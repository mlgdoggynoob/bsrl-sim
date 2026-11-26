/* superfix_moves (bsrl-sim issue #6): supers that move the brawler or hit around it, whose server half is a bare `ret`
 * in the shipped client libg. The skill activation 0xb7b268 switches on the skill's BehaviorType (data +0x1a8) and
 * calls these stubs; the client half (move speed, "airborne" checks, no attacks in the air) is shipped and runs.
 *
 * FlyJump (Mico, LeaperUlti, type 19): handler 0xb7ceec calls the jump start 0xb55598(char) (`ret`, one caller 0xb7cf00),
 * then spawns the skill's AreaEffectObject LeaperUltiArea (Effect, follows the owner, its damage word +0xe8 = the
 * damage of its ChainAreaEffect, computed by the handler at 0xb7cf54..0xb7cfa0) through spawnAreaEffect 0xb3970c
 * (superfix.c). While the ulti skill's active counter +8 >= 1 the client treats Mico as airborne (0xb477f4: no fire,
 * MovementSpeed). Missing: the height and the landing hit. Here: the start hook starts a job; while the skill is active
 * the character's z (+0x40) follows a ramp up / hold / ramp down; the landing is the indicator area's ChainAreaEffect
 * (data +0xe0, getter 0xa97c04: LeaperUltiAreaExplosion, Damage + Pushback) spawned at the indicator when it times out:
 * the area update 0xb28c0c calls expire 0xb28f84 only from 0xb28d08, whose `bl` is redirected here. The chain area gets
 * the indicator's kind (+248) and is spawned and started with the shipped helper 0xb35c40 (its damage word is then the
 * chain data's own Damage), so libg's area apply deals the damage and the push. Moves sent while airborne are taken by
 * the shipped mover (the client only drops them during the 1000 ms CastingTime). The indicator's expired byte +244 is set before expire runs (expire sets it itself as
 * its first store), so a generic "chain on expire" hook on 0xb28f84 that checks +244 does not spawn it a second time.
 * Fallback without an indicator (or if it never expires): the chain is spawned at Mico LAND_WAIT ticks after the skill
 * ended.
 *
 * Ww (Carl, WhirlwindUlti, type 8): handler 0xb7d1c8 calls the spin 0xb5a704(char, scaled damage, Damage,
 * MsBetweenAttacks) (`ret`, one caller 0xb7d204); the client changes the move speed while the skill is active. Missing:
 * the contact damage. Here (modelled on env.c charge_contact_tick): while the ulti skill is active, each living enemy
 * character within WW_R of Carl is hit for the scaled damage through the damage root 0xb422d0 (so env's damage model,
 * power cubes and event records apply), at most once per MsBetweenAttacks per target; the owner's super charge is
 * kept (a super's hits do not recharge it, as env.c does for the charge contact and the leap bombs).
 *
 * Blink (Gigi, DaredevilUlti, type 1): handler 0xb7c198 -> 0xb80110(skill, char) calls the teleport 0xb4ffe0(char, tx,
 * ty, areaLeave, areaEnter, scaled damage, Damage, ...) (`ret`; 5 callers). Only its two Blink call sites are taken here
 * (return address 0xb804a8 / 0xb80334; the projectile / component callers 0xb7495c, 0xb75dc0, 0xb9beb0 keep the stub):
 * the leave area is spawned at the start, the brawler is moved to the target (pulled back along the line to a walkable
 * tile: ForceValidTile), the enter area is spawned there, a Damage area (the overcharged DaredevilOverchargedUltiDamage,
 * no Damage of its own) with the scaled damage as its extra damage, so libg's area apply deals it; for an Effect area
 * (DaredevilUltiNoDamageEnter) every living enemy character within its radius is hit once for the scaled damage
 * through the damage root. A
 * BlinkReturn skill (type 23, the swapped-in DaredevilUltiReturn) teleports back to where the last Blink started.
 *
 * ChangeCharacter (Bonnie's CannonGirlSmall, Moe's DiggerDrill, Meg's MechaDude ulti, type 11 via 0xb7d010; also the
 * launch of the CannonGirl charge at 0xb7bb58 and the end of the Digger charge, env.c dig_change): the shipped 0xb4ffec(char, new data) is a stub that kills the old character
 * and returns NULL; battle_fix.c already replaces it (my_die) so a NULL does not crash the caller. battle_fix calls
 * superfix_change_character (weak) first: it builds the new character the way the hero spawner 0xc2806c does (factory
 * 0xb5dd08, add 0xb63198, player / team ids, 0xb59de0 with the player's hero entry, skin 0xc70d2c, components 0xb58068)
 * but without placement, spawn protection or super reset, at the old character's position and facing; the HP fraction
 * carries over (the mech, UniqueProperty 2, starts full); the player's hero id +0x10 is pointed at it so the env's
 * player-to-character lookup and input follow the new form. The stub then retires the old character as before.
 *
 * A type-11 skill with an AreaEffectObject (CannonGirlSmallUlti: CannonGirlExplosion, an Effect area, Damage 620) goes off
 * where the change happens: its server half is compiled out (the case at 0xb7cfe4 only changes the character). The `bl
 * 0xb4ffec` at 0xb7d010 is redirected (change_site): the area is spawned at the old position, owned by the new form, and
 * every living enemy character within its radius is hit once for the skill's Damage through the damage root.
 *
 * CrossSlashGround (Kenji, SamuraiUlti, area type 38): the super's projectile lands and spawns SamuraiCrossSlashArea
 * (0xb73fa8..0xb74020; no Radius, no Damage); the apply's type gate ignores 38 and the slash itself is server code. From
 * the area tick (superfix.c on_area_tick -> superfix_moves_area), once per area: every living enemy character within
 * SLASH_W of one of the two slash lines (an X at +-45 degrees to the throw direction, SLASH_H each way from the area's
 * centre) is hit once for the ulti skill's Damage, and Kenji's own hide status from the cast (SamuraiHide: root,
 * invisibility, shield; CancelOnCharge) ends there (superfix_status_cancel). The X shape and its size are host guesses.
 *
 * Split (R-T, SplitterUlti, type 18): the use-skill code 0xb819fc calls the split 0xb5c7b0(char) (call at 0xb82328), which
 * spawns his Pet SplitterLegs (0xb56e00) at his feet; the rejoin branch after its UniqueProperty 13 test (0xb5c810) is
 * compiled out, and so is the partner getter 0xb392d4 (it tests UniqueProperty 13 and the hero kind, then returns NULL). The
 * client code that uses the partner is shipped: the use-skill code fires the legs' weapon whenever R-T fires his (0xb82ed8),
 * and his component tick 0xb9c42c swaps his weapon to the legs' one (0xb35c3c, superfix_cc.c) and gives him +Value2 speed
 * of his ulti card for 2 ticks (0xb5901c(char, 100, 2, 0), a stub). Here: the getter returns the partner (the head's living
 * legs, or the legs' living head: same player, UniqueProperty 13, the other kind), the speed stub is taken at that call site
 * only (return 0xb9c4fc; superfix_split_speed feeds superfix_status_speed), and the split with legs alive is the rejoin
 * (Radar Waves): R-T moves to his legs, the legs are retired the way 0xb4ffec retires a character (HP 0, +3273), and he heals
 * by Value3 of the legs' ulti card (SplitterLegs_ulti 1000); when the legs' spot is blocked for him (water, a wall) he goes
 * to the nearest walkable spot instead (split_land, on the live map). Legs whose head is gone are retired too, at once when
 * env.c parks a knocked-out head (superfix_split_drop: he keeps full HP while he waits). Once the getter
 * finds no legs, the component swaps the weapon back and the speed lapses. The split head walks over water: the shipped
 * canWalkOverWater 0xb51200 calls isSplit 0xb5a7b0 and drops the result (isSplit's other call, 0xb55560 in 0xb554e4, drops it
 * too, so hooking isSplit would change nothing); my_wow takes 0xb51200 and adds "a head with living legs". A head whose legs
 * went while he stood on water (a linked hit he survived, see env.c split_link) is put on the nearest land by his next
 * tick. env.c does the rest of the server half: the legs' death kills the head (split_link), the storm hits the legs
 * (split_gas); it finds the parts through superfix_split_head / superfix_split_legs, and moves a teammate who would respawn
 * on a split head's water spot to land (superfix_land).
 *
 * Grapple (Buzz, RopeDudeUlti; its projectile's UniqueProperty 5, ProjectileData +0x234): the hit code names the character the
 * torpedo hit to its owner (0xb5c180, from 0xb74a68; the follow target char +0xca0); the pull and the stun are server code.
 * Here (superfix_grapple_end, from spawnfix.c's projectile end): a torpedo that stopped on a character or a wall (end reason 2..4)
 * pulls Buzz in a straight dash to where it hit (env.c's dash mover); when the dash ends, every enemy within GR_STUN_R is
 * stunned (superfix_cc.c), longer the longer the pull. The hypercharged torpedo that stops on a wall gives the super back.
 * The speed, the radius and the stun times are host guesses (no data columns).
 *
 * Portals (Gray, DoorManUlti, type 16): libg drops the two Portal items; their link, the walk-in teleport and the leave /
 * arrive areas are here (portal_tick, see the comment there), the hypercharged pair's shield in hyper.c.
 *
 * Also here, two other summons whose server half is missing: the pets a building spawns by itself (Mr. P's porters from his
 * home base, bpet_tick) and the shadows Sirius stores from his hits (superfix_hit_event, from env.c's damage root).
 *
 * The per-tick work runs from the character tick 0xb3ae74 (enter hook, per character; only characters with a job do
 * anything). NB_SUPERFIX=0 turns every part off (superfix_install does not call this file's install). */
#include "nbhost.h"
#include <math.h>
#include <stdlib.h>
extern Module *g_libg;
extern int g_superfix, g_superfix_dbg;
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
void hook_bl(Module *m, uint64_t off, void *fn);
#define B(off) ((uint8_t *)g_libg->base + (off))
#define I32(p, o) (*(volatile int32_t *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(volatile uint8_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void *volatile *)((uint8_t *)(p) + (o)))
#define VTOF(o) ((int)((uint8_t *)PTR(o, 0) - g_libg->base))
#define VT_CHAR 0x1209020                     /* character vtable (env.c VT_CHAR) */
#define RET_INSN 0xd65f03c0
static int mode(void) { return g_superfix && I32(g_libg->base, 0x12eefb4) == 3; }   /* battle running (spawnfix.c mode()) */

typedef void *(*getp_t)(void *);
typedef int (*geti_t)(void *);
static void *sim_of(void *o) { return ((getp_t)B(0xb6a378))(o); }
static int now_of(void *o) { void *s = sim_of(o); return s ? I32(s, 0x10) : 0; }             /* sim tick (0xc26bd8) */
static void *ulti_skill(uint8_t *ch) {   /* skill slot 1 = ulti (ctor 0xb34560: +0x458 array, +0x464 count) */
    void **sk = PTR(ch, 0x458); return sk && I32(ch, 0x464) > 1 ? sk[1] : NULL;
}
static uint8_t *skill_data(void *sk) { return sk ? ((uint8_t *(*)(void *, int))B(0xb7adfc))(sk, U8(sk, 49) & 1) : NULL; }   /* +49 = overcharged */
static int sd_damage(uint8_t *sd) { return ((geti_t)B(0xb0dc14))(sd); }   /* SkillData Damage getter (gadget.c SD_DAMAGE) */
static int area_radius(uint8_t *ad) { int r = ad ? I32(ad, 0x12c) : 0; return r > 0 && r < 5000 ? r : 0; }   /* AreaEffectData Radius (+300, getter a97bb4; +292 is TimeMs) */
/* the shipped helper 0xb35c40(owner, data, x, y, extra damage, kind, modifiers): create 0xb2aefc, add 0xb63198, start
 * 0xb29494; kind 2 = what the skill execute passes (0xb7bebc). The area's damage word is extra + the data's own Damage
 * (0xb2b0b4), so extra is 0 here, as at every shipped caller, but for the Blink enter area that has no Damage. */
static void *spawn_area(uint8_t *owner, void *data, int x, int y, int dmg, int kind) {
    if (!owner || !data || !PTR(owner, 0x20)) return NULL;
    return ((void *(*)(void *, void *, int, int, int, int, void *))B(0xb35c40))(owner, data, x, y, dmg, kind, NULL);
}

/* damage `v` for `dmg` through the (env-hooked) damage root, the way env.c charge_contact_tick calls it; the owner's
 * super charge (player +0x54) is restored afterwards */
typedef uint64_t (*root_t)(void *, int, int, int, int, void *, void *, int, int, int, void *, int, int, int, int, int, int, int);
static void hit(uint8_t *ch, uint8_t *v, int dmg) {
    void *sim = sim_of(ch); int owner = I32(ch, 0x80), np = sim ? I32(sim, 0x7c) : 0;
    uint8_t *pl = sim && owner >= 0 && owner < np && np <= 64 ? ((uint8_t **)PTR(sim, 0x70))[owner] : NULL;
    int c0 = pl ? I32(pl, 0x54) : 0;
    ((root_t)B(0xb422d0))(v, owner, dmg, dmg, 0, ch, NULL, 1, I32(ch, 0x38), I32(ch, 0x3c), NULL, 0, 0, 0, 1, 0, 0, 0);
    if (pl) I32(pl, 0x54) = c0;
}
static int enemy(uint8_t *ch, uint8_t *c) {   /* a living enemy character (another owner; env.c's charge contact rule) */
    return c && c != ch && VTOF(c) == VT_CHAR && I32(c, 0x3c4) > 0 && !(I32(c, 0x80) == I32(ch, 0x80) && I32(ch, 0x80) >= 0);
}
static void **objs(void *sim, int *n) { void *h = sim ? PTR(sim, 0) : NULL; *n = h ? I32(h, 0xc) : 0; if (*n < 0 || *n > 4096) *n = 0; return h ? (void **)PTR(h, 0) : NULL; }

/* ======================= FlyJump */
#define FJ_H 700           /* [?] peak z, not in the data: the height env.c's leap uses (Piper). Mico's landing hit itself is
                            * LeaperUltiAreaExplosion's own Radius 700, read from the area */
#define FJ_RAMP 6          /* ticks up and down (300 ms) */
#define LAND_WAIT 10       /* ticks after the skill ended without an indicator expiry: land anyway */
typedef struct { uint8_t *ch; int id, t, seen, done_t, landed; void *ind; } FlyJob;
static FlyJob g_fj[16]; static int g_nfj;
static long g_fj_start, g_fj_land, g_fj_fallback;
static void flyjump_start(uint64_t *ctx) {   /* enter 0xb55598(char) */
    uint8_t *ch = (uint8_t *)ctx[0]; if (!mode() || !ch) return;
    void *sk = ulti_skill(ch); uint8_t *sd = skill_data(sk); if (!sd || I32(sd, 0x1a8) != 19) return;
    int k; for (k = 0; k < g_nfj && g_fj[k].ch != ch; k++) {}
    if (k == g_nfj) { if (g_nfj >= 16) return; g_nfj++; }
    g_fj[k] = (FlyJob){ch, I32(ch, 8), 0, 0, 0, 0, PTR(sd, U8(sk, 49) & 1 ? 176 : 160)};   /* AreaEffectObject (OC +176) */
    g_fj_start++;
    if (g_superfix_dbg) LOG("[superfix] flyjump start char %d at %d,%d active %d indicator %p chain %p\n", I32(ch, 8),
                            I32(ch, 0x38), I32(ch, 0x3c), I32(sk, 8), g_fj[k].ind, g_fj[k].ind ? PTR(g_fj[k].ind, 0xe0) : NULL);
}
static void flyjump_land(FlyJob *j, uint8_t *at, int kind, const char *how) {
    void *chain = j->ind ? PTR(j->ind, 0xe0) : NULL;   /* ChainAreaEffect */
    j->landed = 1; I32(j->ch, 0x40) = 0;
    if (!chain || I32(j->ch, 0x3c4) <= 0) return;
    void *a = spawn_area(j->ch, chain, I32(at, 0x38), I32(at, 0x3c), 0, kind);
    g_fj_land++;
    if (g_superfix_dbg) LOG("[superfix] flyjump land (%s) char %d at %d,%d: area %p type %d r %d dmg %d kind %d\n", how, j->id,
                            I32(at, 0x38), I32(at, 0x3c), a, I32(chain, 0x118), area_radius(chain), a ? I32(a, 232) : 0, kind);
}
static void flyjump_tick(FlyJob *j) {
    uint8_t *ch = j->ch; void *sk = ulti_skill(ch); int left = sk ? I32(sk, 8) : 0;
    if (I32(ch, 0x3c4) <= 0) { I32(ch, 0x40) = 0; j->landed = 2; return; }
    j->t++;
    if (left >= 1) j->seen = 1;
    else if (!j->seen && j->t < 40) return;              /* the active counter may be set after the start hook */
    if (left >= 1 && !j->done_t) {
        int up = j->t < FJ_RAMP ? j->t : FJ_RAMP, down = left < FJ_RAMP ? left : FJ_RAMP;
        I32(ch, 0x40) = FJ_H * (up < down ? up : down) / FJ_RAMP;
        return;
    }
    I32(ch, 0x40) = 0;
    if (!j->done_t) j->done_t = j->t;
    if (!j->landed && j->t - j->done_t >= LAND_WAIT) {   /* no indicator expiry seen: land at the brawler */
        g_fj_fallback++; flyjump_land(j, ch, 2, "fallback");
    }
}
/* in place of `bl 0xb28f84` (area expire) at 0xb28d08 */
static void on_area_expire(uint8_t *a) {
    if (mode() && a && !U8(a, 244)) {
        uint8_t *own = PTR(a, 280);   /* the character the area follows */
        for (int i = 0; i < g_nfj; i++) {
            FlyJob *j = &g_fj[i];
            if (j->landed || own != j->ch || !j->ind || ((getp_t)B(0xb6a384))(a) != j->ind) continue;
            if (now_of(a) < I32(a, 216)) continue;           /* a natural timeout only (+216 = end tick) */
            U8(a, 244) = 1;                                  /* expire's own first store, done early (see the header) */
            flyjump_land(j, a, I32(a, 248), "indicator");
        }
    }
    ((void (*)(void *))B(0xb28f84))(a);
}

/* ======================= Ww */
#define WW_R 300           /* [?] contact radius, not in the data or the wiki ("a short radius"): ~ Carl's WhirlwindTrail
                            * area (Radius 300). WhirlwindUlti's CastingRange 7 (700 u) is the cast ring, not the hit radius */
typedef struct { uint8_t *ch; int id, dmg, every, n; int hid[24], ht[24]; } WwJob;
static WwJob g_ww[16]; static int g_nww;
static long g_ww_start, g_ww_hits;
static void ww_start(uint64_t *ctx) {   /* enter 0xb5a704(char, scaled damage, Damage, MsBetweenAttacks) */
    uint8_t *ch = (uint8_t *)ctx[0]; if (!mode() || !ch) return;
    int ms = (int)ctx[3], k;
    for (k = 0; k < g_nww && g_ww[k].ch != ch; k++) {}
    if (k == g_nww) { if (g_nww >= 16) return; g_nww++; }
    g_ww[k] = (WwJob){ch, I32(ch, 8), (int)ctx[1], ms / 50 > 0 ? ms / 50 : 1, 0, {0}, {0}};   /* 50 ms per tick */
    g_ww_start++;
    if (g_superfix_dbg) LOG("[superfix] ww start char %d dmg %d (Damage %d) every %d ms\n", I32(ch, 8), (int)ctx[1], (int)ctx[2], ms);
}
static int ww_tick(WwJob *j) {   /* 0 = job over */
    uint8_t *ch = j->ch; void *sk = ulti_skill(ch); uint8_t *sd = skill_data(sk);
    if (I32(ch, 0x3c4) <= 0 || !sd || I32(sd, 0x1a8) != 8 || I32(sk, 8) < 1) return 0;
    void *sim = sim_of(ch); int now = sim ? I32(sim, 0x10) : 0, n, x = I32(ch, 0x38), y = I32(ch, 0x3c);
    void **v = objs(sim, &n);
    for (int i = 0; i < n; i++) {
        uint8_t *c = v[i]; if (!enemy(ch, c)) continue;
        long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; if (dx * dx + dy * dy > (long)WW_R * WW_R) continue;
        int cid = I32(c, 8), h; for (h = 0; h < j->n && j->hid[h] != cid; h++) {}
        if (h < j->n && now - j->ht[h] < j->every) continue;
        if (h == j->n) { if (j->n >= 24) continue; j->n++; j->hid[h] = cid; }
        j->ht[h] = now;
        int hp0 = I32(c, 0x3c4); hit(ch, c, j->dmg); g_ww_hits++;
        if (g_superfix_dbg) LOG("[superfix] ww hit char %d -> %d: hp %d -> %d\n", j->id, cid, hp0, I32(c, 0x3c4));
        v = objs(sim, &n);   /* the root may add objects */
    }
    return 1;
}

/* ======================= Blink */
static int tile_blocks_move(int id) {   /* tiles.csv BlocksMovement rows (env.c SF_BLOCK) */
    static const int rows[] = {1,2,3,4,6,9,10,11,12,13,14,15,16,18,20,21,39,40,41,42,43,44,45,46,53,54,55,56,57,58,59,60,61,62,63,65,66,69,70,71,72,73};
    for (unsigned i = 0; i < sizeof rows / sizeof *rows; i++) if (id == 27000000 + rows[i]) return 1;
    return 0;
}
static int walkable(void *sim, int x, int y) {   /* env.c walkable(): 300-unit tiles of the sim's map (+0x68) */
    void *m = PTR(sim, 0x68); if (!m) return 1;
    int W = I32(m, 0xc4), Hh = I32(m, 0xc8), tx = (int)floor(x / 300.0), ty = (int)floor(y / 300.0);
    if (tx < 0 || ty < 0 || tx >= W || ty >= Hh) return 0;
    void *t = ((void **)PTR(m, 0x20))[tx + W * ty]; if (!t) return 1;
    void *d = PTR(t, 8); return !d || !tile_blocks_move(I32(d, 0x20));
}
static void stop_mover(void *ch) {   /* env.c sf_stop: not charging, can stop, moving -> stop 0xb4103c */
    if (!U8(ch, 0x490) && (((geti_t)B(0xb50ac8))(ch) & 1) && (((geti_t)B(0xb393f0))(ch) & 1)) ((void (*)(void *))B(0xb4103c))(ch);
}
typedef struct { uint8_t *ch; int x, y; } BlinkHome;
static BlinkHome g_home[16]; static int g_nhome;
static long g_blink, g_blink_back, g_blink_hits;
static void blink_start(uint64_t *ctx) {   /* enter 0xb4ffe0(char, tx, ty, areaLeave, areaEnter, scaled damage, Damage, ...) */
    uint64_t lr = ctx[9] - (uint64_t)g_libg->base;
    if (!mode() || (lr != 0xb804a8 && lr != 0xb80334)) return;   /* the two calls in the Blink handler 0xb80110 */
    uint8_t *ch = (uint8_t *)ctx[0]; void *sim = ch ? sim_of(ch) : NULL; if (!sim || I32(ch, 0x3c4) <= 0) return;
    uint8_t *sd = skill_data(ulti_skill(ch)); int type = sd ? I32(sd, 0x1a8) : -1;
    int tx = (int)ctx[1], ty = (int)ctx[2], dmg = (int)ctx[5], x0 = I32(ch, 0x38), y0 = I32(ch, 0x3c), k;
    uint8_t *aLeave = (uint8_t *)ctx[3], *aEnter = (uint8_t *)ctx[4];
    for (k = 0; k < g_nhome && g_home[k].ch != ch; k++) {}
    if (type == 23) {                                        /* BlinkReturn: back to the remembered start */
        if (k == g_nhome) return;
        tx = g_home[k].x; ty = g_home[k].y; g_blink_back++;
    } else {
        if (k == g_nhome) { if (g_nhome >= 16) return; g_nhome++; }
        g_home[k] = (BlinkHome){ch, x0, y0};
    }
    double L = hypot(tx - x0, ty - y0), back = 0; int lx = tx, ly = ty;   /* ForceValidTile: back along the line */
    while (!walkable(sim, lx, ly) && back < L) {
        back += 50; double f = (L - back) / (L > 1 ? L : 1); if (f < 0) f = 0;
        lx = (int)floor(x0 + (tx - x0) * f + 0.5); ly = (int)floor(y0 + (ty - y0) * f + 0.5);
    }
    if (aLeave) spawn_area(ch, aLeave, x0, y0, 0, 2);
    stop_mover(ch);
    ((void (*)(void *, int, int, int))B(0xb6a61c))(ch, lx, ly, 0);
    if (aEnter) spawn_area(ch, aEnter, lx, ly, type != 23 && I32(aEnter, 0x118) == 0 ? dmg : 0, 2);   /* a Damage area: the scaled damage */
    int r = area_radius(aEnter), hits = 0;
    if (type != 23 && dmg > 0 && r > 0 && (!aEnter || I32(aEnter, 0x118) != 0)) {   /* the enter area does not hit (not Damage) */
        int n; void **v = objs(sim, &n);
        for (int i = 0; i < n; i++) {
            uint8_t *c = v[i]; if (!enemy(ch, c)) continue;
            long dx = I32(c, 0x38) - lx, dy = I32(c, 0x3c) - ly; if (dx * dx + dy * dy > (long)r * r) continue;
            hit(ch, c, dmg); hits++; v = objs(sim, &n);
        }
    }
    g_blink++; g_blink_hits += hits;
    if (g_superfix_dbg) LOG("[superfix] blink type %d char %d %d,%d -> %d,%d (asked %d,%d) leave %p enter %p r %d type %d dmg %d hits %d\n",
                            type, I32(ch, 8), x0, y0, lx, ly, tx, ty, aLeave, aEnter, r, aEnter ? I32(aEnter, 0x118) : -1, dmg, hits);
}

/* ======================= Grapple (Buzz, RopeDudeUlti: a projectile of UniqueProperty 5) */
#define GR_SPEED 3800      /* [?] the pull's speed: RopeDudeUltiProjectile's own Speed (projectiles_logic.csv), no column for it */
#define GR_STUN_R 600      /* [?] the landing stun's radius: no data (the description: "stunning nearby opponents") */
#define GR_STUN_MIN 10     /* [?] stun ticks after the shortest pull (0.5 s; RopeDude_unique min_stun's Value 10 read as ticks) */
#define GR_STUN_MAX 30     /* [?] stun ticks after a pull of GR_FULL u or more (1.5 s): "The stun time increases based on distance" */
#define GR_FULL 3000       /* RopeDudeUlti CastingRange 30 tiles (x100 u, as the skill code's range) */
#define VT_ITEM 0x1209240  /* item vtable (env.c VT_ITEM) */
typedef int (*rad_t)(void *);
static int char_radius(uint8_t *c) { void **vt = *(void ***)c; return ((rad_t)vt[88 / 8])(c); }   /* vtable +88: CollisionRadius (0xb6d974) */
typedef struct { uint8_t *ch, *tgt; int id, tick; } GrHit;
static GrHit g_grh[8]; static int g_ngrh;
typedef struct { uint8_t *ch; int id, x0, y0, start, nostun; } GrJob;
static GrJob g_gr[16]; static int g_ngr;
static long g_gr_char, g_gr_wall, g_gr_land, g_gr_stun, g_gr_reload;
static void grapple_hit(uint64_t *ctx) {   /* enter 0xb5c180(owner, hit character): the hit of a UniqueProperty 5 projectile */
    uint8_t *ch = (uint8_t *)ctx[0], *t = (uint8_t *)ctx[1];
    if (!mode() || !ch || !t) return;
    int k; for (k = 0; k < g_ngrh && g_grh[k].ch != ch; k++) {}
    if (k == g_ngrh) { if (g_ngrh >= 8) k = 0; else g_ngrh++; }
    g_grh[k] = (GrHit){ch, t, I32(ch, 8), now_of(ch)};
}
static int is_oc_proj(uint8_t *ch, void *d) {   /* d is in the brawler's super's OverchargedProjectiles (SkillData +0x68 / +0x74) */
    uint8_t *cd = ((getp_t)B(0xb6a384))(ch), *sd = cd ? PTR(cd, 0x268) : NULL;   /* CharacterData UltimateSkill */
    void **l = sd ? PTR(sd, 0x68) : NULL; int n = sd ? I32(sd, 0x74) : 0;
    for (int k = 0; l && k < n && k < 8; k++) if (l[k] == d) return 1;
    return 0;
}
int env_dash_start(uint8_t *ch, int tx, int ty, int speed);   /* env.c: the native charge mover, no contact job */
int superfix_cc_stun(uint8_t *ch, int ticks, const char *why);
int gadget_buoy_nostun(uint8_t *ch) __attribute__((weak));   /* gadget.c: Buzz's Reserve Buoy, "his next Super does not stun" */
static int walkable_now(void *sim, int x, int y);
/* spawnfix.c's projectile end (0xb75998): a grapple that stopped (reason 3: on a character it does not pierce; 2 / 4: the
 * other stops of the projectile tick 0xb70650..0xb70668, the wall in a live trace: Buzz's torpedo at the wall tile) pulls
 * its owner there (a straight dash, the path Bull's charge lays); the hypercharged one (the super's OverchargedProjectiles:
 * RopeDudeOverchargedUltiProjectile) that stopped on a wall gives the super back ("Buzz's torpedo can now be used again if he
 * hits a wall": player +0x54 = max +0x58) */
void superfix_grapple_end(uint8_t *pr, int reason) {
    uint8_t *d = pr ? PTR(pr, 0x10) : NULL, *ch = pr ? PTR(pr, 0xe0) : NULL;
    if (!mode() || !pr || I32(pr, 0x90) != 0) return;
    if (!d || I32(d, 0x234) != 5 || !ch || VTOF(ch) != VT_CHAR || I32(ch, 0x3c4) <= 0) return;   /* ProjectileData UniqueProperty (getter 0xafab98) */
    static uint8_t *nlast; static int nlast_start, nostun;   /* issue #46: the torpedo after a Reserve Buoy, hit or miss */
    if (pr != nlast || I32(pr, 0x28) != nlast_start) { nlast = pr; nlast_start = I32(pr, 0x28); nostun = gadget_buoy_nostun && gadget_buoy_nostun(ch); }
    if (reason < 2 || reason > 4) return;   /* 1: range end (a miss: no pull) */
    static uint8_t *last; static int last_start;
    if (pr == last && I32(pr, 0x28) == last_start) return;
    last = pr; last_start = I32(pr, 0x28);
    void *sim = sim_of(ch); if (!sim) return;
    int now = I32(sim, 0x10), x0 = I32(ch, 0x38), y0 = I32(ch, 0x3c), tx = I32(pr, 0x38), ty = I32(pr, 0x3c), k;
    uint8_t *t = NULL;
    for (k = 0; k < g_ngrh; k++) if (g_grh[k].ch == ch && g_grh[k].id == I32(ch, 8) && now - g_grh[k].tick <= 1) t = g_grh[k].tgt;
    if (t && (VTOF(t) != VT_CHAR || I32(t, 0x3c4) <= 0)) t = NULL;
    if (t) { tx = I32(t, 0x38); ty = I32(t, 0x3c); g_gr_char++; }
    else {   /* the wall: back along the throw to open ground */
        double L = hypot(tx - x0, ty - y0);
        for (double b = 0; b < L && !walkable_now(sim, tx, ty); b += 50) {
            tx = (int)floor(x0 + (I32(pr, 0x38) - x0) * (L - b) / L + 0.5); ty = (int)floor(y0 + (I32(pr, 0x3c) - y0) * (L - b) / L + 0.5); }
        g_gr_wall++;
        if (is_oc_proj(ch, d)) {
            int owner = I32(ch, 0x80), np = I32(sim, 0x7c);
            uint8_t *pl = owner >= 0 && owner < np && np <= 64 ? ((uint8_t **)PTR(sim, 0x70))[owner] : NULL;
            if (pl) { I32(pl, 0x54) = I32(pl, 0x58); g_gr_reload++; }
        }
    }
    /* the hit's follow target (char +0xca0, x/y +0xca8 / +0xcac, set by 0xb5c180): the character tick re-paths toward it once
     * it moves (0xb3ba6c..0xb3bbfc) and drops the charge flag doing so; the pull goes to where it was hit, so it is cleared as
     * 0xb5c180(owner, NULL) does */
    PTR(ch, 0xca0) = NULL; I32(ch, 0xca8) = -1; I32(ch, 0xcac) = -1;
    uint8_t s98d = U8(ch, 0x98d), s98e = U8(ch, 0x98e);
    U8(ch, 0x98d) = 1; U8(ch, 0x98e) = 1;   /* a straight path (env.c native_charge_start, Bull) */
    int len = env_dash_start(ch, tx, ty, GR_SPEED);
    U8(ch, 0x98d) = s98d; U8(ch, 0x98e) = s98e;
    if (len > 0) {
        for (k = 0; k < g_ngr && g_gr[k].ch != ch; k++) {}
        if (k == g_ngr && g_ngr < 16) g_ngr++;
        if (k < 16) g_gr[k] = (GrJob){ch, I32(ch, 8), x0, y0, now, nostun};
    }
    if (g_superfix_dbg) LOG("[superfix] grapple char %d: %s at %d,%d, pull %d u%s\n", I32(ch, 8), t ? "character" : "wall", tx, ty, len,
                            !t && is_oc_proj(ch, d) ? ", super given back" : "");
}
static int grapple_tick(GrJob *j) {   /* 0 = job over: the pull ended -> the landing stun */
    uint8_t *ch = j->ch; void *sim = sim_of(ch); int now = sim ? I32(sim, 0x10) : 0;
    if (I32(ch, 8) != j->id || now < j->start || now - j->start > 100 || I32(ch, 0x3c4) <= 0) return 0;
    if (now == j->start || U8(ch, 0x490)) return 1;
    int x = I32(ch, 0x38), y = I32(ch, 0x3c), n, hits = 0;
    double dist = hypot(x - j->x0, y - j->y0); if (dist > GR_FULL) dist = GR_FULL;
    int ticks = GR_STUN_MIN + (int)((GR_STUN_MAX - GR_STUN_MIN) * dist / GR_FULL);
    void **v = objs(sim, &n);
    for (int i = 0; i < n && !j->nostun; i++) {   /* nostun: the first super after a Reserve Buoy (gadget.c) */
        uint8_t *c = v[i]; if (!enemy(ch, c) || I32(c, 0x84) == I32(ch, 0x84)) continue;
        long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; if (dx * dx + dy * dy > (long)GR_STUN_R * GR_STUN_R) continue;
        superfix_cc_stun(c, ticks, "grapple landing"); hits++;
    }
    g_gr_land++; g_gr_stun += hits;
    if (g_superfix_dbg) LOG("[superfix] grapple landing char %d at %d,%d after %.0f u: %d stunned for %d ticks%s\n", j->id, x, y, dist, hits, ticks,
                            j->nostun ? " (Reserve Buoy: no stun)" : "");
    return 0;
}

/* ======================= Portals (Gray, DoorManUlti, BehaviorType 16) */
/* libg's Portals handler (0xb7d198..0xb7e7e0) drops the pair: one Portal item (ItemData +84 == 0x31) at Gray, one at the skill's
 * target, each with the player (+0x80), team (+0x84), pair number (+0x2c0), overcharged byte (+0x2c4: OverChargedPortal from the
 * hypercharged super) and its leave / arrive area ids (+0x2e4 / +0x2e8); before that it destroys the oldest of his pairs of the
 * same kind past the limit (2, or the hypercharge card's Value) together with the partner in item +0x128, which only the server
 * fills. The walk-in is server code too. Here: each tick the two portals of a cast are linked through +0x128 (so a third cast
 * destroys a whole pair, not a NULL partner), and a character of the portal's team that steps into one (the client pickup range:
 * TriggerRangeSubTiles (ItemData +0xe0) x 100 + its CollisionRadius, 0xb6d964..0xb6d9bc) is moved to the partner, the item's
 * CustomAreaEffect1 (leave, 0xae81b4) spawned at the one it entered and CustomAreaEffect2 (arrive, 0xae81bc) at the one it
 * reached; it goes again only after it has left the portal it arrived in (a door that opens under it does not move it). A hypercharged pair shields (hyper.c
 * hyper_portal_shield). [?] no cooldown: the data has none (Portal Value 1 is the count the handler caps). */
#define PORTAL_KIND 0x31
typedef struct { uint8_t *ch, *in; int id; } PIn;   /* the portal a character stands in (NULL: none) */
static PIn g_pin[32]; static int g_npin;
static uint8_t *g_portal[16]; static int g_nportal, g_portal_tick = -1, g_portal_new[16]; static void *g_portal_sim;
static struct { uint8_t *p; int id, tick; } g_pseen[32]; static int g_npseen;   /* when each portal was first seen */
static long g_portal_tp, g_portal_links, g_portal_shields;
int hyper_portal_shield(void *ch, int player) __attribute__((weak));   /* hyper.c */
static void portals_scan(void *sim, int now) {   /* once per tick: the live portals, partners linked */
    if (sim == g_portal_sim && now == g_portal_tick) return;
    if (sim != g_portal_sim || now < g_portal_tick) g_npin = g_npseen = 0;   /* a new battle or episode */
    g_portal_sim = sim; g_portal_tick = now; g_nportal = 0;
    int n; void **v = objs(sim, &n);
    for (int i = 0; i < n && g_nportal < 16; i++) {
        uint8_t *o = v[i]; if (!o || VTOF(o) != VT_ITEM || U8(o, 144)) continue;   /* +144: destroyed (0xb6e0b0) */
        uint8_t *d = ((getp_t)B(0xb6a384))(o); if (!d || I32(d, 84) != PORTAL_KIND) continue;
        int k; for (k = 0; k < g_npseen && !(g_pseen[k].p == o && g_pseen[k].id == I32(o, 8)); k++) {}
        if (k == g_npseen) { if (g_npseen >= 32) g_npseen = k = 0; g_pseen[g_npseen++] = (typeof(g_pseen[0])){o, I32(o, 8), now}; }
        g_portal_new[g_nportal] = g_pseen[k].tick == now || now < g_pseen[k].tick; g_portal[g_nportal++] = o;
    }
    for (int i = 0; i < g_nportal; i++) {
        uint8_t *p = g_portal[i]; if (PTR(p, 0x128)) continue;
        for (int j = i + 1; j < g_nportal; j++) {
            uint8_t *q = g_portal[j];
            if (PTR(q, 0x128) || I32(q, 0x80) != I32(p, 0x80) || I32(q, 0x2c0) != I32(p, 0x2c0) || U8(q, 0x2c4) != U8(p, 0x2c4)) continue;
            PTR(p, 0x128) = q; PTR(q, 0x128) = p; g_portal_links++; break;
        }
    }
}
static void portal_tick(uint8_t *ch) {
    void *sim = sim_of(ch); if (!sim) return;
    int now = I32(sim, 0x10); portals_scan(sim, now);
    int k; for (k = 0; k < g_npin && !(g_pin[k].ch == ch && g_pin[k].id == I32(ch, 8)); k++) {}
    if (!g_nportal && k == g_npin) return;
    uint8_t *in = NULL; int x = I32(ch, 0x38), y = I32(ch, 0x3c), r = I32(ch, 0x3c4) > 0 ? char_radius(ch) : 0;
    for (int i = 0; i < g_nportal && I32(ch, 0x3c4) > 0; i++) {
        uint8_t *p = g_portal[i], *d = ((getp_t)B(0xb6a384))(p);
        if (I32(p, 0x84) != I32(ch, 0x84)) continue;   /* his team's doors only */
        long range = (long)I32(d, 0xe0) * 100 + r, dx = I32(p, 0x38) - x, dy = I32(p, 0x3c) - y;
        if (dx * dx + dy * dy <= range * range && (!in || (k < g_npin && p == g_pin[k].in))) in = p;   /* the one he is
                                               * in stays his, so a door over the one he arrived in does not send him on */
    }
    int fresh = 0; for (int i = 0; in && i < g_nportal; i++) if (g_portal[i] == in) fresh = g_portal_new[i];   /* a door that
                                                * opened under him (Gray's own at his feet) counts as one he is already in */
    if (k == g_npin) { if (!in || g_npin >= 32) return; g_pin[g_npin++] = (PIn){ch, fresh ? in : NULL, I32(ch, 8)}; }
    uint8_t *q = in ? PTR(in, 0x128) : NULL;
    if (in && in != g_pin[k].in && !fresh && q && !U8(q, 144) && !U8(ch, 0x490)) {   /* stepped in (not in a dash / charge) */
        uint8_t *d = ((getp_t)B(0xb6a384))(in);
        void *aLeave = ((getp_t)B(0xae81b4))(d), *aArrive = ((getp_t)B(0xae81bc))(d);
        int px = I32(in, 0x38), py = I32(in, 0x3c), qx = I32(q, 0x38), qy = I32(q, 0x3c);
        stop_mover(ch);
        ((void (*)(void *, int, int, int))B(0xb6a61c))(ch, qx, qy, 0);
        if (aLeave) spawn_area(ch, aLeave, px, py, 0, 2);
        if (aArrive) spawn_area(ch, aArrive, qx, qy, 0, 2);
        int sh = U8(in, 0x2c4) && hyper_portal_shield ? hyper_portal_shield(ch, I32(in, 0x80)) : 0;
        g_portal_tp++; g_portal_shields += sh > 0;
        if (g_superfix_dbg) LOG("[superfix] portal: char %d %d,%d -> %d,%d (pair %d of player %d%s), shield %d\n", I32(ch, 8), px, py, qx, qy,
                                I32(in, 0x2c0), I32(in, 0x80), U8(in, 0x2c4) ? ", hypercharged" : "", sh);
        in = q;
    }
    g_pin[k].in = in;
    if (!in && !g_nportal) g_pin[k] = g_pin[--g_npin];
}

/* ======================= Attach (Kit, AttacherUlti: a charge of type 19) */
/* The jump is env.c's native charge (type 19, its contact hit); what happens where Kit lands is server code. Here, when a type-19
 * charge ends, the nearest other living character within KIT_GRAB_R of Kit is grabbed:
 *   - an enemy gets his CharacterData StatusEffect AttacherUltiDot (Damage 125 every TriggerRate 20 ticks, DurationTicks 40)
 *     and Kit rides on it for those 40 ticks ("damages enemies over time"); hypercharged, the enemy is stunned for them instead
 *     and Kit stays free (TID_ATTACHER_OVERCHARGE_DESC "Kit's Super stuns the enemy but he can move and attack normally");
 *   - a teammate carries him for his ulti card's Value seconds (Attacher_ulti 20) and is healed KIT_HEAL every 20 ticks (x
 *     KIT_OC_HEAL % hypercharged: "Attaching to teammates will heal them more"); while attached his weapon is its SecondarySkill
 *     (AttacherWeaponAlternate, the yarn balls; hypercharged SecondarySkill2, AttacherWeaponAlternateOvercharge: CastingRange 30
 *     vs 22, "his Yarn Balls have a longer range"), through superfix_cc.c's swap. A rider is put on his carrier every tick.
 * [?] the grab radius, the teammate's carry time and heal and the hypercharged stun time are host guesses (see the numbers). */
#define KIT_GRAB_R 400     /* [?] landing within 400 u (between centres) of a character grabs it */
#define KIT_HEAL 125       /* [?] a carrier's heal per 20 ticks: AttacherUltiDot's Damage, read as the heal (no heal column) */
#define KIT_OC_HEAL 150    /* [?] hypercharged: the heal x 150 % (the description: "heal them more"; no number) */
typedef struct { uint8_t *ch, *on; int id, on_id, until, next, ally, oc, jumping; } KitJob;
static KitJob g_kit[8]; static int g_nkit;
static long g_kit_jumps, g_kit_ally, g_kit_enemy, g_kit_stun, g_kit_heal;
static int card_value(void *cd, int meta, int k);
static void *status_named(const char *name) {   /* status_effects row by name (table 117, as hyper.c data_named) */
    extern void *div_data(int id);
    static void *cache; static int done; if (done) return cache;
    for (int idx = 0, miss = 0; idx < 4000 && miss < 64; idx++) {
        uint8_t *d = div_data(117000000 + idx);
        if (!d) { miss++; continue; }
        miss = 0;
        void *s = PTR(d, 8) ? ((void *(*)(void *, int))B(0xcf6a28))(PTR(d, 8), 0) : NULL;
        if (s && (((int (*)(void *, const char *))B(0xe9779c))(s, name) & 1)) { cache = d; break; }
    }
    done = 1; return cache;
}
static void kit_land(KitJob *j, void *sim, int now) {
    uint8_t *ch = j->ch, *best = NULL; long bd = (long)KIT_GRAB_R * KIT_GRAB_R; int n, x = I32(ch, 0x38), y = I32(ch, 0x3c);
    void **v = objs(sim, &n);
    for (int i = 0; i < n; i++) {
        uint8_t *c = v[i]; if (!c || c == ch || VTOF(c) != VT_CHAR || I32(c, 0x3c4) <= 0 || I32(c, 0x80) < 0) continue;
        long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; if (dx * dx + dy * dy >= bd) continue;
        bd = dx * dx + dy * dy; best = c;
    }
    j->on = NULL; if (!best) return;
    uint8_t *cd = ((getp_t)B(0xb6a384))(ch), *own = cd ? PTR(cd, 0x260) : NULL;
    j->ally = I32(best, 0x84) == I32(ch, 0x84);
    if (j->ally) {
        int secs = card_value(cd, 3, 1);   /* Attacher_ulti Value (cards.csv MetaType 3) */
        j->on = best; j->on_id = I32(best, 8); j->until = now + (secs > 0 ? secs : 20) * 20; j->next = now + 20; g_kit_ally++;
        void *w = own ? PTR(own, j->oc ? 0x160 : 0x158) : NULL;   /* SkillData SecondarySkill / SecondarySkill2 */
        extern void superfix_cc_weapon(uint8_t *, void *) __attribute__((weak));
        if (w && superfix_cc_weapon) superfix_cc_weapon(ch, w);
        if (g_superfix_dbg) LOG("[superfix] kit %d rides teammate %d for %d ticks%s, weapon -> skill %d\n", j->id, j->on_id, j->until - now,
                                j->oc ? " (hypercharged)" : "", w ? I32(w, 0x20) : -1);
        return;
    }
    uint8_t *st = status_named("AttacherUltiDot");   /* CharacterData StatusEffect (characters.csv) */
    if (st) ((void (*)(void *, void *, int, int, void *, void *, int, int, int, int, int))B(0xb35dd0))(best, st, I32(ch, 0x80),
        I32(ch, 0x84), ch, ch, 2, 0, -1, -1, 0);
    g_kit_enemy++;
    if (j->oc) { superfix_cc_stun(best, 40, "kit hypercharged super"); g_kit_stun++; }   /* AttacherUltiDot DurationTicks 40 */
    else { j->on = best; j->on_id = I32(best, 8); j->until = now + 40; }                 /* rides it as long as the Dot lasts */
    if (g_superfix_dbg) LOG("[superfix] kit %d grabs enemy %d (dot %p)%s\n", j->id, I32(best, 8), st, j->oc ? ": stunned, Kit free" : "");
}
static int kit_tick(KitJob *j) {   /* 0 = job over */
    uint8_t *ch = j->ch; void *sim = sim_of(ch); int now = sim ? I32(sim, 0x10) : 0;
    if (I32(ch, 8) != j->id || I32(ch, 0x3c4) <= 0) return 0;
    if (j->jumping) {
        if (U8(ch, 0x490) && I32(ch, 0x508) == 19) return 1;
        j->jumping = 0; kit_land(j, sim, now);
        return j->on != NULL;
    }
    uint8_t *on = j->on;
    int alive = on && I32(on, 8) == j->on_id && VTOF(on) == VT_CHAR && I32(on, 0x3c4) > 0;
    if (!alive || now >= j->until || (U8(ch, 0x490) && I32(ch, 0x508) == 19)) {   /* let go (a new jump starts its own job) */
        extern void superfix_cc_weapon(uint8_t *, void *) __attribute__((weak));
        if (j->ally && superfix_cc_weapon) superfix_cc_weapon(ch, NULL);
        if (g_superfix_dbg) LOG("[superfix] kit %d lets go of %d\n", j->id, j->on_id);
        return 0;
    }
    stop_mover(ch);
    ((void (*)(void *, int, int, int))B(0xb6a61c))(ch, I32(on, 0x38), I32(on, 0x3c), 0);
    if (j->ally && now >= j->next) {
        int mx = I32(on, 0x3c8), hp = I32(on, 0x3c4), h = j->oc ? KIT_HEAL * KIT_OC_HEAL / 100 : KIT_HEAL;
        if (hp < mx) { I32(on, 0x3c4) = hp + h < mx ? hp + h : mx; g_kit_heal++; }
        j->next = now + 20;
    }
    return 1;
}
static void kit_watch(uint8_t *ch) {   /* a type-19 charge started: a job (one per Kit) */
    if (!U8(ch, 0x490) || I32(ch, 0x508) != 19) return;
    int k; for (k = 0; k < g_nkit && !(g_kit[k].ch == ch && g_kit[k].id == I32(ch, 8)); k++) {}
    if (k < g_nkit && g_kit[k].jumping) return;
    if (k < g_nkit && g_kit[k].ally) { extern void superfix_cc_weapon(uint8_t *, void *) __attribute__((weak)); if (superfix_cc_weapon) superfix_cc_weapon(ch, NULL); }
    if (k == g_nkit) { if (g_nkit >= 8) return; g_nkit++; }
    uint8_t **sk = PTR(ch, 0x458);
    int oc = (sk && I32(ch, 0x464) > 1 && sk[1] && (U8(sk[1], 0x31) & 1)) ||   /* the super's overcharged latch (0xb82d34) */
             ((int (*)(void *))B(0xb35bf0))(ch);   /* or isOvercharged now (hyper.c answers it): the charge skill sets no latch */
    g_kit[k] = (KitJob){ch, NULL, I32(ch, 8), 0, 0, 0, 0, oc, 1}; g_kit_jumps++;
}

/* ======================= ChangeCharacter: the new character for battle_fix.c's hook on 0xb4ffec */
static long g_change, g_change_skip;
void env_char_changed(uint8_t *old, uint8_t *nc) __attribute__((weak));   /* env.c: the power cubes move to the new form */
uint64_t superfix_change_character(uint8_t *old, uint8_t *nd) {   /* the new character, or 0 (battle_fix keeps the old) */
    if (!mode() || !old || !nd || VTOF(old) != VT_CHAR || !PTR(old, 0x20)) { g_change_skip++; return 0; }
    uint8_t *pl = ((uint8_t *(*)(void *))B(0xb6a718))(old), *sim = sim_of(old);
    void *cfg = pl ? ((getp_t)B(0xc41460))(pl) : NULL;               /* the player's hero entry (spawner's x3) */
    if (!pl || !sim || !cfg) { g_change_skip++; return 0; }
    uint8_t *nc = ((uint8_t *(*)(void *))B(0xb5dd08))(nd);          /* factory: alloc 0xf18 + character ctor */
    if (!nc) { g_change_skip++; return 0; }
    U8(nc, 3741) = U8(old, 3741);
    ((void (*)(void *, void *))B(0xb63198))(PTR(old, 0x20), nc);   /* add to the object manager (spawner order) */
    I32(nc, 128) = I32(old, 128); I32(nc, 132) = I32(old, 132); I32(nc, 136) = I32(old, 136);   /* player, team, ... */
    U8(nc, 1129) = U8(old, 1129);
    ((void (*)(void *, void *, int))B(0xb59de0))(nc, cfg, 0);       /* level, HP, skills, cards */
    I32(nc, 1260) = I32(sim, 0x10);
    ((void (*)(void *))B(0xb5a638))(nc);
    void *sc = PTR(pl, 472);                                         /* skin as the spawner's caller picks it (0xc27940) */
    if (!sc) { void **hs = PTR(pl, 48); int hi = I32(pl, 64); sc = hs && hi >= 0 && hs[hi] ? PTR(hs[hi], 32) : NULL; }
    PTR(nc, 24) = sc ? ((void *(*)(void *, void *, int))B(0xc70d2c))(sc, nd, 0) : PTR(old, 24);
    I32(nc, 1824) = I32(old, 1824);
    /* no placement 0xc2ca08, spawn protection or super reset (spawn-only): the new form stands where the old one was */
    ((void (*)(void *, int, int, int))B(0xb6a61c))(nc, I32(old, 0x38), I32(old, 0x3c), 0);
    I32(nc, 800) = I32(old, 800);                                    /* facing */
    ((void (*)(void *))B(0xb58068))(nc);                             /* the data's Components (Brawler_MechaDude) */
    int hp = I32(old, 0x3c4), mhp = I32(old, 0x3c8), up = ((geti_t)B(0xab3d04))(nd);
    if (up != 2 && hp > 0 && mhp > 0) {   /* the HP fraction carries over; the mech (UniqueProperty 2) and a form after a death start full */
        long v = (long)I32(nc, 0x3c8) * hp / mhp; I32(nc, 0x3c4) = v < 1 ? 1 : (int)v;
    }
    I32(pl, 0x10) = I32(nc, 8);   /* the player's hero id (env player_char_id, the input path); +0x1e4 is the possession link
                                     (Willow): a character whose possession timer +3284 is 0 clears it at once (0xb40f30) */
    if (env_char_changed) env_char_changed(old, nc);
    g_change++;
    if (g_superfix_dbg) LOG("[superfix] change character %d (data %p hp %d/%d) -> %d (data %p hp %d/%d) at %d,%d\n", I32(old, 8),
                            PTR(old, 0x10), hp, mhp, I32(nc, 8), nd, I32(nc, 0x3c4), I32(nc, 0x3c8), I32(nc, 0x38), I32(nc, 0x3c));
    return (uint64_t)nc;
}

/* ======================= ChangeCharacter with an area (Bonnie's return to Clyde): hook_bl on 0xb7d010 */
static long g_change_area, g_change_hits;
static uint64_t change_site(uint8_t *old, void *nd, uint64_t a2, uint64_t a3) {
    uint8_t *sd = old && mode() ? skill_data(ulti_skill(old)) : NULL;   /* read before the stub retires the old character */
    void *ad = sd && I32(sd, 0x1a8) == 11 ? PTR(sd, 160) : NULL;       /* AreaEffectObject (skill data +160, getter 0xb0de40) */
    int x = old ? I32(old, 0x38) : 0, y = old ? I32(old, 0x3c) : 0, dmg = sd ? sd_damage(sd) : 0;
    uint8_t *nc = (uint8_t *)((uint64_t (*)(void *, void *, uint64_t, uint64_t))B(0xb4ffec))(old, nd, a2, a3);
    if (!ad || !nc || VTOF(nc) != VT_CHAR || I32(nc, 0x3c4) <= 0) return (uint64_t)nc;
    spawn_area(nc, ad, x, y, 0, 2); g_change_area++;
    int r = area_radius(ad), hits = 0, n;
    if (I32(ad, 0x118) == 6 && r > 0 && dmg > 0) {   /* an Effect area hits no one in libg: the skill's Damage by hand (raw: env's root scales it) */
        void **v = objs(sim_of(nc), &n);
        for (int i = 0; i < n; i++) {
            uint8_t *c = v[i]; if (!enemy(nc, c) || I32(c, 0x84) == I32(nc, 0x84)) continue;
            long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; if (dx * dx + dy * dy > (long)r * r) continue;
            hit(nc, c, dmg); hits++; v = objs(sim_of(nc), &n);
        }
    }
    g_change_hits += hits;
    if (g_superfix_dbg) LOG("[superfix] change with area: char %d -> %d at %d,%d area type %d r %d dmg %d hits %d\n",
                            old ? I32(old, 8) : -1, I32(nc, 8), x, y, I32(ad, 0x118), r, dmg, hits);
    return (uint64_t)nc;
}

/* ======================= CrossSlashGround (Kenji): superfix.c's area tick calls this for every area */
#define SLASH_H 600   /* [?] half-length of each slash line (2 tiles): the server's geometry is compiled out */
#define SLASH_W 250   /* [?] half-width of a slash line incl. the victim's CollisionRadius (env.c's CHARGE_HIT_R) */
typedef struct { void *a; int start; } SlashRec;
static SlashRec g_slash[32]; static int g_nslash_rec, g_slash_last = -1; static long g_slash_n, g_slash_hits;
void superfix_status_cancel(uint8_t *ch, int within) __attribute__((weak));
void superfix_moves_area(uint8_t *a) {
    if (!mode() || !a) return;
    uint8_t *d = ((getp_t)B(0xb6a384))(a); if (!d || I32(d, 0x118) != 38) return;
    int start = I32(a, 0xd0), now = now_of(a);
    if (now < g_slash_last) g_nslash_rec = 0;   /* the tick went back: a new episode, area objects are reused */
    g_slash_last = now;
    for (int k = 0; k < g_nslash_rec; k++) if (g_slash[k].a == a && g_slash[k].start == start) return;   /* once per area */
    if (g_nslash_rec >= 32) g_nslash_rec = 0;
    g_slash[g_nslash_rec++] = (SlashRec){a, start};
    uint8_t *ch = PTR(a, 0x108);
    if (!ch || VTOF(ch) != VT_CHAR || I32(ch, 0x3c4) <= 0) return;
    uint8_t *sd = skill_data(ulti_skill(ch)); int dmg = sd && I32(sd, 0x1a8) == 0 ? sd_damage(sd) : 0;
    if (dmg <= 0) return;
    double cx = I32(a, 0x38), cy = I32(a, 0x3c), fx = cx - I32(ch, 0x38), fy = cy - I32(ch, 0x3c), fl = hypot(fx, fy);
    if (fl < 1) { fx = 1; fy = 0; } else { fx /= fl; fy /= fl; }
    double ux[2] = {(fx - fy) * M_SQRT1_2, (fx + fy) * M_SQRT1_2}, uy[2] = {(fy + fx) * M_SQRT1_2, (fy - fx) * M_SQRT1_2};   /* +-45 degrees */
    int n, hits = 0; void **v = objs(sim_of(ch), &n);
    for (int i = 0; i < n; i++) {
        uint8_t *c = v[i]; if (!enemy(ch, c) || I32(c, 0x84) == I32(ch, 0x84)) continue;
        double px = I32(c, 0x38) - cx, py = I32(c, 0x3c) - cy; int in = 0;
        for (int l = 0; l < 2 && !in; l++) {
            double along = px * ux[l] + py * uy[l], across = fabs(px * uy[l] - py * ux[l]);
            in = fabs(along) <= SLASH_H && across <= SLASH_W;
        }
        if (!in) continue;
        hit(ch, c, dmg); hits++; v = objs(sim_of(ch), &n);
    }
    if (superfix_status_cancel) superfix_status_cancel(ch, 60);   /* SamuraiHide ends at the slash (CancelOnCharge) */
    g_slash_n++; g_slash_hits += hits;
    if (g_superfix_dbg) LOG("[superfix] cross slash char %d at %.0f,%.0f dir %.2f,%.2f dmg %d hits %d\n", I32(ch, 8), cx, cy, fx, fy, dmg, hits);
}

/* ======================= Split (R-T) */
#define SPLIT_HEAL 1000    /* fallback heal at the rejoin: Value3 of SplitterLegs_ulti (cards.csv, the heal icon), read from
                            * the card when it is there; x P11_SCALE at the rejoin (power 1, issue #22) */
static long g_split_rejoin, g_split_spd, g_split_orphan; static int g_split_on;
static int up_of(void *c) { void *d = c ? ((getp_t)B(0xb6a384))(c) : NULL; return d ? ((geti_t)B(0xab3d04))(d) : -1; }
static int hero_kind(void *c) { return ((geti_t)B(0xb34de4))(c) & 1; }   /* +1064 or the data's type in {0, 26} (0xab2fd0) */
static uint8_t *split_partner(uint8_t *ch) {   /* in place of 0xb392d4: the head's legs or the legs' head, NULL = none */
    if (!mode() || !ch || VTOF(ch) != VT_CHAR || up_of(ch) != 13 || I32(ch, 0x80) < 0) return NULL;
    int hk = hero_kind(ch), own = I32(ch, 0x80), n; void **v = objs(sim_of(ch), &n);
    for (int i = 0; v && i < n; i++) {
        uint8_t *c = v[i];
        if (c && c != ch && VTOF(c) == VT_CHAR && I32(c, 0x3c4) > 0 && I32(c, 0x80) == own && up_of(c) == 13 && hero_kind(c) != hk) return c;
    }
    return NULL;
}
static int card_value(void *cd, int meta, int k) {   /* the character's card of MetaType `meta`, its Value k (0xace760 / 0xaa9568) */
    void *card = cd ? ((void *(*)(void *, int))B(0xace760))(cd, meta) : NULL;
    return card ? ((int (*)(void *, int))B(0xaa9568))(card, k) : -1;
}
static void retire(uint8_t *c) { I32(c, 0x3c4) = 0; U8(c, 3273) = 1; }   /* 0xb4ffec's end: HP 0, the retired flag */
/* env.c: R-T's legs (UniqueProperty 13, not the hero kind), and the living head of legs (NULL: none, or not legs) */
int superfix_split_legs(uint8_t *c) { return g_split_on && mode() && c && VTOF(c) == VT_CHAR && up_of(c) == 13 && !hero_kind(c); }
uint8_t *superfix_split_head(uint8_t *legs) { return superfix_split_legs(legs) ? split_partner(legs) : NULL; }
/* env.c: R-T's head is knocked out (duo / trio: parked at full HP, so the partner lookup would still see him) -> his legs go */
void superfix_split_drop(uint8_t *head) {
    if (!g_split_on || !mode() || !head || VTOF(head) != VT_CHAR || up_of(head) != 13 || !hero_kind(head)) return;
    uint8_t *legs = split_partner(head); if (!legs) return;
    retire(legs); g_split_orphan++;
    if (g_superfix_dbg) LOG("[superfix] split: legs %d retired (head %d knocked out)\n", I32(legs, 8), I32(head, 8));
}
static int walkable_now(void *sim, int x, int y) {   /* walkable() on the live tile data (+0, Open once a wall is broken; +8 is
                                                       * the battle-start one), as env.c snap_map */
    void *m = PTR(sim, 0x68); if (!m) return 1;
    int W = I32(m, 0xc4), Hh = I32(m, 0xc8), tx = (int)floor(x / 300.0), ty = (int)floor(y / 300.0);
    if (tx < 0 || ty < 0 || tx >= W || ty >= Hh) return 0;
    void *t = ((void **)PTR(m, 0x20))[tx + W * ty]; if (!t) return 1;
    void *d = PTR(t, 0) ? PTR(t, 0) : PTR(t, 8); return !d || !tile_blocks_move(I32(d, 0x20));
}
#define SPLIT_LAND_STEP 100   /* [?] the search for land: rings every 100 u up to 900 u (3 tiles), 16 points each. The research */
#define SPLIT_LAND_MAX 900    /* (RADAR WAVES: "if the legs stand on water, R-T is pushed to the nearest land") has no distance */
static int split_land(void *sim, int *x, int *y) {   /* a blocked spot -> the nearest walkable one; 1 = moved */
    if (!sim || walkable_now(sim, *x, *y)) return 0;
    for (int r = SPLIT_LAND_STEP; r <= SPLIT_LAND_MAX; r += SPLIT_LAND_STEP)
        for (int a = 0; a < 16; a++) {
            int px = (int)floor(*x + r * cos(a * M_PI / 8) + 0.5), py = (int)floor(*y + r * sin(a * M_PI / 8) + 0.5);
            if (walkable_now(sim, px, py)) { *x = px; *y = py; return 1; }
        }
    /* farther out (a lake wider than the rings): the centre of the nearest walkable tile of the whole map. [?] Neither search
     * looks at walls in between or at the storm */
    void *m = PTR(sim, 0x68); if (!m) return 0;
    int W = I32(m, 0xc4), Hh = I32(m, 0xc8), bx = 0, by = 0; long best = -1;
    if (W < 1 || Hh < 1 || W * Hh > 16384) return 0;
    for (int ty = 0; ty < Hh; ty++)
        for (int tx = 0; tx < W; tx++) {
            int cx = tx * 300 + 150, cy = ty * 300 + 150; if (!walkable_now(sim, cx, cy)) continue;
            long d = (long)(cx - *x) * (cx - *x) + (long)(cy - *y) * (cy - *y);
            if (best < 0 || d < best) { best = d; bx = cx; by = cy; }
        }
    if (best < 0) return 0;
    *x = bx; *y = by; return 1;
}
int superfix_land(void *sim, int *x, int *y) { return split_land(sim, x, y); }   /* env.c: a respawn spot on water */
static int on_map_blocked(void *sim, int x, int y) {   /* inside the map on a tile that blocks a walker (not the parking spot) */
    void *m = sim ? PTR(sim, 0x68) : NULL; if (!m) return 0;
    int tx = (int)floor(x / 300.0), ty = (int)floor(y / 300.0);
    return tx >= 0 && ty >= 0 && tx < I32(m, 0xc4) && ty < I32(m, 0xc8) && !walkable_now(sim, x, y);
}
typedef int (*wow_t)(void *); static wow_t o_wow; static long g_split_wow, g_split_land;
/* a head with living legs: he walks over water (my_wow; env.c also raycasts his joystick target past water with it) */
int superfix_split_water(uint8_t *c) {
    return o_wow && mode() && c && VTOF(c) == VT_CHAR && up_of(c) == 13 && hero_kind(c) && split_partner(c);
}
static int my_wow(void *c) {   /* canWalkOverWater 0xb51200: the data's CanWalkOverWater, or a split head (isSplit's meaning) */
    if (o_wow(c) & 1) return 1;
    if (!superfix_split_water(c)) return 0;
    g_split_wow++; return 1;
}
typedef struct { uint8_t *ch; int id, amount, until; } SplitSpd;
static SplitSpd g_ss[16]; static int g_nss;
static void my_speed_buff(uint8_t *ch, int amount, int ticks, int flag) {   /* 0xb5901c(char, speed, ticks, flag): a stub */
    (void)flag;
    if (!mode() || !ch || __builtin_return_address(0) != (void *)B(0xb9c4fc) || amount <= 0 || ticks <= 0) return;   /* R-T only */
    int k; for (k = 0; k < g_nss && g_ss[k].ch != ch; k++) {}
    if (k == g_nss) { if (g_nss >= 16) k = (int)(g_split_spd % 16); else g_nss++; }
    g_ss[k] = (SplitSpd){ch, I32(ch, 8), amount, now_of(ch) + ticks}; g_split_spd++;
}
int superfix_split_speed(uint8_t *ch) {
    if (!g_nss || !ch || !mode()) return 0;
    for (int k = 0; k < g_nss; k++) if (g_ss[k].ch == ch) return g_ss[k].id == I32(ch, 8) && now_of(ch) < g_ss[k].until ? g_ss[k].amount : 0;
    return 0;
}
static void (*o_split)(uint8_t *);
static void my_split(uint8_t *ch) {   /* 0xb5c7b0(char) */
    uint8_t *legs = mode() && ch && hero_kind(ch) ? split_partner(ch) : NULL;
    if (!legs) { o_split(ch); return; }
    int x = I32(legs, 0x38), y = I32(legs, 0x3c), hp0 = I32(ch, 0x3c4), mhp = I32(ch, 0x3c8);
    int heal = card_value(((getp_t)B(0xb6a384))(legs), 3, 3); if (heal <= 0) heal = SPLIT_HEAL;
    heal *= P11_SCALE;
    retire(legs);
    if (split_land(sim_of(ch), &x, &y)) g_split_land++;   /* the legs' spot is blocked for him (whole again: no water) */
    stop_mover(ch);
    ((void (*)(void *, int, int, int))B(0xb6a61c))(ch, x, y, 0);
    if (hp0 > 0) I32(ch, 0x3c4) = hp0 + heal < mhp ? hp0 + heal : mhp;
    g_split_rejoin++;
    if (g_superfix_dbg) LOG("[superfix] split: rejoin char %d at legs %d (%d,%d -> %d,%d), hp %d -> %d / %d\n", I32(ch, 8), I32(legs, 8),
                            I32(legs, 0x38), I32(legs, 0x3c), x, y, hp0, I32(ch, 0x3c4), mhp);
}
static long g_split_comp;
static int g_was_split[16], g_nws, g_ws_tick; static void *g_ws_sim;   /* ids of heads that had living legs at their last
                                                                        * tick; the battle (sim, last tick) they belong to */
static void ws_drop(int id) { for (int k = 0; k < g_nws; k++) if (g_was_split[k] == id) { g_was_split[k] = g_was_split[--g_nws]; return; } }
static void head_land(uint8_t *ch) {   /* the legs went: a head left standing on water goes to the nearest land */
    int id = I32(ch, 8), k, split = split_partner(ch) != NULL; void *sim0 = sim_of(ch); int now = sim0 ? I32(sim0, 0x10) : 0;
    if (sim0 != g_ws_sim || now < g_ws_tick) g_nws = 0;   /* a new battle */
    g_ws_sim = sim0; g_ws_tick = now;
    for (k = 0; k < g_nws && g_was_split[k] != id; k++) {}
    if (split) { if (k == g_nws && g_nws < 16) g_was_split[g_nws++] = id; return; }
    if (k == g_nws) return;
    g_was_split[k] = g_was_split[--g_nws];
    void *sim = sim_of(ch); int x = I32(ch, 0x38), y = I32(ch, 0x3c);
    if (!on_map_blocked(sim, x, y) || !split_land(sim, &x, &y)) return;
    stop_mover(ch); ((void (*)(void *, int, int, int))B(0xb6a61c))(ch, x, y, 0); stop_mover(ch); g_split_land++;
    if (g_superfix_dbg) LOG("[superfix] split: head %d whole on a blocked tile, put on land at %d,%d\n", id, x, y);
}
static void split_tick(uint8_t *ch) {
    if (I32(ch, 0x3c4) <= 0) { if (g_nws) ws_drop(I32(ch, 8)); return; }   /* a dead head leaves the tracking */
    if (up_of(ch) != 13) return;
    if (hero_kind(ch)) {   /* the head: run his Brawler_Splitter component's tick (vtable +0x40 = 0xb9c42c), which libg never
                            * calls (as Draco's MountUp tick, superfix_status.c): the weapon swap, the speed, the hypercharged
                            * circling projectiles and their removal */
        int nc = I32(ch, 0xa6c); void **c = PTR(ch, 0xa60);
        for (int i = 0; c && i < nc && i < 64; i++)
            if (c[i] && PTR(c[i], 8) == ch && (*(void ***)c[i])[0x40 / 8] == (void *)B(0xb9c42c)) { ((void (*)(void *))B(0xb9c42c))(c[i]); g_split_comp++; }
        head_land(ch);
        return;
    }
    if (split_partner(ch)) return;   /* legs whose head is gone go too */
    retire(ch); g_split_orphan++;
    if (g_superfix_dbg) LOG("[superfix] split: legs %d retired (no head)\n", I32(ch, 8));
}

/* ======================= Building pets (Mr. P's porters) */
/* A character whose CharacterData has a Pet (+0x250) and PetAutoSpawnDelay (+0x280, seconds) spawns that pet by itself:
 * Mr. P's home base SpawnerDudeTurret (Pet SpawnerPet, 4 s) and the hypercharged one OverchargedSpawnerDudeTurret
 * (OverchargedSpawnerPet, ExtraMinions +0x27c = 1: "he can have two active Super Porters at the same time",
 * TID_SPAWNER_DUDE_OVERCHARGE_DESC). The client only (de)serialises the base's spawn timer (char +0x7e0, 0xb376bc / 0xb2f05c);
 * the spawning is server code. Here, from the character tick: while the base's owner has fewer than 1 + ExtraMinions living
 * pets of that data, a pet comes out every PetAutoSpawnDelay seconds ([?] guess: the first one that long after the base
 * lands, the next that long after the count dropped), through the summon 0xb56e00 with the arguments R-T's split
 * (0xb5c7b0, the same "spawn my Pet at my feet" call) passes, but no MaxSpawns count (w5 0: the count is the one above). */
#define BPET_MAX 16
static struct { uint8_t *ch; int id, due; } g_bpet[BPET_MAX];
static long g_bpet_spawn;
typedef void *(*summon_t)(void *, int, int, int, int, int, int, int, void *, uint64_t, uint64_t, uint64_t, uint64_t,
                          uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                          uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static void bpet_tick(uint8_t *ch) {
    uint8_t *cd = ((getp_t)B(0xb6a384))(ch), *pd = cd ? PTR(cd, 0x250) : NULL;
    int delay = cd ? I32(cd, 0x280) : 0, own = I32(ch, 0x80);
    if (!pd || delay < 1 || delay > 60 || own < 0 || I32(ch, 0x3c4) <= 0) return;
    int k = 0, fr = -1, now = now_of(ch);
    for (; k < BPET_MAX && !(g_bpet[k].ch == ch && g_bpet[k].id == I32(ch, 8)); k++)
        if (fr < 0 && (!g_bpet[k].ch || now - g_bpet[k].due > 2000)) fr = k;   /* free, or stale */
    if (k == BPET_MAX) { if (fr < 0) return; k = fr; g_bpet[k].ch = ch; g_bpet[k].id = I32(ch, 8); g_bpet[k].due = 0; }
    int n, have = 0, cap = 1 + (I32(cd, 0x27c) > 0 && I32(cd, 0x27c) < 10 ? I32(cd, 0x27c) : 0); void **v = objs(sim_of(ch), &n);
    for (int i = 0; v && i < n; i++) {
        uint8_t *c = v[i];
        if (c && VTOF(c) == VT_CHAR && I32(c, 0x3c4) > 0 && I32(c, 0x80) == own && ((getp_t)B(0xb6a384))(c) == pd) have++;
    }
    if (have >= cap) { g_bpet[k].due = 0; return; }
    if (!g_bpet[k].due) { g_bpet[k].due = now + delay * 20; return; }   /* seconds x 20 ticks */
    if (now < g_bpet[k].due) return;
    g_bpet[k].due = 0;
    uint64_t z = 0;
    void *p = ((summon_t)B(0xb56e00))(pd, ((geti_t)B(0xb6a628))(ch), ((geti_t)B(0xb6a630))(ch), 0, 1, 0, I32(ch, 1148), I32(ch, 2724),
                                      sim_of(ch), (uint64_t)((geti_t)B(0xb6a754))(ch), (uint64_t)((geti_t)B(0xb6a818))(ch),
                                      (uint64_t)((geti_t)B(0xb6a884))(ch), (uint64_t)((geti_t)B(0xb6a5d4))(ch), z, z, z,
                                      (uint64_t)U8(ch, 2801), z, 1, z, z, z, z, z, 1, z, (uint64_t)-1, z, z, z, z);
    if (p) g_bpet_spawn++;
    if (g_superfix_dbg || g_bpet_spawn <= 4) LOG("[superfix] building pet: ch %d (data %d) spawned %d (data %d, %d of %d) at tick %d\n",
                                                 I32(ch, 8), I32(cd, 0x20), p ? I32(p, 8) : -1, I32(pd, 0x20), have + !!p, cap, now);
}

/* ======================= Sirius's shadows (Shadowdemon) */
/* His Brawler_Shadowdemon component (type 13, ctor 0xb99b7c, vtable 0x120a710) is client code that listens on three of
 * his character's event lists. Two of them libg fires itself: his skill use (char +0x190, 0xb9aebc: for an ulti it
 * summons every stored shadow around him through 0xb9a7fc -> the summon 0xb56e00, with the traits ShadowdemonMinionDamage
 * / Health, or their Overcharged ones while he is hypercharged: TID_SHADOWDEMON_OVERCHARGE_DESC) and his death (+0x90,
 * 0xb9b2e4: the shadows go). The third, his hits (char +0x280, 0xb9aad8(component, event): event +0 the character hit, +32
 * the projectile or area; every Values[0] = 4th hit of his main attack, 0xc70b70, stores that brawler's shadow, at most
 * Values[1] = 3: TID_SHADOWDEMON_WEAPON_DESC), only the server fires, so nothing was ever stored and his super summoned
 * nobody. Here: the damage root (env.c my_root) hands each hit he deals to superfix_hit_event, which calls that handler.
 * The component tick 0xb9a290 (nothing stored or alive: super disabled) is not run. */
static uint8_t *shadow_comp(uint8_t *ch) {
    int nc = I32(ch, 0xa6c); void **c = PTR(ch, 0xa60);
    for (int i = 0; c && i < nc && i < 64; i++)
        if (c[i] && I32(c[i], 0x10) == 13 && PTR(c[i], 8) == ch && (*(void ***)c[i])[0x40 / 8] == (void *)B(0xb9a290)) return c[i];
    return NULL;
}
static long g_shadow_hits;
void superfix_hit_event(uint8_t *victim, uint8_t *attacker, void *src) {
    if (!mode() || !victim || !attacker || !src || VTOF(attacker) != VT_CHAR || VTOF(victim) != VT_CHAR) return;
    uint8_t *comp = shadow_comp(attacker); if (!comp) return;
    void *ev[8] = {0}; ev[0] = victim; ev[4] = src;   /* +0 the character hit, +32 the projectile / area */
    int n0 = I32(comp, 68);
    ((void (*)(void *, void *))B(0xb9aad8))(comp, ev);
    if (g_superfix_dbg || g_shadow_hits++ < 8) LOG("[superfix] shadowdemon hit: %d on %d, hit count %d, shadows stored %d -> %d\n",
                                                   I32(attacker, 8), I32(victim, 8), I32(comp, 88), n0, I32(comp, 68));
}

/* ======================= per character tick (enter 0xb3ae74) */
static void on_char_tick(uint64_t *ctx) {
    uint8_t *ch = (uint8_t *)ctx[0];
    if (!ch || !mode()) return;
    if (VTOF(ch) == VT_CHAR && I32(ch, 0x80) >= 0) bpet_tick(ch);
    if (g_split_on && VTOF(ch) == VT_CHAR && I32(ch, 0x80) >= 0) split_tick(ch);
    if (VTOF(ch) == VT_CHAR) portal_tick(ch);
    for (int i = 0; i < g_ngr; i++) if (g_gr[i].ch == ch && !grapple_tick(&g_gr[i])) g_gr[i--] = g_gr[--g_ngr];
    if (VTOF(ch) == VT_CHAR) kit_watch(ch);
    for (int i = 0; i < g_nkit; i++) if (g_kit[i].ch == ch && !kit_tick(&g_kit[i])) g_kit[i--] = g_kit[--g_nkit];
    if (!g_nfj && !g_nww) return;
    for (int i = 0; i < g_nfj; i++) if (g_fj[i].ch == ch) {
        if (I32(ch, 8) != g_fj[i].id) { g_fj[i--] = g_fj[--g_nfj]; continue; }   /* object reused */
        flyjump_tick(&g_fj[i]);
        if (g_fj[i].landed) g_fj[i--] = g_fj[--g_nfj];
    }
    for (int i = 0; i < g_nww; i++) if (g_ww[i].ch == ch)
        if (I32(ch, 8) != g_ww[i].id || !ww_tick(&g_ww[i])) g_ww[i--] = g_ww[--g_nww];
}

void superfix_moves_install(void) {
    int n = 0;
    if (*(uint32_t *)B(0xb3ae74) != 0xa9ba7bfd) { LOG("[superfix] moves: 0xb3ae74 is not the character tick: left out\n"); return; }   /* stp x29, x30, [sp, #-96]! */
    hook_enter(g_libg, 0xb3ae74, on_char_tick);
    if (*(uint32_t *)B(0xb55598) == RET_INSN && *(uint32_t *)B(0xb7cf00) == 0x97ff61a6 &&   /* bl 0xb55598 */
        *(uint32_t *)B(0xb28d08) == 0x9400009f) {                                            /* bl 0xb28f84 */
        hook_enter(g_libg, 0xb55598, flyjump_start); hook_bl(g_libg, 0xb28d08, (void *)on_area_expire); n |= 1;
    } else LOG("[superfix] moves: FlyJump sites differ: left out\n");
    if (*(uint32_t *)B(0xb5a704) == RET_INSN && *(uint32_t *)B(0xb5a708) == RET_INSN) { hook_enter(g_libg, 0xb5a704, ww_start); n |= 2; }
    else LOG("[superfix] moves: 0xb5a704 is not the Ww stub: left out\n");
    if (*(uint32_t *)B(0xb4ffe0) == RET_INSN) { hook_enter(g_libg, 0xb4ffe0, blink_start); n |= 4; }
    else LOG("[superfix] moves: 0xb4ffe0 is not the teleport stub: left out\n");
    if (*(uint32_t *)B(0xb7d010) == 0x97ff4bf7) { hook_bl(g_libg, 0xb7d010, (void *)change_site); n |= 8; }   /* bl 0xb4ffec */
    else LOG("[superfix] moves: 0xb7d010 is not the ChangeCharacter call: left out\n");
    if (*(uint32_t *)B(0xb392d4) == 0xa9be7bfd && *(uint32_t *)B(0xb3930c) == 0xaa1f03e0 &&   /* stp x29, x30, [sp, #-32]!; ...; mov x0, xzr */
        *(uint32_t *)B(0xb5901c) == RET_INSN && *(uint32_t *)B(0xb5c7b0) == 0xd10483ff && *(uint32_t *)B(0xb9c4f8) == 0x97fef2c9) {   /* sub sp, sp, #0x120; bl 0xb5901c */
        hook_replace(g_libg, 0xb392d4, (void *)split_partner); hook_replace(g_libg, 0xb5901c, (void *)my_speed_buff);
        o_split = hook_replace(g_libg, 0xb5c7b0, (void *)my_split); g_split_on = 1; n |= 16;
        if (*(uint32_t *)B(0xb51200) == 0xa9bd7bfd && *(uint32_t *)B(0xb51224) == 0x94002563) {   /* stp x29, x30, [sp, #-48]!; bl 0xb5a7b0 */
            o_wow = (wow_t)hook_replace(g_libg, 0xb51200, (void *)my_wow); n |= 32;
        } else LOG("[superfix] moves: 0xb51200 is not canWalkOverWater: R-T's head keeps off water\n");
    } else LOG("[superfix] moves: R-T's split sites differ: left out\n");
    if (*(uint32_t *)B(0xb5c180) == 0xa9be7bfd && *(uint32_t *)B(0xb74a68) == 0x97ff9dc6) { hook_enter(g_libg, 0xb5c180, grapple_hit); n |= 64; }   /* stp x29, x30, [sp, #-32]!; bl 0xb5c180 */
    else LOG("[superfix] moves: 0xb5c180 is not the grapple target setter: Buzz pulls to walls only\n");
    LOG("[superfix] moves installed:%s%s%s%s%s%s%s cross-slash, portals, grapple%s\n", n & 1 ? " flyjump" : "", n & 2 ? " ww" : "", n & 4 ? " blink" : "", " change",
        n & 8 ? " change-area" : "", n & 16 ? " split" : "", n & 32 ? " split-water" : "", n & 64 ? " (character hits)" : "");
}
void superfix_moves_status(void) {
    LOG("[superfix] moves: flyjump %ld starts, %ld landings (%ld fallback); ww %ld starts, %ld hits; blink %ld (%ld back), %ld hits; "
        "change character %ld (%ld left to battle_fix), with area %ld (%ld hits); cross slash %ld (%ld hits); split: rejoins %ld, "
        "component ticks %ld, speed ticks %ld, legs retired without a head %ld, water walks %ld, put on land %ld; portals: %ld links, "
        "%ld teleports (%ld shields); grapple: %ld character / %ld wall pulls, %ld landings (%ld stuns), %ld supers given back; "
        "kit: %ld jumps, %ld on teammates (%ld heals), %ld on enemies (%ld stuns)\n", g_fj_start, g_fj_land,
        g_fj_fallback, g_ww_start, g_ww_hits, g_blink, g_blink_back, g_blink_hits, g_change, g_change_skip, g_change_area, g_change_hits,
        g_slash_n, g_slash_hits, g_split_rejoin, g_split_comp, g_split_spd, g_split_orphan, g_split_wow, g_split_land, g_portal_links, g_portal_tp,
        g_portal_shields, g_gr_char, g_gr_wall, g_gr_land, g_gr_stun, g_gr_reload, g_kit_jumps,
        g_kit_ally, g_kit_heal, g_kit_enemy, g_kit_stun);
}
