/* nbenv: shared-memory protocol between one nbhost process (the game, one battle) and the Python vector env.
 * One file per instance (Python creates it with the full size, nbhost maps it with --env PATH).
 * All fields are little-endian int32/uint32/float (same layout on AArch64 guest and x86-64 host).
 * Python mirror: work/py/nbpc/proto.py (ctypes). Bump NBE_VERSION on any change.
 *
 * Handshake: Python fills `cmd`, then writes hdr.cmd_seq = n (release). nbhost (game thread, at a step boundary)
 * sees cmd_seq != the last one it served, executes the command, fills `resp` (+ state/pixel blocks), then writes
 * hdr.resp_seq = n. Python waits for resp_seq == n. Exactly one command in flight. */
#pragma once
#include <stdint.h>

#define NBE_MAGIC 0x3145424eu        /* 'NBE1' */
#define NBE_VERSION 5
#define NBE_MAXP 16                  /* player slots in the per-player arrays (Showdown uses 10) */
#define NBE_STATE_CAP (64 * 1024)    /* int32 capacity of the state2 block (the agent's snap2 buffer) */
#define NBE_MAP_CAP 16384            /* tiles */
#define NBE_REC_CAP 4096             /* action records (8 int32 each) per step */
#define NBE_PIX_CAP (2400 * 1080 * 4)  /* bytes; expertbot round: full-resolution capture (was 512 * 256 * 4) */
#define NBE_OBS_VEC 436              /* state2.encode vector length */
#define NBE_OBS_GRID (6 * 25 * 25)

enum { NBE_CMD_NONE = 0, NBE_CMD_STEP = 1, NBE_CMD_RESET = 2, NBE_CMD_QUIT = 3, NBE_CMD_PING = 4, NBE_CMD_SETUP = 5, NBE_CMD_JOYTEST = 6 };
enum { NBE_ST_BOOT = 0, NBE_ST_READY = 1, NBE_ST_RUNNING = 2, NBE_ST_DEAD = 9 };
/* cmd.flags */
#define NBE_F_STATE 1u        /* write the snap2 state2 bytes */
#define NBE_F_PIXELS 2u       /* render this step's frame and read it back (pixel block) */
#define NBE_F_REC 4u          /* controller-call records of this step (demo recorder) */
#define NBE_F_MAP 8u          /* write the map tiles (always written on RESET) */
#define NBE_F_OBS 16u         /* write the encoded observation (state2.encode) for every player in obs_mask */

typedef struct {
    int32_t move_dir;     /* -1 = joystick released (stop if moving), 0..15 = direction k*22.5 deg (x right, y down) */
    int32_t fire;         /* 0 none, 1 attack (attack_angle), 2 super (super_angle + super_dist), 3 gadget (input kind 8, diversity round),
                             4 hypercharge (hypercharge round, hyper.c; no aim) */
    float aim_deg;        /* any degrees, x right / y down */
    float super_dist;     /* (0, 1] -> leap length 2600 * dist */
} NbeAction;

typedef struct {          /* diversity round: NbeCmd.div (RESET) */
    int32_t location;     /* locations.csv 15xxxxxx, a location with the PLAY battle's game mode variation (Solo Showdown);
                             0 = the PLAY battle's location. Its Map gives the tiles, its LocationTheme the look */
    int32_t theme;        /* location_themes.csv id: replaces the location's LocationTheme for this battle; 0 = its own */
    int32_t chr[NBE_MAXP];   /* per player index: characters.csv 16xxxxxx (a Hero); 0 = g_roster ("Sniper") */
    int32_t skin[NBE_MAXP];  /* per player index: skins.csv 29xxxxxx of that character; 0 = the character's default skin */
    int32_t gadget[NBE_MAXP];  /* per player index: cards.csv 23xxxxxx gadget card (MetaType 5) of that character -> its
                                  config +0x10; 0 = none (as before: the offline build gives no cards) */
    int32_t star[NBE_MAXP];    /* per player index: cards.csv 23xxxxxx star power card (MetaType 4) -> config +0x08; 0 = none */
    uint32_t setup_super_mask; /* SETUP (test harness): bit i = fill player i's super charge (player +0x54 = +0x58); bit 16+i = its hypercharge (+0x98 = +0x9c) */
    uint32_t setup_unprotect_mask; /* SETUP (test harness): bit i = clear player i's spawn protection (char +0x4f0 end tick = 0) */
    int32_t reserved[2];
    /* hypercharge round (bsrl-sim issue #4, appended): bit i = put player i's brawler's hypercharge card (cards.csv MetaType 6)
     * in its config (+0x28), so NbeAction.fire 4 can activate it (hyper.c); 0 = none (as before). A brawler without one gets none */
    uint32_t hyper_mask;
    /* gear round (bsrl-sim issue #51, appended): per player index two gear_boosts.csv 62xxxxxx ids -> config +0x18 / +0x20
     * (gear.c); 0 = none. A gear not allowed for the character (libg 0xae2aa4) or a second of one kind is rejected */
    int32_t gear[NBE_MAXP][2];
} NbeDiv;
#define NBE_DIV_MAGIC 0x31564944u   /* 'DIV1' in NbeHdr.reserved[0]: this game host understands NbeCmd.div / NbeResp.div_* */

