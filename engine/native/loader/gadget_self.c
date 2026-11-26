/* gadget_self.c (bsrl-sim issue #46): the gadgets that act on the brawler itself: statuses, shields, a sleep, a last stand,
 * bush vision. gadget.c owns the per-player bookkeeping (uses, cooldown, readiness) and calls in here through its SELF
 * entries (gself_kind / gself_fire / gself_ready); the effects are RE-IMPLEMENTED, the game's server code for them is not
 * in this client build (the accessory activation 0xb27c58 is a bare ret).
 *
 * Statuses go into superfix_status.c's store through libg's own add wrapper 0xb35dd0(ch, data, player, team, ch, ch, 0, 0,
 * -1, -1, 0) (the arguments of the area status path), so the store's aggregates apply them: ShieldPercent +0xf4 (char
 * +0x954, the damage root's shield), Invisibility +0x12c (char +0x97c, the encoder's reveal distance), LosePlayerControl
 * +0x131 (libg's "cannot act" 0xb38b54), speed (env.c's mover), DecreaseReloadTimePercent +0x124, and
 * UltiChargeBoostPercent +0xc4 (superfix_status_charge_pct, env.c my_charge). A row the card names is used as it is; a
 * card without a status row gets a synthetic StatusEffectData (one static 0x200-byte block per player: +0x20 the card id
 * for the store's log, +0x98 duration, +0xad Refreshable, and only the fields below). Nothing in libg sees these blocks (the
 * add is the store's and returns NULL). Status rows are removed through the store's remove 0xba3264(ch+0x890, data, -2).
 *
 * Kinds (SK_*), by accessories.csv Type (enum of the parser 0xb2731c):
 *   ROW    empty Type, no AreaEffect / Skill, StatusEffectSelf (+0x68): Jacky's speed boost (published STATUS).
 *   SHIELD empty Type, no AreaEffect / Skill, ShieldPercent / ShieldTicks (getters 0xa93368 / 0xa93378): Hank (40 % for 60
 *          ticks), Lou (100 % for 20 ticks plus StopMovement 0xa932e8 -> LosePlayerControl): synthetic (published SHIELD).
 *   SPEED  movement_speed 37 (Bonnie's Sugar Rush): StatusEffectSelf plus a synthetic reload of CustomValue1 % faster
 *          ("movement and reload speed are increased by 30 %": r = 30 -> DecreaseReloadTimePercent 100 r / (100 + r) = 23)
 *          for ActiveTicks. Only in the brawler's starting form (MissingTargetText REQUIRES_CANNON [?]).
 *   DIVE   dive 46 (Willow): ShieldPercent 100 and LosePlayerControl for ActiveTicks [?] an approximation of the card's
 *          "untargetable but unable to take any action": she takes no damage, but projectiles still stop on her and enemies
 *          still see her (the card makes her untargetable, not invisible).
 *   VOODOO voodoo_self_buff 60 (Juju): by the tile under her (env.c env_ground): water -> VoodooGadgetSpeedUp, bush ->
 *          synthetic Invisibility 1 for ActiveTicks [? level], else -> VoodooGadgetShield. Both rows are looked up by name
 *          (0xad3378, the StatusEffect table): no libg code or CSV names them, the server does.
 *   BOX    invisible 49 (Kit's cardboard box): synthetic Invisibility 1 for ActiveTicks [? level]. The faster super charge
 *          while standing still (CustomValue1) is not done: partial.
 *   ALLY   give_status_effect 63 (Surge x2, Trunk): the StatusEffectAlly row (+0x58) on the brawler [? self only].
 *          CancelOnDamage (+0xa4) is applied only to these gadget statuses (not to every row that has it): the first damage
 *          that takes HP ends it (gself_root_post); Surge's shield row then gives COD_AMMO ammo. ReceiveDamageInversion
 *          (BooleanAttributes +0x14b, Trunk): the first damage is healed instead of taken and ends the status
 *          (gadget_root_pre).
 *   CHARGE give_buff_to_self 54 with CustomValue1 17 (Moe): synthetic UltiChargeBoostPercent CustomValue2 (50) for
 *          ActiveTicks; not in his drill form (MissingTargetText CANT_BE_DRILL: starting form only).
 *   STAND  give_buff_to_self 54 with CustomValue1 21 (Draco's Last Stand): for ActiveTicks a hit cannot take him under 1 HP
 *          (gadget_root_pre clamps the damage before libg's root and the knockout code).
 *   SLEEP  heal 8 SubType 1 (Sandy's Sleep Stimulator; published STATUS: the heal comes after the sleep): LosePlayerControl
 *          for ActivationDelay ticks, then full HP through libg's heal 0xb41554; damage during the sleep wakes her with no
 *          heal (Interruptable).
 *   VISION vision 12 (Tara SubType 0: her team sees every enemy in a bush; Buzz SubType 1: enemies in a bush within
 *          BUZZ_VISION_R of him) for ActiveTicks: env.c's bush hiding (emulate_client_flags) asks gadget_vision. The
 *          observation's shape is unchanged.
 * Every status kind needs superfix's status store (superfix_status_live): without it they classify as not usable.
 * NB_GAD_SELF=0 turns them all off (kind NONE). NB_GAD_DBG=1 logs the fires and their effects. */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define I32(p, o) (*(volatile int32_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void *volatile *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(volatile uint8_t *)((uint8_t *)(p) + (o)))
#define B(off) ((uint8_t *)g_libg->base + (off))
#define VTOF(o) ((int)((uint8_t *)PTR(o, 0) - g_libg->base))
enum { VT_CHAR = 0x1209020 };
extern Module *g_libg;
void *env_obj_by_id(void *sim, int id);         /* env.c */
int env_ground(void *sim, int x, int y);        /* env.c: 1 bush, 2 water, 0 other ground under world (x, y) */
int superfix_status_live(void) __attribute__((weak));   /* superfix_status.c: the store is installed and on */

enum { SK_NONE, SK_ROW, SK_SHIELD, SK_SPEED, SK_DIVE, SK_VOODOO, SK_BOX, SK_ALLY, SK_CHARGE, SK_STAND, SK_SLEEP, SK_VISION, SK_N };
static const char *const SK_NAME[SK_N] = {"none", "row", "shield", "speed", "dive", "voodoo", "box", "ally", "charge", "stand", "sleep", "vision"};
enum { T_HEAL = 8, T_VISION = 12, T_SPEED = 37, T_DIVE = 46, T_INVISIBLE = 49, T_BUFF = 54, T_VOODOO = 60, T_GIVE_STATUS = 63 };
enum { AD_SE_ALLY = 0x58, AD_SE_SELF = 0x68, AD_AREA = 0x70, AD_SKILL = 0x80 };                  /* AccessoryData (createReferences) */
#define AD_SUBTYPE 0xa93258
#define AD_ACTIVE_TICKS 0xa932c8
#define AD_ACT_DELAY 0xa932b8
#define AD_CV1 0xa933d0
#define AD_CV2 0xa933e0
#define AD_STOP_MOVE 0xa932e8   /* StopMovement (bool) */
#define AD_SHIELD_PCT 0xa93368  /* ShieldPercent */
#define AD_SHIELD_TICKS 0xa93378
enum { SE_ID = 0x20, SE_DUR = 0x98, SE_COD = 0xa4, SE_REFRESH = 0xad, SE_CHARGE = 0xc4, SE_SHIELD = 0xf4, SE_RELOAD = 0x124,
       SE_INVIS = 0x12c, SE_LOSECTL = 0x131, SE_INVERT = 0x14b };   /* StatusEffectData (loader 0xba3814) */
#define BUFF_CHARGE 17          /* give_buff_to_self CustomValue1: the buff the row names (Moe 17, Draco 21; Clancy 22 and
                                 * Kenji 26 are not done) */
