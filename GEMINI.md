# GEMINI.md - Fisching Overhaul

## Project Overview
**Fisching Overhaul** is a text-based, highly expandable fishing game built with Python. It features a data-driven architecture where game content (pools, fish, rods, baits, events, and missions) is defined using JSON files, making it easy to add new content without modifying the core engine.

### Core Technologies
- **Python 3.10+**
- **colorama**: For terminal styling and colors.
- **pynput**: For real-time, non-blocking keyboard input (QTE sequences).
- **JSON**: Used for all game data definitions.

### Key Directories
- `utils/`: Core game logic and system managers (fishing engine, save system, UI, etc.).
- `pools/`: Fishing locations, each with its own `pool.json` and `fish/` subdirectory.
- `rods/`: Fishing rod definitions.
- `baits/`: Bait crate and individual bait definitions.
- `mutations/`: Fish mutations that affect value and XP.
- `events/` & `hunts/`: Dynamic world events and special fishing "hunts".
- `missions/`: Quest and mission definitions.
- `tests/`: Characterization tests using `pytest`.

---

## Gameplay Mechanics

### 1. Rarity and XP Scaling
The game uses a tiered rarity system that determines both the selling price of the fish and the XP gained.
- **Rarity Tiers:** `Comum`, `Incomum`, `Raro`, `Epico`, `Lendario`.
- **XP per Catch:** Defined in `utils/levels.py` (e.g., Comum: 10, Lendário: 100).
- **Leveling:** Requirement grows exponentially (Base: 100 XP, Growth: 1.35x).

### 2. Equipment Stats
Rods and Baits have three primary stats that influence the fishing mini-game:
- **Luck:** Increases the chance of catching rarer fish by shifting the probability weights.
- **Control:** Grants bonus time (seconds) to complete the QTE sequence.
- **Weight (KG Max/Plus):** Rods have a maximum weight limit, while baits can provide a weight boost.

Special Rod Abilities:
- **Slash:** Chance to instantly remove keys from the sequence or catch the fish.
- **Slam:** Chance to gain bonus time during the catch.

### 3. Mutations
Fish have a chance to spawn with mutations (defined in `mutations/`). 
- Mutations provide **multipliers** for both XP and Gold (e.g., `Albino`, `Noir`, `Solar`).
- Some mutations are **rod-specific**, meaning they only appear if a certain rod is equipped.

### 4. Dynamic World Events & Hunts
- **Events:** Global modifiers that last for a set duration (e.g., `Eclipse Solar`, `Tempestade Arcana`). They can increase luck, XP, and introduce event-exclusive fish and mutations.
- **Hunts:** Pool-specific occurrences triggered by "disturbance" (increased by catching fish). High disturbance triggers a hunt with unique, high-value fish.

---

## Content Organization & Progression

### 1. Item Structure (Rods & Baits)
Items are developed with a clear progression path, moving from general-use equipment to highly specialized tools.
- **Naming:** Follows a thematic progression. Starting with basic materials (`Bambu`, `Plástico`), moving to performance materials (`Carbono`, `Fibra`), and ending with mythical/elemental themes (`Kraken`, `Eclipse`, `Sniper`).
- **Descriptions:** Reflect the item's "flavor" and mechanical niche. 
    - *Example:* The **Vara de Bambu** is described as "Leve e simples," while the **Vara do Kraken** "canaliza a energia dos tentáculos... para imobilizar os peixes."
- **Stat Scaling:**
    - **Early Game:** High control (bonus time) but very low weight capacity (`KG Max`).
    - **Mid Game:** Focus on specialized stats like high weight capacity (`Vara de Carbono`) or specific elemental resistances.
    - **End Game:** Introduction of unique abilities like `can_slam` (bonus time on hit) or `can_slash` (removing QTE keys), paired with high luck and extreme weight limits.

### 2. Difficulty & Gating Mechanisms
The game controls the player's pace through several interconnected systems:
- **Location Gating:** New fishing pools are unlocked via **Missions** (e.g., `unlock_grandreef`). Unlocking a pool often acts as a prerequisite for finding the fish needed for the next tier of equipment.
- **Crafting Recipes:** Advanced rods are not bought; they are built. 
    - **Unlock Logic:** A recipe (like `receita_vara_kraken`) remains hidden until a trigger occurs, such as catching a specific boss fish (`Lula Gigante`).
    - **Material Costs:** Requires a combination of high-rarity fish (testing the player's luck/skill), bulk common fish (testing persistence), and large sums of gold.
- **Mission Progression:** Missions serve as the primary tutorial and progression guide. Early missions teach basic mechanics (selling fish), while later missions reward the player with **Rod Unlocks** and **New Pool Access**, directly increasing the game's complexity.

### 3. Data Organization
- **Thematic Folders:** Content is grouped by its function (e.g., `baits/cheap_bait_crate/` contains its own definition and its drop pool).
- **Extensible Schema:** Every JSON file follows a consistent structure, allowing the game engine to interpret difficulty (e.g., `reaction_time_s` in fish profiles) and rewards dynamically.

---

## Building and Running

### Installation
To install in development mode:
```bash
pip install -e .
```

### Running the Game
Using the installed command:
```bash
fisching
```
Or directly via Python:
```bash
python start_game.py
```

### Running Tests
```bash
pytest
```

---

## Development Conventions

### 1. Data-Driven Content
All content should be added via JSON files in the appropriate directories.
- **New Fish:** Add a `.json` file to `pools/<pool_name>/fish/`.
- **New Pool:** Create a new directory in `pools/` with a `pool.json` and a `fish/` folder.
- **New Rod:** Add a `.json` file to `rods/`.

### 2. Fishing Engine Logic
The core fishing loop is managed by `FishingMiniGame` in `utils/pesca.py`. It uses a sequence of keys (`w`, `a`, `s`, `d` by default) that the player must press within a time limit.

### 3. Save System
Progress is stored in `savegame.json` in the project root. The save format is managed by `utils/save_system.py`.

### 4. UI Standards
The game supports two UI modes:
- **Simple UI**: Standard terminal output.
- **Modern UI**: A more polished, panel-based interface (controlled by `utils/modern_ui.py`).
- **Cosmetics**: Players can unlock UI colors and icons, defined in `cosmetics_catalog/`.

### 5. Expandability Checklist
When adding new content, ensure:
- JSON files are valid and follow the expected schema.
- Rarity strings match those used in `utils/levels.py`.
- New pools or rods are linked to mission rewards or set to `unlocked_default` if necessary.

### 6. Development Tools
The game includes a **Dev Tools** menu (accessible via `7` in the main menu when in dev mode) to modify the save state, unlock content, and test events.