typedef struct {
    uint32_t type;        /* NBE_CMD_* */
    uint32_t ticks;       /* STEP: ticks in this step (the phone env: 4) */
    uint32_t flags;       /* NBE_F_* */
    int32_t seed;         /* RESET: battle seed (0..2^31-1) */
    uint32_t ctl_mask;    /* STEP: bit i = player index i takes act[i] this step (its native AI does not run) */
    uint32_t hold_mask;   /* bit i = player i holds still (the agent's bot policy 'hold'); persists until changed */
    uint32_t native_mask; /* bit i = player i is driven by the native bot AI (bots: default; the local player: local_ai) */
    uint32_t obs_mask;    /* NBE_F_OBS: players whose encoded observation is written */
    int32_t act_tick;     /* RESET: the first observation is taken after an empty 1-tick step at this tick (200) */
    int32_t gas;          /* RESET: storm damage on (1) / off (0). STEP: 0 = storm clock model; k+1 = latched storm step k for this
                             step (replay of a recorded phone schedule; env.c gas_test_step) */
    int32_t pix_w, pix_h; /* NBE_F_PIXELS: readback size (GPU box-downscale of the 2400x1080 frame) */
    int32_t reserved[4];  /* RESET: [0] = storm latch phase + 1 (0..7; 0 = derived from the seed); [1] = 1: a local player in
                             native_mask is AI-driven during the intro too (the phone from a session's 2nd episode on), else
                             only from the reset observation on (the phone's 1st episode).
                             RESET/STEP [2] = pixel format: 0 = GPU box-downscale to pix_w x pix_h, RGBA bottom-left (raw capture);
                             1 = policy observation: the 300x135 capture -> PIL-exact BOX to pix_w x pix_h, RGB top-left
                             (= adb_driver.preprocess_train without the HUD mask), done in nbgl.
                             any command [3] > 0: bell pipes (--cmd-fd): spin this many us for the next command before
                             blocking (0: --bell-spin-us, default 200) */
    NbeAction act[NBE_MAXP];
    /* SETUP (test harness, the phone's debug_js_tick): applied inside the next tick, before its snapshot */
    uint32_t set_mask;            /* bit i: teleport player i's brawler to (set_x, set_y), stop it, HP = max */
    uint32_t ai_off_mask;         /* bit i: clear the AI flag char+0x469 (the phone test's frozen bots) */
    int32_t set_x[NBE_MAXP], set_y[NBE_MAXP];
    /* pctrain round (2026-10-04): "native + lead" aim. Every command sets it (like hold_mask): bit i = the native AI of
     * player i aims its targeted attacks (0xb8d888 -> 0xb487c4) at the linear intercept of its target brawler instead of the
     * target's position + U[-150,150)^2 noise. lead_speed: bullet speed (units/tick, <= 0: 197); lead_dt: extra ticks of
     * bullet delay in the intercept equation (|T + v t - S| = speed (t - dt)). 0 = the game unchanged. */
    uint32_t lead_mask;
    float lead_dt, lead_speed;
    float lead_frac;      /* aim = T + lead_frac * v * t (1 = the full linear intercept; 0 = the target's current position, no noise) */
    /* diversity round (2026-10-09): the battle setup a RESET asks for (appended; all 0 = the default battle, unchanged:
     * the PLAY event's location with its own theme, every player the roster brawler g_roster "Sniper" with its default
     * skin). Global data ids = CSV row + type * 1000000 (csv_logic). Checked by the game host; a rejected entry falls back
     * to the default and is flagged in NbeResp.div_err. */
    NbeDiv div;
} NbeCmd;