#define BUFF_STAND 21
#define COD_AMMO 2              /* character_actions.csv PowerLevelerGadgetShieldGiveAmmo: GiveAmmoSource, Value 2 [?] 2 bars */
#define BUZZ_VISION_R 1800      /* RopeDudeSuperChargeArea Radius (his super charging area; the Large row's 2400 is not used) */

static int g_on = -1;
static int dbg(void) { static int d = -1; if (d < 0) { const char *e = getenv("NB_GAD_DBG"); d = e && atoi(e) > 0; } return d; }
static int ad_get(void *ad, uint64_t getter) { return ((int (*)(void *))B(getter))(ad); }
static int now_tick(void *obj) { uint8_t *sim = ((void *(*)(void *))B(0xb6a378))(obj); return sim ? I32(sim, 0x10) : -1; }

typedef struct {
    int sk, start_data;                 /* kind; the brawler's CharacterData id at its first tick (form gate) */
    int ch_id, until;                   /* the timed effect's brawler and end tick (0 = none running) */
    void *data;                         /* ALLY: the status row put on (CancelOnDamage / inversion), SLEEP: the synthetic one */
    int cod, invert, sub;               /* ALLY flags; VISION SubType */
} Self;
static Self g_self[NBE_MAXP];
static uint8_t g_syn[NBE_MAXP][0x200] __attribute__((aligned(16)));
static long g_fired[SK_N], g_clamps, g_inverts, g_cancels, g_ammo, g_sleeps, g_woken, g_vision_hits, g_named_miss;

