# Issue #46: more gadgets (batches 0, 1 and 2, review fixes)

Branch `gadgets-next`, first on main 48387c6 (2026-11-25), rebased on main 232e80e (2026-11-26, after #53, #57-#62
and #69). Game data and libg v68.279. Patch: `engine/patches/gadgets_batch3.patch`, now a diff on top of
`hyper_unmodelled.patch`.

## What works now

Usable gadgets: 89 of 213 (`super_audit.gadget_kind` counts 79: shot 25, next 16, status 13, area 10, repeat 4,
skill_area 2, item 2, shield 2, super 2, heal_now 2, auto_aim 1; plus the 7 dashes and 3 heals it does not cover).
17 more classify but are masked (no effect live), 107 are not usable. Main alone (232e80e) had 52 in its README.
Batch 1 added 16 next-main-attack modifiers (`next_attack_change`, accessory type 23), published as STATUS:

Mandy Slow, Finx (stasis shot), Pearl Poison and Healing, Cordelius (silence shot), Janet
(jump attack), Pam (ammo sink), Doug x2 (double heal / double damage area), Sandy (sleep), Ollie (taunt shot), Byron
(spread), Otis (big shots), Belle (bounce shot), Piper (seeker), Squeak (longer throw). Hank's slow classifies too but
is masked (below).

## The rebase on 232e80e

- Main re-implemented Buzz's grapple (pull and landing stun, `superfix_moves.c`), so the Reserve Buoy's catch is real
  now: the buoy remembers the brawler, and the grapple asks `gadget_buoy_nostun` when his next torpedo ends (hit or
  miss); that one lands without the stun. Both files had a `superfix_cc_stun`; there is one now, returning whether the
  stun was applied.
- Main made Squeak's blobs blow (`superfix_items.c`). His next-attack range gadget (StickyBomb_Range) was masked for "no
  damage"; with the blobs blowing it works in `super_audit --gadget`, so it is no longer masked.
- Main's masks (Darryl, Fang's popcorn, Bea, Amber) and ours are both in `g_masked` / `super_audit.MASKED`. No address is
  hooked twice (0xb422c8, 0xb27cfc, 0xb78c28 only in `gadget.c`).
- `desc_audit` reads the new kinds: next and status run the game's own data, shield is a shield, Buzz's buoy names his
  super's stun. Janet's "even over walls" (libg's own recoil) is listed in `gadget_check.DESC_OPEN`, not checked yet.
- `super_audit.expected_gadget`: the text's push / heal for next SubTypes 15 (Janet's own recoil), 21 and 24 (heals for
  allies) is a note, not expected on the target.
- Main now has Lou's freeze meter, Sirius's shadows and Kit's attach. Lou Cryo Syrup and Sirius Master of Shadows are
  doable on top of them, and Kit's Cheeseburger could heal the attached ally: left for a later batch.

Measured after the rebase (2026-11-26):
- `super_audit --gadget`, full runs: slot 0 works 45, partial 4, unverified 1 (50 brawlers); slot 1 works 11, partial 1
  (12). Janet, Doug and Pearl missed a push / heal their text names for the shooter or its allies (now notes, see
  above); Bull's mark and Mico missed "damage" and Kenji was unverified in the crowded battle. Rerun alone (`--only`):
  all six work. So slot 0 is 50 of 50 and slot 1 12 of 12 working; main alone had 35 and 8.
