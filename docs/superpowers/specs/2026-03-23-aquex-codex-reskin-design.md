# Aquex — Codex CLI Reskin Design Spec

## Overview

Aquex (Aqua + Codex) is a fork of OpenAI's Codex CLI with a reskinned TUI that brings Claude Code-level polish and an ocean/fantasy aesthetic. All changes are scoped to the `codex-rs/tui` crate — no modifications to core agent logic, protocol, or configuration.

## Goals

- Make the Codex TUI visually polished and comfortable for long coding sessions
- Bring feature parity with Claude Code's UX: rich markdown, syntax-highlighted diffs, clear message separation, informative status bar, collapsible tool calls
- Apply an ocean/fantasy theme inspired by the Fisching universe
- Keep all changes in the TUI layer so upstream Codex updates remain mergeable
- Easy to remove: uninstall Aquex and use vanilla Codex, or revert the TUI crate

## Non-Goals

- Custom slash commands, progression systems, or game integrations (future work)
- Changes to agent behavior, model selection logic, or sandboxing
- Mobile or web UI

## Approach

Fork `openai/codex`, patch `codex-rs/tui` in place. No new crates.

## Color Palette

Soft, low-saturation ocean tones optimized for eye comfort:

| Role         | Name        | Hex       | Usage                                    |
|--------------|-------------|-----------|------------------------------------------|
| Background   | Deep Ocean  | `#111d2e` | Primary background tint                  |
| Error        | Coral       | `#c97070` | Errors, diff deletions                   |
| Success      | Seafoam     | `#5ba899` | Success, diff additions, user marker     |
| Accent       | Moonlight   | `#8badc4` | Assistant text accent, H3 headers        |
| Highlight    | Sunken Gold | `#c9a96e` | Warnings, H1/H2 headers, file paths     |
| Special      | Abyssal     | `#8878b8` | Tool calls, inline code background       |
| Text         | Pearl       | `#d0cec8` | Primary body text                        |
| Secondary    | Brine       | `#2a5454` | Borders, separators, line numbers, muted |

The palette adapts to the user's terminal background using the existing `is_light()` detection:
- Dark terminals: use the accent values above
- Light terminals: fall back to Codex default styles (light-mode palette is deferred to a future iteration)

Background blend effects (~8%, ~5% opacity) require 24-bit true-color support. On terminals that lack it, skip background tints and use plain text colors only. The existing `terminal_palette.rs` / `best_color()` mechanism handles this fallback.

## Message Layout

### User Messages
- Seafoam `❯` glyph as left marker
- Subtle Deep Ocean background tint (~8% opacity blend)
- Timestamp in Brine (dimmed)

### Assistant Messages
- Moonlight `◆` glyph as left marker
- No background tint — clean contrast against user messages
- Streaming text renders inline without box borders

### Tool Calls (exec, file edit, MCP)
- Header line: `⟡ shell` / `⟡ edit src/main.rs` / `⟡ mcp:tool_name` in Abyssal
- Content indented below the header
- Thin Abyssal left gutter line (matching code block style) to visually group tool output

**Deferred (v2):** Collapsible tool calls with expand/toggle. This requires adding per-cell focus navigation and toggle state to the chat scroll view, which is a significant feature addition beyond a reskin. For v1, tool calls render fully expanded with the styled header and gutter.

### Turn Separators
- Thin Brine horizontal rule (`─────`) rendered **before each user message** (except the first)
- This visually groups: user prompt → tool calls → assistant response as one block
- No separator between tool calls within a single turn

## Diff Rendering

- Additions: Seafoam text, subtle Seafoam bg (~5% blend)
- Deletions: Coral text, subtle Coral bg (~5% blend)
- Context lines: Pearl text, no background
- Line numbers: Brine, right-aligned
- File path header: Sunken Gold with thin Brine separator line below

## Status Bar

Persistent bottom bar with three zones plus mascot:

```
 ◆ o4-mini │ 12.4k tokens │ suggest mode     ><(((º>  esc: menu │ ctrl+c: stop
 ├── left ──┤──── center ────┤── fish ──┤────── right ──────────┤
```

- **Left:** Model name (Moonlight), collaboration mode
- **Center:** Token count, context usage — live updates during streaming
- **Right:** Contextual keyboard hints (changes based on idle/running/approval state)
- **Fish:** Idle mascot between center and right; replaced by Seafoam spinner when agent is working

