# Hunt Exhaustion Ends Active Hunts Early

## Summary

Active hunts should no longer persist solely until their timer expires. Each active hunt instance must track which hunt fish are still available during that activation. When the player catches a hunt fish during an active hunt, every remaining entry with that fish name is removed from that active hunt's available hunt fish. If no hunt fish remain, the hunt ends immediately. The existing timer limit still applies and remains a second independent end condition.

## Goals

- Remove caught hunt fish from the currently active hunt only.
- End hunts early when all hunt fish for that active hunt have been exhausted.
- Preserve the timer-based expiration as a separate limit.
- Restore a fresh full hunt fish list when the next activation of that hunt starts.
- Keep save/restore behavior compatible with older saves that do not store depletion state.

## Non-Goals

- Changing hunt spawn conditions, disturbance accumulation, or cooldown tuning.
- Supporting duplicate fish names as a content pattern. If duplicates exist anyway, all matching entries are removed by name when that fish is caught.
- Refactoring unrelated event or pool selection systems.

## Current Behavior

The active hunt uses the hunt definition's full `fish_profiles` list for availability throughout the hunt duration. A hunt ends when its timer expires or when it is replaced forcibly. Catching a hunt fish marks the catch as a hunt catch, but the active hunt does not deplete its remaining hunt fish based on the caught species.

## Desired Behavior

### Active Hunt State

Each `ActiveHunt` instance should carry its own remaining hunt fish state derived from `definition.fish_profiles` at activation time.

This state must be rebuilt whenever a hunt starts, including forced hunts and naturally spawned hunts.

This state must be serialized with the active hunt entry so saving mid-hunt preserves which hunt fish are still available.

### Catch Consumption Rules

When a fish is caught:

- Only the active hunt for the selected pool is eligible for depletion.
- Depletion only occurs if the caught fish belongs to that active hunt's remaining hunt fish.
- All remaining entries with the same fish name are removed from the active hunt state.
- If at least one distinct hunt fish remains after removal, the hunt continues.
- If no hunt fish remain after removal, the hunt ends immediately and enters the same completion path used by timer expiry.

For hunts with multiple distinct hunt fish, catching one hunt fish must not end the hunt if another hunt fish remains. Example: `hunts/o_guardiao` should stay active after catching `Mossjaw` if `Awakened Mossjaw` remains available.

### Availability During Fishing

The fishing round should use the active hunt's remaining hunt fish rather than the full hunt definition list when building the available fish set for the current pool.

If an active hunt has already had one hunt fish removed, subsequent round setup and selection must no longer offer that removed hunt fish during the same activation.

### End Conditions

A hunt now ends when either of the following becomes true:

- The active hunt timer reaches zero.
- The active hunt has no remaining hunt fish.

Both conditions should emit the normal hunt-ended notification message.

### Save Compatibility

Serialized active hunt data should include the remaining hunt fish names for that activation.

When restoring:

- If remaining hunt fish names are present, rebuild the active hunt from those names.
- If the field is missing, treat the save as an older format and rebuild the active hunt using the full hunt definition list.
- Ignore unknown fish names during restore rather than failing the load.

## Design Details

### State Shape

Extend `ActiveHunt` with per-activation hunt fish state. The minimal persisted representation is a list of remaining fish names in current availability order.

The runtime may reconstruct the actual `FishProfile` objects from the hunt definition whenever needed, but the saved representation should stay simple and resilient.

### Hunt Manager Responsibilities

`HuntManager` should become the source of truth for active hunt depletion. It should expose helpers that:

- return the currently available hunt fish for a pool
- consume a caught hunt fish from the active hunt for that pool
- report whether consuming that fish ended the hunt

The manager should also centralize the immediate termination path so timer expiry and fish exhaustion produce the same cleanup and notification behavior.

### Fishing Loop Integration

The fishing loop should query `HuntManager` for the active hunt's currently available hunt fish when composing the combined fish list for a round.

After a successful catch, if the fish was a hunt fish, the loop should notify `HuntManager` of the pool and fish name so the manager can deplete the active hunt and end it if exhausted.

## Testing Strategy

Add or update characterization tests for these cases:

1. Starting a hunt initializes its remaining hunt fish from the hunt definition.
2. Catching one hunt fish removes it from the active hunt but keeps the hunt active if another distinct hunt fish remains.
3. Catching the final remaining hunt fish ends the active hunt immediately.
4. Depletion affects only the currently active hunt instance and resets on the next activation.
5. Serialize/restore preserves remaining hunt fish state for an in-progress hunt.
6. Restore from older save data without remaining fish names rebuilds the full hunt fish list.

## Risks And Mitigations

- Risk: save compatibility break for in-progress hunts.
  Mitigation: make remaining fish names optional during restore and default to the full hunt definition list.

- Risk: fishing still reads from `definition.fish_profiles` in one code path.
  Mitigation: route all active hunt fish availability through `HuntManager` and cover this with roundtrip tests.

- Risk: duplicate fish names in a hunt behave unpredictably.
  Mitigation: remove all matching entries by name and treat duplicate-name hunts as unsupported content.