- `gadget_check --roster` (25 brawlers): all 7 kinds, every judged activation showed its effect; random: ok.
- `status_check`, all 8 battles: 39 of 39 scenes ok. `charge_check` 7 of 7 (main's R-T scenes too). `test_fast` 0 of 400
  polls differ. `train_ppo --smoke --gadgets 1` ok. `live_check` and `showdown_check` (one instance each) ok.
- Buzz's buoy, a one-off debug boot (NB_SUPERFIX_DBG=1): a plain torpedo's landing stunned the target (18 ticks), the
  one after a buoy stunned nobody ("Reserve Buoy: no stun"), the next plain one stunned again.

How it runs:
- The host sets the accessory pending (+0x3c). The getter libg asks for the character's accessory, 0xb422c8, is a stub
  (`mov x0, xzr; ret`) in this client build; replaced by `acc_of_char` (player +0x190), libg's skill tick arms the
  modifier (+0x54) and its attack code runs the SubType branch itself.
- libg calls the stub 0xb27cfc ("modifier used", 20 call sites) when it uses one; a hook clears it there. Sites seen:
  0xb4bf20, 0xb4e314, 0xb4de4c, 0xb4f63c, 0xb7fcd0, 0xb7facc, 0xb811b8 (at the shot), 0xb3e1ac, 0xb3b800 (at the hit).
- SubType 2 / 33's enemy status: hook on 0xb78c28 writes the row's StatusEffectEnemy into the shot's hit struct (+0xd0).
- Server-only hit fields, read after the damage in env.c's root (`gadget_root_post`): Sandy's sleep (a 20-tick stun the
  next damage ends), Pam's ammo sink (victim -25 % of full ammo, Pam +50 % of that; measured -750 / +375).
- An armed modifier that sits 20 ticks with no consume, or a pending one with no attack in 200 ticks, is dropped; so is
  one whose brawler died or changed [?].
- `acc_of_char` answers only for the brawler's own character (not summons) when its gadget is a NEXT one; the gadget
  table is cleared when a battle is built, so no pointer outlives its battle.

## Batch 2: the brawler's own statuses, shields, heals (18 more)

New file `engine/native/loader/gadget_self.c` (gadget.c keeps the uses, cooldown and readiness and calls in through its
SELF entries). The game's server code for these is not in the client build, so the effects are re-implemented:
- Statuses go into superfix's status store through libg's add wrapper 0xb35dd0, so the store's aggregates do the work:
  shield (+0xf4), invisibility (+0x12c), lose control (+0x131), speed, reload (+0x124) and the super charge boost (+0xc4,
  now read by `superfix_status_charge_pct`). A card with its own status row uses that row; the others get a small
  synthetic row (one static block per player).
- Rows: Jacky speed, Bonnie Sugar Rush (her row plus a reload of 100*30/130 = 23 %), Hank shield (40 %), Lou freeze (100 %
  plus lose control), Willow dive, Juju (bush: invisible, water: VoodooGadgetSpeedUp, else VoodooGadgetShield; both rows
  looked up by name), Kit's box (invisible), Surge x2, Trunk, Moe (+50 % super charge), Draco Last Stand, Sandy sleep,
  Tara vision, Buzz vision. Hank and Lou publish SHIELD, the rest STATUS.
- CancelOnDamage only for these gadget statuses (not every row that has the flag): the first damage that takes HP ends
  it; Surge's shield row then gives 2 ammo bars.
- Trunk's ReceiveDamageInversion and Draco's Last Stand run in `gadget_root_pre`, which env.c's root calls before libg's
  root: Trunk's first damage instance heals instead and ends the status (one pellet of a shotgun shot); Draco's damage is
  clamped to hp - 1. It runs after the just-popped check and skips a waiting brawler and the storm's damage [?].
- Sandy: lose control for ActivationDelay (30 ticks), then a full heal; damage wakes her early with no heal. The sleep
  status her gadget puts on an enemy (batch 1) only takes off what is left of its own stun when damage wakes the enemy.
- Tara / Buzz: env.c's bush hiding asks `gadget_vision`. Tara's team sees every bush enemy; Buzz's sees those within 1800
  of him (RopeDudeSuperChargeArea's radius). The observation's shape does not change.
- gadget.c: Meg's heal (SubType 4, only in her mech: UniqueProperty 2 via 0xab3d04), Byron's ConsumesAmmo (needs and
  spends one bar; the column's index word is 0x123f7c0, read with the generic bool getter 0xcf6a08), Buster's heal as an
  AREA (heal SubType 6), Buzz's Reserve Buoy (BUOY, published SUPER: fills the super, not ready while it is full), and
  Kenji's heal the right way round (CustomValue2 % of the damage taken in the last CustomValue1 ticks, as the client's
  preview 0xb27c5c computes it).
- `NB_GAD_SELF=0` turns the SELF kinds off. They also need superfix's store (`superfix_status_live`).

Measured (`status_check --battles 5,6`): Jacky 805 -> 1011 u/s; Hank's shot 3000 -> 1800; Draco under fire of
three stays alive at 1 HP; Trunk's shot after the gadget took 1800 (one pellet healed), the next 3000; Surge 1050 -> 3000
ammo at the hit; Tara's bush enemy hidden before, visible during; Moe 0.400 -> 0.600 super charge per damage; Sandy moved
0 u asleep and woke at full HP; Lou's shot 3000 -> 0. `super_audit --gadget`: Buster's heal area works (healed 936).

Measured (`status_check --battles 7,8`): Buzz's bush enemy hidden before, visible during; Byron refused at 272 ammo,
with 2040 ammo it spent a bar (-> 1074) and healed 2200 -> 3500; Buzz's buoy refused on a full super, then 0 -> 4000 of
4000; Juju's shield 3000 -> 2100; Bonnie 634 -> 831 u/s; Meg healed +518 in 20 ticks in her mech; Kenji lost 3000, healed
1500; Surge's Power Surge 0.600 -> 0.780 super charge per damage (x1.3; his shot starts about 350 u out and did not
reach a target at 600 u, so the scene uses 400 u); Willow's shot 3000 -> 0 while diving; Kit seen from 2000 u before
his box, not in it. All 39 status_check scenes pass.

Buzz's buoy: before the rebase every torpedo was already a no-stun one (no grapple in the host). Main's grapple now
stuns, and the torpedo after a buoy skips that stun (above).

Partial (their checked part works live): Kit's box (the faster charge while standing still is not done), Willow's
dive (shield 100 + lose control; projectiles still stop on her and enemies still see her), Buster's
heal (the per-ally scaling, CustomValue3, not done).

Review fixes (same patch): readiness is recomputed right before each response (Byron's last attack could spend the ammo
after the tick's readiness was set; `gadget_check` caught it), and Byron's counts the main attacks still queued for
the next step start (`g_fire_delay`: they spend a bar each before that step's gadget input; `gadget_check --roster`
caught a fire published ready and then refused); skill gadgets whose skill has MaxCharge 2..9 (Shelly's
Clay Pigeons, Colette's Na-ah) get that many shots per cooldown, each after the skill's own Cooldown (250 ms = 5 ticks)
[?]; superfix's `charge_pct` now also gives two non-gadget rows their effect (RockWeaponDamageBoost 50,
DaredevilSpUltiChargeRate 30), as the game data says. The skill Cooldown fallback (a skill gadget with no
BonusSkillCooldown; none of the classified rows) is read as ms / 50: the getter 0xb0d868 gives the raw column, ms.

Guesses [?]: Surge / Trunk's ally rows put on the brawler only; Juju's and Kit's invisibility level 1; Bonnie's gadget
only in her starting form; Kenji's CustomValue1 as the window in ticks; Willow's dive as shield + lose control.

Left for later (Batch 9 guesses): Edgar's consumable shield, Bolt's speed shield, Nani's Return to Sender, Chester's
Candy Beans.

## Batch 0

- Readiness: a kind can say "not ready" (NEXT: a modifier is pending). The gadget then publishes cooldown >= 1, and a fire
  is refused without spending a use. `gadget_check` judges this.
- Skill gadgets' cooldown: the accessory's own, else the skill's BonusSkillCooldown (the getter is 0xb0d878, not 0xb0d880
  as the plan said; that is mid-function), else the skill's Cooldown. Before, the skill's Cooldown column (ms) was read
  as ticks: 250 ticks for most skill gadgets, 50 for Colt x2, Frank's Noise Cancel and KatanaKid_FishNet, 0 for Griff's
  Coin Shower (no cooldown at all). Now 300 to 480 ticks (15 to 24 s), e.g. Colt 340 / 300, Griff 300, Bull 400,
  Mortis 480 / 360, Shelly 360 and Colette 340 (3 shots each per cooldown).
- `super_audit --gadget` now preps (fills / fires the super, waits) and watches per row; it follows each next-attack gadget
  with two main attacks and compares them.

## Measured after batch 1 (super_audit --gadget, both slots, one boot each)

- Full run: slot 0 works 39, partial 11, unverified 1; slot 1 works 10, partial 3. The next rows partial there (Byron,
  Cordelius, Mandy Slow, Piper) only missed "damage" in the crowded full battles; each worked in its batch-only run.
- Statuses seen in the host log: Finx stasis 40 ticks, Cordelius silence 20 ticks, Ollie taunt 20 ticks, Mandy's slow,
  Pearl's poison, Byron's dots. Janet moved 828 u. Doug's double damage area: 7200 damage.

After batch 2 (full run, both slots): slot 0 works 42, partial 10; slot 1 works 10, partial 3. The partials are the
crowded-battle "damage" misses as before (Cordelius, Ollie, Piper, Amber, Bea, Damian, Griff, Wendy, 8-Bit, Fang,
Barley, Spike) and Meeple's push.

## Masked (classified, but no effect live)

- Dynamike Stun: the explosion's damage reaches the root with no source object, so the stun in the hit struct is never read.
- Alli Lifesteal: consumed at the hit (0xb3e1ac), but her dash damage never reaches env.c's root; no heal.
- Buster Pull: consumed, no pull.
- (Squeak Range was masked here until the rebase: his blobs never blew. It works now.)
- Mandy Pierce, Angelo Pierce: armed, never consumed in 20 ticks, no pierce.
- Hank FishTank Slow: armed and consumed at 0xb7fcd0 and the shot does its damage (2100), but no slow status is ever
  added in the host log.

## Guesses [?]

- NEXT_TIMEOUT 200 ticks: the game keeps a pending modifier until the next attack; the timeout only guards a path that
  never arms it.
- NEXT_IDLE 20 ticks: the slowest hit-time consume seen was 10 ticks after arming. Char +0x4f4 stayed 0 for every armed
  attack, so this is in effect a time limit.

## Not doable for now (22 cards)

Ash Chill Pill and Rotten Banana (rage meter), Gus Soul Switcher (spirit storage), Nori Sushi Snack (fish count), Clancy
Snappy Shooting (token counter), Kenji Dashi Dash (server attack chain), Alli Cold-Blooded (bloodhunt state), Glowy More
Lumens (tether), Melodie Perfect Pitch and Interlude (orbiting notes), Stu Breakthrough (wall-breaking charge), Chuck Ghost
Train (two-phase super never runs here), Lou Cryo Syrup and Sirius Master of Shadows (doable now on main's freeze meter
and shadows, later),
Eve Motherly Love (egg hatch), Jessie Recoil Spring (turret timer field), Lumi Grim and Frostbitten (slippery), Amber Fire
Starters (petrol is server-only), Penny Trusty Spyglass (turret rules), Draco Upper Cut (knock-up state), Grom Radio Check
(burst not in client code). Also the next-attack SubTypes 5, 6, 8, 13, 17, 18, 19, 25, 27, 28, 30: no client code.