static void *status_by_name(const char *name) {   /* offline.c char_data's pattern with the StatusEffect lookup 0xad3378 */
    uint8_t *s = ((void *(*)(unsigned long))B(0x11a4d90))(16); char *c = strdup(name);
    ((void (*)(void *, const char *))B(0xe96e10))(s, c);
    void *d = ((void *(*)(void *, void *))B(0xad3378))(s, NULL);
    ((void (*)(void *))B(0xe96d00))(s); free(c);
    LOG("[gadget] self: status row %s -> %p (id %d)\n", name, d, d ? I32(d, SE_ID) : -1);
    return d;
}
static void *voodoo_row(int water) {
    static void *speed, *shield; static int done;
    if (!done) { speed = status_by_name("VoodooGadgetSpeedUp"); shield = status_by_name("VoodooGadgetShield"); done = 1; }
    return water ? speed : shield;
}
static uint8_t *syn(int pid, int card, int dur) {
    uint8_t *d = g_syn[pid]; memset(d, 0, sizeof g_syn[pid]);
    I32(d, SE_ID) = card; I32(d, SE_DUR) = dur > 0 ? dur : 1; U8(d, SE_REFRESH) = 1;
    return d;
}
static void st_apply(uint8_t *ch, void *data, int pid) {
    int team = ((int (*)(void *))B(0xb6a820))(ch);
    ((void (*)(void *, void *, int, int, void *, void *, int, int, int, int, int))B(0xb35dd0))(ch, data, pid, team, ch, ch, 0, 0, -1, -1, 0);
    if (dbg()) LOG("[gadget] self: player %d status %d on ch %d (%d ticks, shield %d invis %d lose %d charge %d reload %d)\n", pid,
                   I32(data, SE_ID), I32(ch, 8), I32(data, SE_DUR), I32(data, SE_SHIELD), I32(data, SE_INVIS), U8(data, SE_LOSECTL),
                   I32(data, SE_CHARGE), I32(data, SE_RELOAD));
}
static void st_end(uint8_t *ch, void *data) { ((void (*)(void *, void *, void *))B(0xba3264))(ch + 0x890, data, (void *)(intptr_t)-2); }

