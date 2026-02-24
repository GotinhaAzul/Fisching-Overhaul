# Bestiary Rewards

Each JSON file defines one claimable bestiary reward.

## Trigger

- `type`: `fish_bestiary`, `rods_bestiary`, or `pools_bestiary`
- `threshold_percent`: completion percent needed
- For `fish_bestiary`, set `target.pool`:
  - pool name (example: `Mar`)
  - `All` for global fish completion

## Reward payloads

- `money`: `{ "type": "money", "amount": 5000 }`
- `xp`: `{ "type": "xp", "amount": 1200 }`
- `bait`: `{ "type": "bait", "bait_id": "cheap_bait_crate/minhoca", "amount": 10 }`
- `rod`: `{ "type": "rod", "rod_name": "Vara de Bambu" }`
- `ui_color`: `{ "type": "ui_color", "color_id": "sunset_orange" }`
- `ui_icon`: `{ "type": "ui_icon", "icon_id": "fish" }`

`rod` is supported by code, but currently not used in the starter reward files.

## Cosmetic catalog

All available `color_id` and `icon_id` values are listed in
`bestiary_rewards/COSMETICS.md`.

## Pool completion rewards

There is now one `fish_bestiary` reward at `100%` for each existing pool,
in files named `pool_*_100.json`.

Each pool reward includes:

- one pool-themed `ui_color`
- one pool-themed `ui_icon`
- `money`, `xp`, and `bait` tuned by pool difficulty