Built on existing `footer.rs` layout logic, restyled and extended.

## Fish Mascot

Simple single-line ASCII fish as an idle companion:

```
><(((º>
```

- Single line, ~7 chars wide — fits naturally in the status bar footer
- Lives in the status bar between center info and right-side shortcuts
- Animates subtly: alternates between `><(((º>` and `><((( º>` (tail wiggle), bubble char (` · `) drifts nearby across frames
- Replaced by a Seafoam spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) when agent is working
- Fish reappears when turn completes
- 4-6 idle frames (simple character swaps, no multi-line art)
- Rendered in Seafoam
- Animation state driven by agent activity events, integrated via `status_indicator_widget.rs` / `StatusIndicatorState`
- Uses the existing `ascii_animation.rs` frame system for timing

## Markdown Rendering

Enhances existing `markdown_render.rs`:

### Headers
- `# H1` — Sunken Gold, bold, full-width Brine underline
- `## H2` — Sunken Gold, bold
- `### H3` — Moonlight, bold

### Inline Formatting
- **Bold** — Pearl, bold attribute
- *Italic* — Moonlight, italic attribute
- `inline code` — Abyssal background tint, Pearl text
- Links — Seafoam, underlined

### Code Blocks
- Thin Brine left gutter line (no full box)
- Language label in Brine at top-right
- Syntax highlighting via existing theme system
- Ships "Aquex Deep" as default syntax theme — derived from the palette at implementation time (map keywords→Seafoam, strings→Sunken Gold, comments→Brine, types→Moonlight, etc.). Full token-color mapping defined during implementation, not in this spec.

### Lists
- Bullets: Seafoam `•`
- Numbered: Sunken Gold numbers
- Proper indentation for nested lists

## Branding

- Replace Codex ASCII splash frames in `frames/` with Aquex identity
- Update binary name references where visible in the TUI
- Keep "Powered by Codex" attribution somewhere unobtrusive (e.g., in `/about` or startup log)

## Files Modified

| File | Change |
|------|--------|
| `codex-rs/tui/src/style.rs` | Aquex theme system |
| `codex-rs/tui/src/color.rs` | Palette constants, light/dark adaptation |
| `codex-rs/tui/src/theme_picker.rs` | "Aquex Deep" syntax theme |
| `codex-rs/tui/src/markdown_render.rs` | Enhanced markdown styling |
| `codex-rs/tui/src/diff_render.rs` | Restyled diff colors and layout |
| `codex-rs/tui/src/bottom_pane/footer.rs` | Enhanced status bar |
| `codex-rs/tui/src/history_cell.rs` | Message glyphs and separation |
| `codex-rs/tui/src/chatwidget.rs` | Tool call header/glyph styling |
| `codex-rs/tui/src/chatwidget/` submodules | Tool call rendering (as needed) |
| `codex-rs/tui/src/exec_cell/` | Exec tool call presentation |
| `codex-rs/tui/src/status_indicator_widget.rs` | Fish/spinner integration |
| `codex-rs/tui/src/ascii_animation.rs` | Fish mascot frames + Aquex branding |
| `codex-rs/tui/src/frames.rs` | Register new frame sets |
| `codex-rs/tui/frames/` | New animation frame assets |

## Suggested Implementation Order

Ordered by difficulty (easiest first) to build confidence before harder tasks:

1. **Color palette constants** — pure data in `color.rs`, no logic
2. **Style functions** — swap colors in `style.rs`
3. **Message glyphs and separators** — small rendering changes in `history_cell.rs`
4. **Diff rendering** — color swaps in `diff_render.rs`
5. **Markdown enhancements** — extend existing renderer in `markdown_render.rs`
6. **Status bar restyling** — modify footer layout in `footer.rs`
7. **Branding/splash frames** — asset replacement in `frames/`, update `frames.rs`
8. **Fish mascot animation** — new feature, medium complexity, wire into status indicator

## Reversibility

- Aquex is a separate fork/binary — vanilla Codex remains untouched
- All changes in `codex-rs/tui` only — `git checkout main -- codex-rs/tui` reverts everything
- No core, protocol, or config changes to untangle