/* accessory -> SK_* (0 = not one of these) */
int gself_kind(void *ad, int type) {
    if (g_on < 0) { const char *e = getenv("NB_GAD_SELF"); g_on = !(e && !atoi(e)); if (!g_on) LOG("[gadget] self gadgets off (NB_GAD_SELF=0)\n"); }
    if (!g_on || !ad) return SK_NONE;
    int vision = type == T_VISION && ad_get(ad, AD_ACTIVE_TICKS) > 0;   /* no status: needs no store */
    if (vision) return SK_VISION;
    if (!superfix_status_live || !superfix_status_live()) return SK_NONE;
    int sub = ad_get(ad, AD_SUBTYPE), at = ad_get(ad, AD_ACTIVE_TICKS);
    switch (type) {
    case 0:
        if (PTR(ad, AD_AREA) || PTR(ad, AD_SKILL)) return SK_NONE;
        if (PTR(ad, AD_SE_SELF)) return SK_ROW;
        return ad_get(ad, AD_SHIELD_PCT) > 0 && ad_get(ad, AD_SHIELD_TICKS) > 0 ? SK_SHIELD : SK_NONE;
    case T_SPEED: return PTR(ad, AD_SE_SELF) ? SK_SPEED : SK_NONE;
    case T_DIVE: return at > 0 ? SK_DIVE : SK_NONE;
    case T_VOODOO: return at > 0 ? SK_VOODOO : SK_NONE;
    case T_INVISIBLE: return at > 0 ? SK_BOX : SK_NONE;
    case T_GIVE_STATUS: return PTR(ad, AD_SE_ALLY) ? SK_ALLY : SK_NONE;
    case T_BUFF: { int b = ad_get(ad, AD_CV1);
        return at <= 0 ? SK_NONE : b == BUFF_CHARGE && ad_get(ad, AD_CV2) > 0 ? SK_CHARGE : b == BUFF_STAND ? SK_STAND : SK_NONE; }
    case T_HEAL: return sub == 1 && ad_get(ad, AD_ACT_DELAY) > 0 ? SK_SLEEP : SK_NONE;
    }
    return SK_NONE;
}
int gself_published(int sk) { return sk == SK_SHIELD ? NBE_GAD_SHIELD : NBE_GAD_STATUS; }

static int cur_data(uint8_t *ch) { void *cd = ((void *(*)(void *))B(0xb6a384))(ch); return cd ? I32(cd, SE_ID) : 0; }
/* readiness: alive, not already running (the rows' TargetAlreadyActiveText), the form gate */
int gself_ready(void *sim, int pid, uint8_t *ch, void *ad, int sk) {
    (void)sim; (void)ad;
    if (pid < 0 || pid >= NBE_MAXP || !ch || I32(ch, 0x3c4) <= 0) return 0;
    Self *s = &g_self[pid]; int t = now_tick(ch);
    if (!s->start_data) s->start_data = cur_data(ch);
    if ((sk == SK_SPEED || sk == SK_CHARGE) && cur_data(ch) != s->start_data) return 0;
    if ((sk == SK_STAND || sk == SK_SLEEP || sk == SK_VISION) && s->until > t) return 0;
    return 1;
}

int gself_fire(void *sim, int pid, uint8_t *ch, void *ad, int card, int sk, int tick) {
    if (!gself_ready(sim, pid, ch, ad, sk)) return 0;
    Self *s = &g_self[pid]; int at = ad_get(ad, AD_ACTIVE_TICKS); uint8_t *d;
    s->sk = sk;
    switch (sk) {
    case SK_ROW: st_apply(ch, PTR(ad, AD_SE_SELF), pid); break;
    case SK_SHIELD:
        d = syn(pid, card, ad_get(ad, AD_SHIELD_TICKS)); I32(d, SE_SHIELD) = ad_get(ad, AD_SHIELD_PCT);
        U8(d, SE_LOSECTL) = ad_get(ad, AD_STOP_MOVE) != 0; st_apply(ch, d, pid); break;
    case SK_SPEED: {
        int r = ad_get(ad, AD_CV1);
        st_apply(ch, PTR(ad, AD_SE_SELF), pid);
        if (r > 0) { d = syn(pid, card, at); I32(d, SE_RELOAD) = 100 * r / (100 + r); st_apply(ch, d, pid); }
        break; }
    case SK_DIVE:
        d = syn(pid, card, at); I32(d, SE_SHIELD) = 100; U8(d, SE_LOSECTL) = 1; st_apply(ch, d, pid); break;
    case SK_BOX: d = syn(pid, card, at); I32(d, SE_INVIS) = 1; st_apply(ch, d, pid); break;
    case SK_VOODOO: {
        int g = env_ground(sim, I32(ch, 0x38), I32(ch, 0x3c));
        if (g == 1) { d = syn(pid, card, at); I32(d, SE_INVIS) = 1; st_apply(ch, d, pid); }
        else { void *row = voodoo_row(g == 2); if (!row) { g_named_miss++; return 0; } st_apply(ch, row, pid); }
        if (dbg()) LOG("[gadget] self: player %d Juju on %s\n", pid, g == 1 ? "a bush" : g == 2 ? "water" : "ground");
        break; }
    case SK_ALLY: {
        void *row = PTR(ad, AD_SE_ALLY);
        st_apply(ch, row, pid);
        s->data = row; s->ch_id = I32(ch, 8); s->until = tick + I32(row, SE_DUR); s->cod = U8(row, SE_COD); s->invert = U8(row, SE_INVERT);
        break; }
    case SK_CHARGE: d = syn(pid, card, at); I32(d, SE_CHARGE) = ad_get(ad, AD_CV2); st_apply(ch, d, pid); break;
    case SK_STAND: s->ch_id = I32(ch, 8); s->until = tick + at; break;
    case SK_SLEEP: {
        int n = ad_get(ad, AD_ACT_DELAY);
        d = syn(pid, card, n); U8(d, SE_LOSECTL) = 1; st_apply(ch, d, pid);
        s->data = d; s->ch_id = I32(ch, 8); s->until = tick + n; g_sleeps++;
        break; }
    case SK_VISION: s->ch_id = I32(ch, 8); s->until = tick + at; s->sub = ad_get(ad, AD_SUBTYPE); break;
    default: return 0;
    }
    g_fired[sk]++;
    if (dbg()) LOG("[gadget] self: player %d card %d %s fired at tick %d\n", pid, card, SK_NAME[sk], tick);
    return 1;
}

