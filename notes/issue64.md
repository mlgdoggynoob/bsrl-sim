# Issue #64: the last seven masked gadgets

Branch `masked-seven` from e5daa5e (the `repeat-masked` head, 2026-11-26). Game data and libg v68.279. Patch:
`engine/patches/masked_seven.patch`, a diff on top of `star_powers2.patch`.

Bo's BowDude_Totem (23000263), Max's Speedy_Rewind (23000311), Frank's HammerDude_Pull (23000351), Griff's
AssaultShotgun_Bomb (23000399), Leon's Ninja_InvisibleArea (23000408), Damian's Gladiator_Amp (23001247) and Starr Nova's
MagicalGirl_FlyArea (23001255) were masked. All seven work now and are unmasked (`gadget.c` g_masked, which keeps six
NEXT / pull rows, `super_audit.MASKED`, `desc_audit`'s check). Usable gadgets: 100 of 213 (was 93).

## Summons and items: the shot was never armed

- All five (Bo, Leon, Starr Nova, Damian, and Spike's Cactus_Cover, which was not masked but whose cactus never spawned) are
  SHOT rows whose skill has SummonedCharacters or a SpawnedItem. libg's attack path arms each projectile after the spawn:
  0xb703c8(proj, CharacterData, NumSpawns, MaxSpawns, ...) stores the summon at proj +0x1c0, 0xb79130(proj, ItemData, count,
  max, damage, ...) the item at +0x1c8, and the projectile's end spawns them (0xb77344 for a summon, the item factory
  0xb55684). `gadget.c` used the bare spawn 0xb78190, which leaves both empty: the projectile flew and nothing came out.
- `arm_shot` now does what the attack path does for a SHOT gadget's projectiles (skill data getters 0xb0dd5c NumSpawns,
  0xb0dd6c MaxSpawns, 0xb0ddf8 the summon, 0xb0de70 the item; the item's max from 0xb6e680; its two damage words the
  projectile's damage and the skill's 0xb0dc14, as the Attack handler sets them at 0xb7ed38). The summon's four extra
  words are passed as 0 [?] (the attack path's are skin bonuses).
- Bo's totem area (BowDudeSuperChargeArea, ExtraSuperCharge, type 31) gave a flat charge. The card says +50 % charge from
  hits inside it: every tick, each teammate inside now holds a ZN_TOTEM mark of the area's CustomValue (50) for that tick,
  which env.c's charge hook adds through `superfix_status_charge_pct` (summed with Edgar's hypercharge zone and status
  charge boosts [?]). Live: charge per damage 0.370 before the totem, 0.555 with it (x1.50); the totem loses
  HP (1000 -> 650 in the watch: HealthPromilleLostPerSecond).
- Leon's smoke (NinjaInvisibleArea, SmokeScreen) needed nothing else once it spawned: the far target saw Leon before the
  fire and not after it (observation grid, enemy channel).