typedef struct {          /* per player slot, reward bookkeeping of THIS step (the phone env's info.terms) */
    int32_t present, char_id, alive, hp, max_hp, x, y;
    int32_t damage_dealt, damage_taken, gas_damage, kills, hits, box_damage, cubes, cubes_total, gas_ticks, in_gas;
                          /* cubes = picked up this step; cubes_total = held now (all picked up, 0 after a team knock-out) */
    int32_t bomb_damage;  /* PC extra: leap-bomb damage dealt (the phone agent applies it from JS: not in damage_dealt) */
    int32_t eliminated, elim_rank, elim_tick, elim_gas; /* elimination tracker (rank 10 = first out) */
    int32_t leaping, super_charge, super_max, ammo;
    int32_t reserved[4];
} NbePlayer;

typedef struct {
    uint32_t seq;
    int32_t status;       /* 0 ok, <0 error (see err) */
    int32_t tick, done, result, local_index, generation, alive, hud_left;
    int32_t local_rank;   /* elimination tracker rank of the local player (0 while alive and the match runs) */
    int32_t winner;       /* player index of the last survivor; teams: the last team's lowest-index player (-1) */
    uint32_t map_hash; int32_t map_w, map_h, map_written;
    int32_t state_ints, rec_n, rec_lost, pix_bytes, pix_w, pix_h, obs_written;
    int32_t cam_valid; float cam_x, cam_y;
    int32_t seed_applied, seed_plus1;   /* the seed stored in the sim (+0x14) and whether setSeed's +1 quirk applied */
    int32_t steps_in_frame, frame;
    int32_t us_step, us_state, us_wait;  /* timing of the last step (microseconds) */
    int32_t njumps; int32_t jumps[NBE_MAXP][5];   /* active leaps: char id, t, T, x1, y1 */
    int32_t ncubes; int32_t cubes[NBE_MAXP][2];   /* char id, cubes held (= NbePlayer.cubes_total) */
    int32_t reserved[8];  /* [0] latched storm step used by this step, [1] storm latch phase, [2] env steps since the reset observation,
                             [3] client tick (client mode), [4] pixel format of the pixel block (cmd reserved[2]),
                             [5] lead-aim corrections since the reset (lead_mask), [6] AI attack calls of lead players left unchanged */
    char err[128];
    NbePlayer pl[NBE_MAXP];
    /* expertbot round (client mode): the world camera's view-projection matrix the game uploaded for the frame drawn
     * since the previous response (column-major; render coords = (x, -y, z) of world units; clip -> pixels:
     * u = (cx/cw + 1)/2 * W, v = (1 - cy/cw)/2 * H); cam_mat_seq counts uploads (0 = none yet) */
    float cam_mat[16];
    int32_t cam_mat_seq, cam_mat_n;   /* sequence of the last upload, uploads since the previous response */
    /* diversity round (2026-10-09, appended): the battle as the game built it, read back from the game's objects at every
     * RESET response (kept until the next RESET): the sim's location (sim+0x50) and its theme (location+0x58), the client
     * controller's location (+0xc8, client mode; else 0), the mode variation (sim+0x104), per player the character and skin
     * of its active loadout (player+0x30[player+0x40]: +0x00 character, skin = player+0x1d8 or loadout+0x20). Data ids. */
    int32_t div_valid;                /* 1 = written by this game host */
    int32_t div_location, div_theme, div_cl_location, div_variation;
    int32_t div_err;                  /* rejected requests: bit i = player i's character / skin, bit 30 location, bit 31 theme */
    int32_t pl_char[NBE_MAXP], pl_skin[NBE_MAXP];
    int32_t div_reserved[4];          /* [0] sim+0x134 (cards flag: star powers / gadgets in player configs), [1] bit i = player i
                                         has a gadget object (player+0x190), [2] bit i = player i's config has a star power card */
    /* gadget round (bsrl-sim issue #3, appended): the gadget state of the host's own gadget activation. The shipped libg's
     * activation 0xb27c58 (reached by input kind 8, NbeAction.fire 3) is a bare ret, so the uses and the cooldown are the
     * host's, kept per player for the battle. A host without it leaves everything 0 (gad_valid 0): every gadget reads as
     * not usable and the policy's gadget class stays masked (bsrl-sim obs_v5 self 3). Per player index: */
    int32_t gad_valid;                /* 1 = written by a host with gadget activation (every response) */
    int32_t gad_card[NBE_MAXP];       /* cards.csv data id of the player's gadget (0 = none) */
    int32_t gad_kind[NBE_MAXP];       /* NBE_GAD_* activation the host runs for it; NBE_GAD_NONE = not implemented (not usable) */
    int32_t gad_charges[NBE_MAXP];    /* uses left this battle */
    int32_t gad_cd[NBE_MAXP];         /* ticks until it can be used again (0 = now) */
    int32_t gad_used[NBE_MAXP];       /* activations so far this battle */
    /* hypercharge round (bsrl-sim issue #4, appended): the host's hypercharge (hyper.c: libg's activation, the host's drain,
     * expiry and buffs). The charge and its max are NbePlayer.reserved[0] / [1]. A host without it leaves all 0 (hyp_valid 0).
     * Per player index: */
    int32_t hyp_valid;                /* 1 = written by a host with hyper.c (every response) */
    int32_t hyp_card[NBE_MAXP];       /* cards.csv data id of the equipped hypercharge card (0 = none: cannot hypercharge) */
    int32_t hyp_left[NBE_MAXP];       /* ticks of hypercharge left (0 = not active) */
    int32_t hyp_used[NBE_MAXP];       /* activations so far this battle */
    int32_t hyp_damage_pct[NBE_MAXP], hyp_speed_pct[NBE_MAXP], hyp_shield_pct[NBE_MAXP];   /* buffs while active (characters.csv) */
    /* hypercharged supers (appended): supers cast while hypercharged so far, and the SkillData data id the last one used
     * (the brawler's OverchargedUltimateSkill where characters.csv has one, else its UltimateSkill) */
    int32_t hyp_supers[NBE_MAXP], hyp_super_id[NBE_MAXP];
    /* gear round (bsrl-sim issue #51, appended): the gears in each player's config and the host's gear state (gear.c); all 0
     * (gear_valid 0) with a host without it. gear_stat per player, counts this battle: [0] hits boosted by LowHealthDamage,
     * [1] hp the ConsumableShield absorbed, [2] moves sped up by ForestSpeed, [3] reload queries ReloadSpeed answered */
    int32_t gear_valid;
    int32_t gear_id[NBE_MAXP][2];     /* gear_boosts.csv data ids in config +0x18 / +0x20 (0 = none) */
    int32_t gear_shield[NBE_MAXP];    /* ConsumableShield hp left (0 without the gear) */
    int32_t gear_stat[NBE_MAXP][4];
} NbeResp;
/* NbeResp.gad_kind: what an activation does (one re-implementation per kind, from the gadget's own data rows) */
#define NBE_GAD_NONE 0
#define NBE_GAD_DASH 1        /* moves the brawler (displacement along the aim) */
#define NBE_GAD_HEAL 2        /* restores hp */
#define NBE_GAD_SHIELD 3      /* damage reduction / shield for a while */
#define NBE_GAD_SPAWN 4       /* spawns an object (summon, turret, item, area) */
#define NBE_GAD_PROJECTILE 5  /* fires a projectile (along the aim) */
#define NBE_GAD_STATUS 6      /* a timed status on self or others (speed, slow, stun, ...) */
#define NBE_GAD_SUPER 7       /* charges the brawler's super */