/* gadget.c's gadget_tick: Sandy's sleep ends with a full heal */
void gself_tick(void *sim, int tick) {
    for (int i = 0; i < NBE_MAXP; i++) {
        Self *s = &g_self[i];
        if (s->sk != SK_SLEEP || !s->until || tick < s->until) continue;
        uint8_t *ch = env_obj_by_id(sim, s->ch_id); s->until = 0;
        if (!ch || I32(ch, 0x3c4) <= 0) continue;
        int hp = I32(ch, 0x3c4), mx = I32(ch, 0x3c8);
        if (hp < mx) ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(ch, i, mx - hp, 1, NULL, 0, 0, 0, 0, 0);
        if (dbg()) LOG("[gadget] self: player %d woke at tick %d, hp %d -> %d\n", i, tick, hp, I32(ch, 0x3c4));
    }
}

static Self *running(uint8_t *victim, int sk, int t) {
    int id = I32(victim, 8);
    for (int i = 0; i < NBE_MAXP; i++) if (g_self[i].sk == sk && g_self[i].until > t && g_self[i].ch_id == id) return &g_self[i];
    return NULL;
}
/* env.c my_root, before libg's root (after the env's damage model): -> 1 = skip this hit. Trunk's inversion heals the hit
 * and ends; Draco's last stand clamps the damage to hp - 1 */
int gadget_root_pre(uint8_t *victim, uint8_t *attacker, int *dmg, int *a3) {
    (void)attacker;
    if (!victim || VTOF(victim) != VT_CHAR || *dmg <= 0 || I32(victim, 0x3c4) <= 0) return 0;
    int t = now_tick(victim); Self *s;
    if ((s = running(victim, SK_ALLY, t)) && s->invert) {
        int pid = (int)(s - g_self);
        ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(victim, pid, *dmg, 1, NULL, 0, 0, 0, 0, 0);
        st_end(victim, s->data); s->until = 0; g_inverts++;
        if (dbg()) LOG("[gadget] self: player %d inverted %d damage at tick %d\n", pid, *dmg, t);
        return 1;
    }
    if ((s = running(victim, SK_STAND, t))) {
        int hp = I32(victim, 0x3c4);
        if (*dmg >= hp) {
            int nd = hp - 1; g_clamps++;
            if (dbg()) LOG("[gadget] self: player %d last stand: %d damage -> %d at hp %d, tick %d\n", (int)(s - g_self), *dmg, nd, hp, t);
            if (nd <= 0) return 1;
            if (*a3 == *dmg) *a3 = nd;
            *dmg = nd;
        }
    }
    return 0;
}
static int max_ammo(uint8_t *ch, uint8_t **sk0) {   /* gadget.c's: weapon skill instance +0x18, full = 0xb7aea4 x 1000 */
    uint8_t **sk = PTR(ch, 0x458); int n = I32(ch, 0x464);
    *sk0 = sk && n >= 1 && n <= 16 ? sk[0] : NULL; if (!*sk0) return 0;
    int m = ((int (*)(void *, void *))B(0xb7aea4))(*sk0, ch) * 1000;
    return m > 1000 ? m : 1000;
}
/* gadget.c's gadget_root_post, after libg's root: CancelOnDamage of the gadget statuses (Surge's shield gives its ammo),
 * Sandy woken by damage */