- Starr Nova's device (MagicalGirlFlyArea, StatusEffect area, HitLevitating) adds MagicalGirlLevitation (Levitation
  attribute, 10 ticks, Refreshable) to its owner's team. Two gaps:
  - The status was added once: StatusEffectTickInterval is 0 and the store refreshed it only on entry.
    `superfix_status_area` now re-applies an interval-0 area's ally status every tick when the area belongs to a summon and
    the status is Refreshable.
  - libg reads a levitating byte at char +0x9b0 (hit test 0xb5033c skips the character unless the source area has
    HitLevitating; knockback 0xb49834; obstacle tests 0xb511c8 / 0xb51240; damage 0xb41e00 / 0xb3bfa4) but nothing in the
    client writes it. `superfix_status.c` sets it while a store status with Levitation (StatusEffectData +0x157) from an
    area is on the character. Whether a status came from an area is decided when it is added (the area may be gone
    while its 10-tick status lives). Levitation is not in the observation: an enemy sees only the device.
  - `superfix.c`'s summon-area table (a summon's own area, issue #19) was never emptied between battles: character ids
    restart in a new battle, so an old entry with the same id kept the new device (and in one run Bo's totem) from
    getting its area. It is emptied when a new battle is built (`env_on_build`), and when the character's sim changes or
    its tick goes back.
  Live: the target's shot after the fire took 0 HP (600 before it; 3212 / 0 in a full run). The device sits in the line of fire if thrown at the
  target and the target's shots destroy it, so the audit throws it at right angles (`aim_off`).
- Damian's microphone (GladiatorHealingItem, items.csv type 72, CanBePickedUp, PickUpOnlyByTeam) was picked up by libg's
  scan but its StatusEffectAlly (GladiatorGadgetHeal, 1600 healing on the first tick) was never given: the pick-up effect
  is server code. `superfix_items.c` `pickup_update` gives it to the picker (0xb35dd0, as the area status path does) once
  the item's pick-up flight ends, then removes the item. libg's scan does not leave out the thrower, so Damian heals
  himself; the text says "teammate", and every player is solo here. Live: hit for 600 after the throw, healed 600 at the
  pick-up (2080 in another run).

## Max: the host's rewind

- The bolt (SpeedyRewindProjectile, Indirect) spawns its own marker area when it ends: libg's projectile end
  (0xb75afc -> 0xb76c0c, iteration 0 reads ProjectileData +0x128 through 0xafa7f4) spawns the skin's
  SpawnAreaEffectObject, SpeedyRewindArea (an Effect area that does nothing), the same way Griff's
  AssaultShotgunGadgetProjectile2 spawns its explosion. The host does not spawn a second one: it finds the bolt's area
  with libg's finder 0xb2b1b0(data, Max), and spawns one itself (0xb35c40) only if none shows up within 4 ticks.
- New kind REWIND in `gadget.c` (card 23000311): the bolt at the aim (aimed range, a walkable spot from
  `superfix_valid_spot`). At the throw + 3 s, or at a second fire while the rewind is pending (GadImpl.again, before the
  cooldown test, no use spent: the card's reactivation), the host teleports Max to the area (`superfix_teleport`: valid
  spot, mover stopped, 0xb6a61c), heals the HP lost since the throw (0xb41554) and ends the area. Max dead or another
  character: no rewind, the area ends.
- Cooldown: none while the rewind is pending, so the gadget publishes ready and the policy can reactivate it (obs_v5
  self 3). The full 300-tick cooldown starts at the rewind, or when Max dies first (the throw skill has
  NoBonusSkillCooldown, the blink skill FullBonusSkillCooldownOnDeath).
- libg's own SpeedyRewind component (vtable 0x120a880, at char +0xa60 / +0xa6c) is not used. Its skill-used 0xb9bb84
  stores the area and Max's HP and listens to the area's expire, where 0xb9be00 teleports and heals her. Nothing in this
  libg detaches it when Max dies (0xb9bc8c's only caller is 0xb9bb84 itself), so with Max gone from the object list the
  expire handler could run on a freed character. The host's rewind does the same and is safe at a death.

## Frank and Griff: stale masks

- Griff's bomb already worked (1600 damage, AssaultShotgunGadgetBombExplosion r800, a 900 u push); the "no explosion"
  note predates a later fix [?].
- Frank's pull worked too: 2480 damage and the target ended 900 u nearer (the projectile's PushbackStrength -150 through
  libg's knockback). What was missing was the cost: HammerDude_Pull has UseWeaponAmmo (SkillData +0x238). `shot_ready`
  now needs one ammo bar (ammo_skill +0x18 >= 1000, more while attacks are queued) and `shot_fire` spends it. The other
  UseWeaponAmmo SHOT rows (ShotgunGirl_Focus, Gunslinger_BigBullet, Mummy_Acid, the Percenter rows,
  MechaDude_ReloadTower, FutureGirl_ProjectileGadget) pay it too now, from the data flag alone (their texts do not say
  "consumes ammo"); Arcade_Double is a skill area and unaffected.

## The audit

- `super_audit` checks each effect (`shot_effects`): `decay` (the summon's HP drops), `hide` (the far target, 1800 u away,
  saw the shooter before the fire and not 30 ticks after), `boost` (charge per damage of a main attack 20 ticks after the
  fire, inside the totem's area, >= 1.3 x that of one 30 ticks before it; measured before the super is full, since a
  shooter that was a target in an earlier phase starts with charge), `float` (the target's shot 30 ticks after the fire
  takes no HP), the pick-up heal (Damian walks to his item; one step's HP rise within 55 ticks of the target's hit, at least
  0.8 x that hit, so regen's 600 a step after 3 s does not count), and Max's `move` + `heal` (at least 0.8 x the hit after
  the throw healed back) and `reactivate` (a second fire 3, 16 ticks after the throw, brings her back within 10 ticks,
  long before the 3 s end). Rewind and pick-up rows get no pre-damage (Max did not survive both hits). Frank's row expects
  `pull` from the projectile's negative PushbackStrength. An Effect area (Max's marker) no longer counts as harmful.
- `desc_audit`: "health" no longer reads as a heal ("slowly loses its health" flagged Bo and Leon), and a shot whose skill
  summons or spawns an item gets the game's own effects (`status` / `item`), so Damian's heal text matches.

## Guesses

- `arm_shot`'s summon bonus words are 0; a skin with summon bonuses would differ.
- The UseWeaponAmmo cost is one bar per fire for every such row (the column is a flag, its amount is not in the data).
- Bo's totem percent adds to the other charge boosts (Edgar's hypercharge zone, statuses) rather than taking the max.
- The levitating byte is set only from store statuses whose source is an area; a Levitation status from elsewhere (none
  in the data now) would not set it.

## Checks run (final build)

- `super_audit --gadget` (all 56 slot-0 rows): works 53, partial 3. All seven of this issue work: Max, Leon, Starr Nova,
  Damian, Bo and Griff on the first try (Bo x1.50 charge per damage, Starr 3212 -> 0 HP on the second hit, Damian healed
  2080, Max reactivated 17 ticks after the throw, back 480 u two ticks later and healed 5040, with one SpeedyRewindArea:
  the bolt's own; Griff 1600 damage). The 3 partials (Crow, Pam's MinigunDude, Byron's SnakeOil) work in a smaller batch
  or were partial on main too (Byron): neighbour and spot effects, as in #63.
- `--gadget-slot 1` (17 rows): works 16, partial 1. Frank (2480 damage, pulled 900 u nearer) and Spike's cactus (the
  CactusCover summon spawns) work first try. Belle's slot-1 row is partial in the full run (her shots stop at a wall
  200 u out on the retry spot) and works alone.
- Smaller batch (Max, Bo, Damian, Starr Nova, Leon): all work; the host log shows 1 bolt, 1 reactivation, 1 rewind and
  0 areas spawned by the host.
- `gadget_check` (live): ok, random roster (2 rewind reactivations judged; 33 SHOT volleys within limits: Frank 2480 =
  1.1 x his attack, Shelly's Clay Pigeons 1.0 x, Emz's Acid 1.0 x) and the seven's brawlers as `--roster`. `status_check`,
  `charge_check`, `star_audit`, `test_fast`, `live_check`, `showdown_check`, `train_ppo --run g --smoke --gadgets 1`: ok.
- Self-checks ok; `export_policy --check` (no onnx) and `policy_video --check` (no ffmpeg) need tools this machine lacks.
  `notes/desc_audit.md` regenerated (1 flagged row, JetpackGirl, as before).
- `git apply -R --check --directory=engine engine/patches/masked_seven.patch`: ok.
