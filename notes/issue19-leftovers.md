# Status effect leftovers (#19): running notes

Branch claude/project-thread-21arh3, base main 1270a76. Host change: `engine/patches/status_leftovers.patch`.

## Done
- Reload speed: the skill tick 0xb7b268 refills by dt*1000/T, and T (0xb80b58) ends as T*100/(100+r) with
  r = 0xb38e04(ch), a compiled-out stub (`mov w0, wzr; ret`). `my_reload_pct` answers it from the store: the
  statuses' DecreaseReloadTimePercent +0x124 (a source's statuses add once; capped at 95), as 100p/(100-p). Only Starr
  Nova's hypercharged super (MagicalGirlUltiStatusOvercharged, 90, 30 ticks) adds one in normal play: Nita's star power 2
  and Surge's reload statuses come from buddies. Measured: her transformed weapon refills 714 between attacks after the
  hypercharged super, 71 after the normal one.
- Lifesteal: the damage root heals the attacker at 0xb439c4 when 0xba3258(victim+0x890, attacker) >= 1 (stub).
  `my_lifesteal_pct`: the attacker's LifeSteal +0x10c plus the victim's statuses' SourceLifeSteal +0x110 given by that
  attacker. Measured: Starr Nova's super dealt 600 and healed her 180 (LifeSteal 30).
- Taunt / Fear: StatusEffectData Taunt byte +0x132, Fear (BooleanAttributes) byte +0x133. The host writes them to
  char +0x985 / +0x986, which libg never reads. `superfix_status_taunt` gives the newest live one (1 taunt, 2 fear) and
  its source; env.c's `apply_actions` (policy), `rec_move` (native AI mover 0xb4790c) move the character at the source
  or 1000 u away from it, and `my_skill_block` stops its attacks (a guess: the client has no rule for attacks under taunt).
  Ollie's taunt comes from the chain area SkaterUltiTaunt (r1000) when the 1500 ms landing ends, with the damage.
  Glowy's fear (MenderUltiFear) comes from her projectile's OnEnemyHitActions.
- Areas (`area_extra`), from the area tick: SmokeScreen 1 (zone: the owner's team inside is invisible at level 1, the
  obs v5.9 path, so no obs change), DamageBoost 10 (zone: Damage% to the owner's team's damage), Heal 3 without pushback
  and HealRegen 17 (libg's Hot body run once with the type set to 4), Cleanse 23 (once: enemy-given statuses, stun,
  lose-control), ExtraSuperCharge 31 / EnemyChargeSuper 26 / AllyChargeSuper 29 (CustomValue through 0xb4f7f8 every
  SC_TICKS = 20 ticks: a guess, the rate is server code).
- Gate check: env.c's patch of the apply mask (movz at 0xb29600 to #0x15) keeps the movk high bits (30, 34, 46, 52).

## Not done
- Area types 18 / 57 (Max's hypercharge), 11 / 22 (no row in use), 12 (only MechaDudeReloadTower, never spawned), 19, 32,
  33, 40, 42-44, 45, 51, 55.
- Cleanse's and HealRegen's CustomValue, an immunity after a cleanse, CancelOn* conditions.

## Checks
- `python -m status_check`: scenes 7-11 in a second battle (Ollie taunt, Glowy fear, Starr lifesteal, Starr reload,
  Sandy smoke); all 11 scenes ok on this branch.