void gself_root_post(uint8_t *victim, int removed) {
    if (!victim || removed <= 0) return;
    int t = now_tick(victim); Self *s;
    if ((s = running(victim, SK_ALLY, t)) && s->cod) {
        st_end(victim, s->data); s->until = 0; g_cancels++;
        uint8_t *sk0; int m = max_ammo(victim, &sk0);
        if (sk0 && I32(s->data, SE_SHIELD) > 0) {
            int a = I32(sk0, 0x18) + COD_AMMO * 1000; I32(sk0, 0x18) = a < m ? a : m; g_ammo++;
        }
        if (dbg()) LOG("[gadget] self: player %d status %d cancelled by %d damage at tick %d, ammo %d\n", (int)(s - g_self),
                       I32(s->data, SE_ID), removed, t, sk0 ? I32(sk0, 0x18) : -1);
    }
    if ((s = running(victim, SK_SLEEP, t))) {
        st_end(victim, s->data); s->until = 0; g_woken++;
        if (dbg()) LOG("[gadget] self: player %d woken by %d damage at tick %d (no heal)\n", (int)(s - g_self), removed, t);
    }
}

/* env.c's bush hiding: is an enemy at world (x, y) seen into its bush by player li's team (a Tara or Buzz vision running) */
static void *g_sim; static int g_now;
int gadget_vision(int li, int x, int y) {
    if (!g_sim || li < 0 || li >= NBE_MAXP) return 0;
    int np = I32(g_sim, 0x7c); void **ps = PTR(g_sim, 0x70);
    if (!ps || li >= np || np > 64 || !ps[li]) return 0;
    int team = I32(ps[li], 12);
    for (int i = 0; i < NBE_MAXP && i < np; i++) {
        Self *s = &g_self[i];
        if (s->sk != SK_VISION || s->until <= g_now || !ps[i] || I32(ps[i], 12) != team) continue;
        if (s->sub == 0) { g_vision_hits++; return 1; }
        uint8_t *ch = env_obj_by_id(g_sim, s->ch_id);
        if (!ch || I32(ch, 0x3c4) <= 0) continue;
        long dx = x - I32(ch, 0x38), dy = y - I32(ch, 0x3c);
        if (dx * dx + dy * dy <= (long)BUZZ_VISION_R * BUZZ_VISION_R) { g_vision_hits++; return 1; }
    }
    return 0;
}
void gself_note_tick(void *sim, int tick) { g_sim = sim; g_now = tick; gself_tick(sim, tick); }

/* RESET: the last battle's counters (when any fired), then a clean table */
void gself_clear(void) {
    long n = 0; for (int k = 0; k < SK_N; k++) n += g_fired[k];
    if (n) {
        char b[256]; int o = 0;
        for (int k = 1; k < SK_N; k++) if (g_fired[k]) o += snprintf(b + o, sizeof b - o, " %s %ld", SK_NAME[k], g_fired[k]);
        LOG("[gadget] self:%s; last stand clamps %ld, inversions %ld, cancels %ld (ammo %ld), sleeps %ld (woken %ld), vision hits %ld, "
            "missing rows %ld\n", b, g_clamps, g_inverts, g_cancels, g_ammo, g_sleeps, g_woken, g_vision_hits, g_named_miss);
    }
    memset(g_self, 0, sizeof g_self); memset(g_fired, 0, sizeof g_fired);
    g_clamps = g_inverts = g_cancels = g_ammo = g_sleeps = g_woken = g_vision_hits = 0; g_sim = NULL;
}