typedef struct {
    uint32_t magic, version, total_size, hdr_size;
    uint32_t off_cmd, off_resp, off_state, off_map, off_rec, off_pix, off_obs;
    uint32_t state_cap, map_cap, rec_cap, pix_cap, obs_vec, obs_grid, maxp;
    volatile uint32_t cmd_seq;    /* written by Python */
    volatile uint32_t resp_seq;   /* written by nbhost */
    volatile uint32_t status;     /* NBE_ST_* (nbhost) */
    volatile uint32_t heartbeat;  /* frames (nbhost) */
    volatile int32_t pid;         /* nbhost's pid (as seen by the guest) */
    volatile int32_t boot_ms;     /* time from start to the first battle */
    volatile int32_t crashed;     /* signal number if the crash handler ran */
    uint32_t reserved[13];
} NbeHdr;

#define NBE_OFF_CMD 256
#define NBE_OFF_RESP 4096
#define NBE_OFF_STATE (64 * 1024)
#define NBE_OFF_MAP (NBE_OFF_STATE + NBE_STATE_CAP * 4)
#define NBE_OFF_REC (NBE_OFF_MAP + NBE_MAP_CAP * 4)
#define NBE_OFF_PIX (NBE_OFF_REC + NBE_REC_CAP * 32)
#define NBE_OFF_OBS (NBE_OFF_PIX + NBE_PIX_CAP)
#define NBE_TOTAL (NBE_OFF_OBS + NBE_MAXP * (NBE_OBS_VEC + NBE_OBS_GRID) * 4)
