# Description values (issue #55 step 2): how the client fills <VALUEn>

Static reading of the shipped `libg.so` (v68.279, `engine/native/LIBG_SHA256`), 2026-11-25. Not run in the host yet.

- cards.csv `Value` / `Value2` / `Value3` are codes, not numbers: for a card whose Type is accessory the client reads
  each in turn and switches on it (codes 1..85) to compute the number that fills `<VALUE1>` .. `<VALUE3>`.
- Description builder: around 0x90bde8 .. 0x90e4f4 (the `<VALUE1>` / `<VALUE2>` string loads at 0x90c074 / 0x90c098). The
  card Type dispatch (table 0x1fc058) sends accessory cards to 0x90ccd0; the code switch starts at 0x90d5ac (halfword
  jump table at 0x1fc2e0, target = 0x90d548 + 4 * entry). The file has no section headers: virtual address = file offset
  in the first segment. Disassembled with llvm-objdump on a raw extract.
- The getters the codes call are the accessory's own columns, not a projectile's: 0xa933d0 / 0xa933e0 / 0xa933f0 read
  accessories.csv CustomValue1 / 2 / 3 and 0xa932c8 reads ActiveTicks (gadget.c AD_CV1 .. AD_CV3, AD_ACTIVE_TICKS: the
  same 16-byte getters, column slot at 0x123f000 + 0x790 + 4 x (column - 4)).
- Damage codes (medium confidence): 50, 51 / 68 and 54 read CustomValue1, 2 and 3 times the brawler's damage stat at the
  card's power level (`base + (level - 1) * base / 10`), / 100. So the description treats those CustomValues as damage
  numbers, which questions gadget.c REPEAT's reading of CustomValue1 / 2 as a shot count and spread (issue #54). Not
  settled: Gene's HookDude_Homing (Value2 51, CustomValue2 80) reads as 80 % per missile, but Piper's HandGun (Value2 50,
  CustomValue1 5) would give 5 %, so the stat in the product may not be the main attack's damage.
- Code 19 (and 18, same case 0x90d618): ActiveTicks combined with CustomValue1; not traced to the end (low confidence).
- The other codes are not mapped yet. Mapping each getter to its projectiles.csv column needs the field-id tables the
  client loads at run time (near 0x123f81c / 0x123f7a4), or one card with a known on-screen number per code.
- Many descriptions do not use codes at all: they embed paths such as
  `<!card.accessory.skill.damage.scaleToLevel>` or `<!card.accessory.skill.projectile.chainbullets>`, which name the
  data directly (desc_audit's table keeps them in the text column).

Next: port the damage codes to Python (projectile row x characters.csv damage at level / 100) and check them against a
few known on-screen numbers, or call 0x90ccd0 from the host for every card. Either way no measurement is needed.
