# Update 1.7: Deserto Taara Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Deserto Taara + A Fonte pools (20 fish total), a mutation, 3 new rods, 3 missions, and 1 hunt to deliver Update 1.7.

**Architecture:** All content is data-driven JSON — no Python changes required. Each task creates JSON files and extends the characterization test suite to verify loaders parse them correctly.

**Tech Stack:** Python 3.10+, pytest, JSON content files, existing loaders in `utils/`.

---

## File Map

### New files
```
mutations/arenoso.json
pools/deserto_taara/pool.json
pools/deserto_taara/fish/areia.json
pools/deserto_taara/fish/piramboia_taara.json
pools/deserto_taara/fish/bagre_sedimentar.json
pools/deserto_taara/fish/aruana_sepultado.json
pools/deserto_taara/fish/fossil_errante.json
pools/deserto_taara/fish/saurio_das_dunas.json
pools/deserto_taara/fish/serpente_dunaria.json
pools/deserto_taara/fish/escorpiao_de_ambar.json
pools/deserto_taara/fish/anciao_de_areia.json
pools/deserto_taara/fish/xeique_de_taara.json
pools/a_fonte/pool.json
pools/a_fonte/fish/grilo_dagua.json
pools/a_fonte/fish/peixe_de_copo.json
pools/a_fonte/fish/camarao_aurora.json
pools/a_fonte/fish/borboleta_aquatica.json
pools/a_fonte/fish/lanterna_das_cavernas.json
pools/a_fonte/fish/cego_da_fonte.json
pools/a_fonte/fish/sereia_subterranea.json
pools/a_fonte/fish/anjo_da_fonte.json
pools/a_fonte/fish/guardiao_da_fonte.json
pools/a_fonte/fish/espirito_de_taara.json
missions/unlock_deserto_taara/mission.json
missions/unlock_a_fonte/mission.json
missions/unlock_ouro_fervente_rod/mission.json
rods/ouro_fervente.json
rods/vara_tranquilizante.json
rods/retribuicao.json
crafting/receita_retribuicao/receita_retribuicao.json
hunts/coroa_de_espinhos/hunt.json
```

### Modified files
```
tests/test_mutations_cosmetics_characterization.py  — add Arenoso load test
tests/test_rods_characterization.py                 — add 3 new rod load tests
tests/test_events_hunts_characterization.py         — add Coroa de Espinhos hunt test
tests/test_requirements_characterization.py         — add Retribuição recipe load test
README.md                                           — version bump + 1.7 changelog
```

---

## Task 1: Arenoso Mutation

**Files:**
- Create: `mutations/arenoso.json`
- Modify: `tests/test_mutations_cosmetics_characterization.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_mutations_cosmetics_characterization.py`:

```python
def test_arenoso_mutation_loads_with_correct_fields(tmp_path: Path) -> None:
    mutations_dir = tmp_path / "mutations"
    mutations_dir.mkdir()
    _write_json(
        mutations_dir / "arenoso.json",
        {
            "name": "Arenoso",
            "description": "Grãos de areia se incrustaram entre as escamas ao longo de gerações, criando uma textura áspera e dourada única.",
            "xp_multiplier": 1.1,
            "gold_multiplier": 1.15,
            "chance_percent": 0.22,
        },
    )
    mutations = load_mutations(mutations_dir)
    assert len(mutations) == 1
    assert mutations[0].name == "Arenoso"
    assert mutations[0].chance == pytest.approx(0.0022)
    assert mutations[0].xp_multiplier == pytest.approx(1.1)
    assert mutations[0].gold_multiplier == pytest.approx(1.15)
    assert mutations[0].required_rods == ()
```

Add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_mutations_cosmetics_characterization.py::test_arenoso_mutation_loads_with_correct_fields -v
```

Expected: FAIL (test function not found or AssertionError if the fixture JSON doesn't match)

- [ ] **Step 3: Create `mutations/arenoso.json`**

```json
{
  "name": "Arenoso",
  "description": "Grãos de areia se incrustaram entre as escamas ao longo de gerações, criando uma textura áspera e dourada única.",
  "xp_multiplier": 1.1,
  "gold_multiplier": 1.15,
  "chance_percent": 0.22
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_mutations_cosmetics_characterization.py::test_arenoso_mutation_loads_with_correct_fields -v
```

Expected: PASS

- [ ] **Step 5: Run full suite to check for regressions**

```bash
python -m pytest -q
```

Expected: all existing tests pass

- [ ] **Step 6: Commit**

```bash
git add mutations/arenoso.json tests/test_mutations_cosmetics_characterization.py
git commit -m "content: add Arenoso universal mutation (0.22%, 1.1x XP, 1.15x gold)"
```

---

## Task 2: Deserto Taara Pool and Fish

**Files:**
- Create: `pools/deserto_taara/pool.json` + 10 fish JSONs
- Modify: `tests/test_events_hunts_characterization.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_events_hunts_characterization.py`:

```python
def test_deserto_taara_pool_loads_correct_fish_count(tmp_path: Path) -> None:
    import json as _json
    pool_dir = tmp_path / "deserto_taara"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()

    pool_data = {
        "name": "Deserto Taara",
        "description": "Um leito de mar antigo que secou há milênios. A areia guarda criaturas que se recusam a desaparecer.",
        "unlocked_default": False,
        "rarity_chances": {
            "Comum": 55, "Incomum": 23, "Raro": 14, "Epico": 7, "Lendario": 1
        },
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")

    rarities = [
        ("areia", "Comum"), ("piramboia_taara", "Comum"),
        ("bagre_sedimentar", "Incomum"), ("aruana_sepultado", "Incomum"),
        ("fossil_errante", "Raro"), ("saurio_das_dunas", "Raro"),
        ("serpente_dunaria", "Raro"), ("escorpiao_de_ambar", "Epico"),
        ("anciao_de_areia", "Epico"), ("xeique_de_taara", "Lendario"),
    ]
    for slug, rarity in rarities:
        fish_data = {
            "name": slug, "rarity": rarity, "description": "",
            "kg_min": 1.0, "kg_max": 2.0, "base_value": 10,
            "sequence_len": 4, "reaction_time_s": 2.0,
        }
        (fish_dir / f"{slug}.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    taara = next(p for p in pools if p.name == "Deserto Taara")
    assert len(taara.fish) == 10
    rarities_found = {f.rarity for f in taara.fish}
    assert "Lendario" in rarities_found
    assert "Epico" in rarities_found
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_deserto_taara_pool_loads_correct_fish_count -v
```

Expected: FAIL

- [ ] **Step 3: Create `pools/deserto_taara/pool.json`**

```json
{
  "name": "Deserto Taara",
  "description": "Um leito de mar antigo que secou há milênios. A areia guarda criaturas que se recusam a desaparecer.",
  "unlocked_default": false,
  "rarity_chances": {
    "Comum": 55,
    "Incomum": 23,
    "Raro": 14,
    "Epico": 7,
    "Lendario": 1
  }
}
```

- [ ] **Step 4: Create all 10 fish in `pools/deserto_taara/fish/`**

**`areia.json`**
```json
{
  "name": "Areia",
  "rarity": "Comum",
  "description": "Areia compactada pela pressão das correntes profundas. Não é um peixe, mas aparece nas linhas com frequência incômoda. Indica que o fluxo de areia está ativo naquele ponto.",
  "kg_min": 0.5,
  "kg_max": 3.0,
  "base_value": 2,
  "sequence_len": 3,
  "reaction_time_s": 2.5
}
```

**`piramboia_taara.json`**
```json
{
  "name": "Piramboia de Taara",
  "rarity": "Comum",
  "description": "Um pulmão de peixe adaptado ao ciclo de secas de Taara. Quando a água recua, enterra-se na areia úmida e espera. Quando fisgada, agita o corpo em espirais tensas para se soltar.",
  "kg_min": 0.3,
  "kg_max": 2.0,
  "base_value": 10,
  "sequence_len": 4,
  "reaction_time_s": 2.5
}
```

**`bagre_sedimentar.json`**
```json
{
  "name": "Bagre Sedimentar",
  "rarity": "Incomum",
  "description": "Décadas de exposição aos minerais do deserto cristalizaram camadas sobre sua pele, tornando-a áspera como lixa. Move-se devagar, mas resiste ao anzol com o peso acumulado desses sedimentos.",
  "kg_min": 3.0,
  "kg_max": 7.0,
  "base_value": 26,
  "sequence_len": 5,
  "reaction_time_s": 2.0
}
```

**`aruana_sepultado.json`**
```json
{
  "name": "Aruanã Sepultado",
  "rarity": "Incomum",
  "description": "Uma linhagem de Aruanã que migrou para as correntes subterrâneas de Taara gerações atrás. A ausência de luz clareou suas escamas ao branco e apurou seus reflexos. Quando fisgado, salta com força desproporcional ao corpo.",
  "kg_min": 2.0,
  "kg_max": 6.0,
  "base_value": 30,
  "sequence_len": 5,
  "reaction_time_s": 2.0
}
```

**`fossil_errante.json`**
```json
{
  "name": "Fóssil Errante",
  "rarity": "Raro",
  "description": "Uma criatura cujo metabolismo abrandou ao ponto de suspender o envelhecimento. Suas escamas têm textura calcária, como se já estivesse fossilizado. Resiste ao anzol com uma teimosia silenciosa e constante.",
  "kg_min": 5.0,
  "kg_max": 13.0,
  "base_value": 62,
  "sequence_len": 6,
  "reaction_time_s": 1.5
}
```

**`saurio_das_dunas.json`**
```json
{
  "name": "Saurio das Dunas",
  "rarity": "Raro",
  "description": "Um réptil aquático de escamas largas adaptadas para deslizar sobre areia. Detecta presas pela vibração do substrato e reage com arrancadas curtas e precisas. Na linha, alterna entre resistência passiva e arrancos bruscos.",
  "kg_min": 4.0,
  "kg_max": 10.0,
  "base_value": 65,
  "sequence_len": 6,
  "reaction_time_s": 1.5
}
```

**`serpente_dunaria.json`**
```json
{
  "name": "Serpente Dunária",
  "rarity": "Raro",
  "description": "Uma serpente de escamas que absorvem e irradiam calor. Caça de noite, quando o deserto esfria e suas presas ficam lentas. Suas escamas reagem a certos métodos de pesca com uma intensidade inesperada — como se algo dentro dela fosse ativado.",
  "kg_min": 7.0,
  "kg_max": 16.0,
  "base_value": 75,
  "sequence_len": 7,
  "reaction_time_s": 1.5
}
```

**`escorpiao_de_ambar.json`**
```json
{
  "name": "Escorpião de Âmbar",
  "rarity": "Epico",
  "description": "Preservado em âmbar por tempo incalculável, inexplicavelmente ainda vivo. As patas ainda se movem com precisão mecânica. Quando fisgado, o âmbar ao redor de seu corpo cria resistência lateral intensa.",
  "kg_min": 8.0,
  "kg_max": 20.0,
  "base_value": 95,
  "sequence_len": 7,
  "reaction_time_s": 1.2
}
```

**`anciao_de_areia.json`**
```json
{
  "name": "Ancião de Areia",
  "rarity": "Epico",
  "description": "Uma criatura de porte imenso que habita os canais mais fundos de Taara. Sua idade é estimada pelos minerais incrustados no casco — camadas que levam décadas para se formar. Não foge do anzol.",
  "kg_min": 15.0,
  "kg_max": 35.0,
  "base_value": 100,
  "sequence_len": 8,
  "reaction_time_s": 1.2
}
```

**`xeique_de_taara.json`**
```json
{
  "name": "Xeique de Taara",
  "rarity": "Lendario",
  "description": "O predador dominante do Deserto Taara. Patrulha os corredores subterrâneos com autoridade absoluta, afastando qualquer criatura do seu caminho. A lenda local diz que o deserto obedece a ele. Na linha, dita o ritmo — não o contrário.",
  "kg_min": 50.0,
  "kg_max": 130.0,
  "base_value": 165,
  "sequence_len": 9,
  "reaction_time_s": 0.8
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_deserto_taara_pool_loads_correct_fish_count -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add pools/deserto_taara/ tests/test_events_hunts_characterization.py
git commit -m "content: add Deserto Taara pool with 10 fish"
```

---

## Task 3: A Fonte Pool and Fish

**Files:**
- Create: `pools/a_fonte/pool.json` + 10 fish JSONs
- Modify: `tests/test_events_hunts_characterization.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_events_hunts_characterization.py`:

```python
def test_a_fonte_pool_loads_correct_fish_count(tmp_path: Path) -> None:
    import json as _json
    pool_dir = tmp_path / "a_fonte"
    pool_dir.mkdir()
    fish_dir = pool_dir / "fish"
    fish_dir.mkdir()

    pool_data = {
        "name": "A Fonte",
        "description": "Escondida sob o Deserto Taara, uma nascente subterrânea preserva um ecossistema que o mundo acima desconhece.",
        "unlocked_default": False,
        "rarity_chances": {
            "Comum": 50, "Incomum": 25, "Raro": 16, "Epico": 8, "Lendario": 1
        },
    }
    (pool_dir / "pool.json").write_text(_json.dumps(pool_data), encoding="utf-8")

    rarities = [
        ("grilo_dagua", "Comum"), ("peixe_de_copo", "Comum"),
        ("camarao_aurora", "Incomum"), ("borboleta_aquatica", "Incomum"),
        ("lanterna_das_cavernas", "Raro"), ("cego_da_fonte", "Raro"),
        ("sereia_subterranea", "Raro"), ("anjo_da_fonte", "Epico"),
        ("guardiao_da_fonte", "Epico"), ("espirito_de_taara", "Lendario"),
    ]
    for slug, rarity in rarities:
        fish_data = {
            "name": slug, "rarity": rarity, "description": "",
            "kg_min": 1.0, "kg_max": 2.0, "base_value": 10,
            "sequence_len": 4, "reaction_time_s": 2.0,
        }
        (fish_dir / f"{slug}.json").write_text(_json.dumps(fish_data), encoding="utf-8")

    pools = load_pools(tmp_path)
    fonte = next(p for p in pools if p.name == "A Fonte")
    assert len(fonte.fish) == 10
    rarities_found = {f.rarity for f in fonte.fish}
    assert "Lendario" in rarities_found
    assert "Epico" in rarities_found
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_a_fonte_pool_loads_correct_fish_count -v
```

Expected: FAIL

- [ ] **Step 3: Create `pools/a_fonte/pool.json`**

```json
{
  "name": "A Fonte",
  "description": "Escondida sob o Deserto Taara, uma nascente subterrânea preserva um ecossistema que o mundo acima desconhece.",
  "unlocked_default": false,
  "rarity_chances": {
    "Comum": 50,
    "Incomum": 25,
    "Raro": 16,
    "Epico": 8,
    "Lendario": 1
  }
}
```

- [ ] **Step 4: Create all 10 fish in `pools/a_fonte/fish/`**

**`grilo_dagua.json`**
```json
{
  "name": "Grilo d'Água",
  "rarity": "Comum",
  "description": "Um peixe cujas nadadeiras vibram em frequência audível, criando um som de grilo que ecoa pelas paredes da caverna. Para de soar imediatamente ao sair da água. Não oferece resistência — parece mais curioso do que assustado.",
  "kg_min": 0.1,
  "kg_max": 0.5,
  "base_value": 7,
  "sequence_len": 3,
  "reaction_time_s": 2.5
}
```

**`peixe_de_copo.json`**
```json
{
  "name": "Peixe de Copo",
  "rarity": "Comum",
  "description": "Completamente transparente. Cada órgão interno é visível através da pele como vidro. Evoluiu em A Fonte onde a camuflagem por transparência provou ser mais eficaz que qualquer cor. Quase não resiste ao anzol.",
  "kg_min": 0.2,
  "kg_max": 1.0,
  "base_value": 10,
  "sequence_len": 4,
  "reaction_time_s": 2.5
}
```

**`camarao_aurora.json`**
```json
{
  "name": "Camarão Aurora",
  "rarity": "Incomum",
  "description": "Um camarão cor-de-rosa que filtra os nutrientes da nascente. Grupos formam nuvens que iluminam trechos inteiros da caverna com um brilho suave. Pequeno e fácil de capturar, mas frequentemente confundido à distância com algo maior.",
  "kg_min": 0.3,
  "kg_max": 1.5,
  "base_value": 28,
  "sequence_len": 4,
  "reaction_time_s": 2.0
}
```

**`borboleta_aquatica.json`**
```json
{
  "name": "Borboleta Aquática",
  "rarity": "Incomum",
  "description": "Batizada pelas nadadeiras simétricas que se abrem como asas ao desacelerar. Navega A Fonte por mudanças de pressão na água com precisão quase sobrenatural entre as formações rochosas. Ao ser fisgada, abre as nadadeiras completamente, criando arrasto desproporcional ao tamanho.",
  "kg_min": 1.5,
  "kg_max": 4.5,
  "base_value": 36,
  "sequence_len": 5,
  "reaction_time_s": 2.0
}
```

**`lanterna_das_cavernas.json`**
```json
{
  "name": "Lanterna das Cavernas",
  "rarity": "Raro",
  "description": "Peixe bioluminescente que serve de fonte de luz natural nos trechos mais profundos de A Fonte. Casais sincronizam pulsações para atrair presas. Sob estresse, pulsa em ritmo acelerado — fazendo a caverna piscar.",
  "kg_min": 2.5,
  "kg_max": 7.0,
  "base_value": 62,
  "sequence_len": 5,
  "reaction_time_s": 1.5
}
```

**`cego_da_fonte.json`**
```json
{
  "name": "Cego da Fonte",
  "rarity": "Raro",
  "description": "Sem olhos, navega inteiramente pela pressão da água e campos elétricos imperceptíveis. Gerações em A Fonte tornaram os olhos redundantes. Lento, mas capaz de sentir o anzol antes de tocá-lo — escapando por uma fração de segundo.",
  "kg_min": 3.0,
  "kg_max": 8.0,
  "base_value": 65,
  "sequence_len": 6,
  "reaction_time_s": 1.5
}
```

**`sereia_subterranea.json`**
```json
{
  "name": "Sereia Subterrânea",
  "rarity": "Raro",
  "description": "Comprido, iridescente, e associado às lendas mais antigas sobre A Fonte. Sua vocalização — uma vibração grave sentida mais do que ouvida — ressoa por toda a caverna. Raro o suficiente para que a maioria dos pescadores nunca o veja. Quando fisgado, não luta. Apenas observa.",
  "kg_min": 4.0,
  "kg_max": 11.0,
  "base_value": 70,
  "sequence_len": 6,
  "reaction_time_s": 1.5
}
```

**`anjo_da_fonte.json`**
```json
{
  "name": "Anjo da Fonte",
  "rarity": "Epico",
  "description": "Branco, de nadadeiras semi-transparentes com bordas bioluminescentes que pulsam lentamente. Perfeitamente adaptado à calma de A Fonte, reage a perturbações com um único arranco veloz antes de se estabilizar novamente.",
  "kg_min": 7.0,
  "kg_max": 18.0,
  "base_value": 106,
  "sequence_len": 7,
  "reaction_time_s": 1.2
}
```

**`guardiao_da_fonte.json`**
```json
{
  "name": "Guardião da Fonte",
  "rarity": "Epico",
  "description": "Um peixe de porte grande coberto por placas calcárias acumuladas ao longo de décadas. Mantém posição fixa perto do ponto mais profundo da nascente. Não foge quando fisgado — usa a corrente da fonte como alavanca contra a linha.",
  "kg_min": 14.0,
  "kg_max": 38.0,
  "base_value": 112,
  "sequence_len": 7,
  "reaction_time_s": 1.0
}
```

**`espirito_de_taara.json`**
```json
{
  "name": "Espírito de Taara",
  "rarity": "Lendario",
  "description": "Tão antigo que alguns acreditam que A Fonte se formou ao redor dele, não o contrário. Seu corpo é quase indistinguível da água — visível apenas pela distorção que cria ao se mover. Quando capturado, os pescadores relatam que a água ao redor fica, por um breve instante, completamente imóvel.",
  "kg_min": 22.0,
  "kg_max": 55.0,
  "base_value": 168,
  "sequence_len": 8,
  "reaction_time_s": 0.8
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_a_fonte_pool_loads_correct_fish_count -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add pools/a_fonte/ tests/test_events_hunts_characterization.py
git commit -m "content: add A Fonte pool with 10 fish"
```

---

## Task 4: Mission Chain

**Files:**
- Create: `missions/unlock_deserto_taara/mission.json`
- Create: `missions/unlock_a_fonte/mission.json`
- Create: `missions/unlock_ouro_fervente_rod/mission.json`
- Modify: `tests/test_requirements_characterization.py`

**Chain logic:**
- `unlock_deserto_taara` starts visible (`starts_unlocked: true`), requires level 9 + deliver 1 Arenoso mutation fish. Rewards: unlock Deserto Taara pool + unlock the other two missions.
- `unlock_a_fonte` starts locked, requires 70% Taara bestiary + deliver 2 Arenoso fish. Rewards: unlock A Fonte pool.
- `unlock_ouro_fervente_rod` starts locked, requires deliver Xeique de Taara + deliver Serpente Dunária with Incinerado + earn 5000 gold. Rewards: unlock Ouro Fervente rod.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_requirements_characterization.py`:

```python
def test_unlock_deserto_taara_mission_loads(tmp_path: Path) -> None:
    import json as _json
    mission_dir = tmp_path / "unlock_deserto_taara"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_deserto_taara",
        "name": "Marcas de Areia",
        "description": "Areia voa no ar... de um deserto distante, talvez? Um leito de mar seco que guarda criaturas de outro tempo. Mas o deserto só se abre para quem se entrega a areia.",
        "starts_unlocked": True,
        "requirements": [
            {"type": "level", "level": 9},
            {"type": "deliver_mutation", "count": 1, "mutation_name": "Arenoso"},
        ],
        "rewards": [
            {"type": "unlock_pools", "pool_names": ["Deserto Taara"]},
            {"type": "unlock_missions", "mission_ids": ["unlock_a_fonte", "unlock_ouro_fervente_rod"]},
            {"type": "xp", "amount": 400},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    m = next(x for x in missions if x.mission_id == "unlock_deserto_taara")
    assert m.starts_unlocked is True
    assert any(r.get("type") == "unlock_pools" for r in m.raw_rewards)


def test_unlock_a_fonte_mission_loads(tmp_path: Path) -> None:
    import json as _json
    mission_dir = tmp_path / "unlock_a_fonte"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_a_fonte",
        "name": "Abaixo da Areia",
        "description": "O Deserto Taara esconde algo abaixo dele. Quem conhece bem o deserto consegue ouvir a água.",
        "starts_unlocked": False,
        "requirements": [
            {"type": "bestiary_pool_percent", "pool_name": "Deserto Taara", "percent": 70},
            {"type": "deliver_mutation", "count": 2, "mutation_name": "Arenoso"},
        ],
        "rewards": [
            {"type": "unlock_pools", "pool_names": ["A Fonte"]},
            {"type": "xp", "amount": 500},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    m = next(x for x in missions if x.mission_id == "unlock_a_fonte")
    assert m.starts_unlocked is False
    assert any(r.get("type") == "unlock_pools" for r in m.raw_rewards)


def test_unlock_ouro_fervente_rod_mission_loads(tmp_path: Path) -> None:
    import json as _json
    mission_dir = tmp_path / "unlock_ouro_fervente_rod"
    mission_dir.mkdir()
    payload = {
        "id": "unlock_ouro_fervente_rod",
        "name": "Calor que Forja",
        "description": "No centro do deserto, uma poça de fogo se mantem. Um cetro em seu centro que canaliza a mais pura ganancia por ouro.",
        "starts_unlocked": False,
        "requirements": [
            {"type": "deliver_fish", "count": 1, "fish_name": "Xeique de Taara"},
            {"type": "deliver_fish_with_mutation", "count": 1, "fish_name": "Serpente Dunária", "mutation_name": "Incinerado"},
            {"type": "earn_money", "amount": 5000},
        ],
        "rewards": [
            {"type": "unlock_rods", "rod_names": ["Ouro Fervente"]},
            {"type": "xp", "amount": 800},
        ],
    }
    (mission_dir / "mission.json").write_text(_json.dumps(payload), encoding="utf-8")
    missions = load_missions(tmp_path)
    m = next(x for x in missions if x.mission_id == "unlock_ouro_fervente_rod")
    assert m.starts_unlocked is False
    assert any(r.get("type") == "unlock_rods" for r in m.raw_rewards)
```

Check the existing imports in `tests/test_requirements_characterization.py` and add `load_missions` if not already imported. The function is in `utils.missions`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_requirements_characterization.py::test_unlock_deserto_taara_mission_loads tests/test_requirements_characterization.py::test_unlock_a_fonte_mission_loads tests/test_requirements_characterization.py::test_unlock_ouro_fervente_rod_mission_loads -v
```

Expected: FAIL

- [ ] **Step 3: Create `missions/unlock_deserto_taara/mission.json`**

```json
{
  "id": "unlock_deserto_taara",
  "name": "Marcas de Areia",
  "description": "Boatos de um deserto antigo chegam até você. Um leito de mar seco que guarda criaturas de outro tempo. Mas o deserto só se abre para quem carrega sua marca.",
  "starts_unlocked": true,
  "requirements": [
    {
      "type": "level",
      "level": 9
    },
    {
      "type": "deliver_mutation",
      "count": 1,
      "mutation_name": "Arenoso"
    }
  ],
  "rewards": [
    {
      "type": "unlock_pools",
      "pool_names": ["Deserto Taara"]
    },
    {
      "type": "unlock_missions",
      "mission_ids": ["unlock_a_fonte", "unlock_ouro_fervente_rod"]
    },
    {
      "type": "xp",
      "amount": 400
    }
  ]
}
```

- [ ] **Step 4: Create `missions/unlock_a_fonte/mission.json`**

```json
{
  "id": "unlock_a_fonte",
  "name": "Abaixo da Areia",
  "description": "O Deserto Taara esconde algo abaixo dele. Dizem que quem conhece bem o deserto consegue ouvir a água.",
  "starts_unlocked": false,
  "requirements": [
    {
      "type": "bestiary_pool_percent",
      "pool_name": "Deserto Taara",
      "percent": 70
    },
    {
      "type": "deliver_mutation",
      "count": 2,
      "mutation_name": "Arenoso"
    }
  ],
  "rewards": [
    {
      "type": "unlock_pools",
      "pool_names": ["A Fonte"]
    },
    {
      "type": "xp",
      "amount": 500
    }
  ]
}
```

- [ ] **Step 5: Create `missions/unlock_ouro_fervente_rod/mission.json`**

```json
{
  "id": "unlock_ouro_fervente_rod",
  "name": "Calor que Forja",
  "description": "Algo no coração de Taara guarda uma vara. Ela só pode ser alcançada por quem já dominou o que o deserto tem de mais duro.",
  "starts_unlocked": false,
  "requirements": [
    {
      "type": "deliver_fish",
      "count": 1,
      "fish_name": "Xeique de Taara"
    },
    {
      "type": "deliver_fish_with_mutation",
      "count": 1,
      "fish_name": "Serpente Dunária",
      "mutation_name": "Incinerado"
    },
    {
      "type": "earn_money",
      "amount": 5000
    }
  ],
  "rewards": [
    {
      "type": "unlock_rods",
      "rod_names": ["Ouro Fervente"]
    },
    {
      "type": "xp",
      "amount": 800
    }
  ]
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_requirements_characterization.py::test_unlock_deserto_taara_mission_loads tests/test_requirements_characterization.py::test_unlock_a_fonte_mission_loads tests/test_requirements_characterization.py::test_unlock_ouro_fervente_rod_mission_loads -v
```

Expected: all PASS

- [ ] **Step 7: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add missions/unlock_deserto_taara/ missions/unlock_a_fonte/ missions/unlock_ouro_fervente_rod/ tests/test_requirements_characterization.py
git commit -m "content: add Taara, A Fonte, and Ouro Fervente unlock mission chain"
```

---

## Task 5: Ouro Fervente Rod

**Files:**
- Create: `rods/ouro_fervente.json`
- Modify: `tests/test_rods_characterization.py`

Stats: `luck 0.38`, `kg_max 500.0`, `control -0.10`. `can_alter`: `timecount -25` (−25% time), `hardcount 50` (+50% keys). `can_greed`: `greed_chance 0.18`. Unlocked via mission — starts locked, no price, `unlocked_default: false`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_rods_characterization.py`:

```python
def test_ouro_fervente_rod_loads_alter_and_greed(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "ouro_fervente.json",
        {
            "name": "Ouro Fervente",
            "luck": 0.38,
            "kg_max": 500.0,
            "control": -0.10,
            "description": "A forja do deserto transforma os peixes em seu anzol no mais puro desejo dourado. Pode puxa-los?",
            "price": 0,
            "unlocked_default": False,
            "can_alter": True,
            "timecount": -15,
            "hardcount": 30,
            "can_greed": True,
            "greed_chance": 0.18,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Ouro Fervente"
    assert rod.can_alter is True
    assert rod.timecount == pytest.approx(-25.0)
    assert rod.hardcount == pytest.approx(50.0)
    assert rod.can_greed is True
    assert rod.greed_chance == pytest.approx(0.18)
```

Add `import pytest` if not already present.

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_rods_characterization.py::test_ouro_fervente_rod_loads_alter_and_greed -v
```

Expected: FAIL

- [ ] **Step 3: Create `rods/ouro_fervente.json`**

```json
{
  "name": "Ouro Fervente",
  "luck": 0.38,
  "kg_max": 500.0,
  "control": -0.10,
  "description": "A forja do deserto transforma os peixes em seu anzol no mais puro desejo dourado. Pode puxa-los?",
  "price": 0,
  "unlocked_default": false,
  "can_alter": true,
  "timecount": -25,
  "hardcount": 50,
  "can_greed": true,
  "greed_chance": 0.18
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_rods_characterization.py::test_ouro_fervente_rod_loads_alter_and_greed -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add rods/ouro_fervente.json tests/test_rods_characterization.py
git commit -m "content: add Ouro Fervente rod (alter -25t/+50k, greed 18%)"
```

---

## Task 6: Vara Tranquilizante and Retribuição Rods

**Files:**
- Create: `rods/vara_tranquilizante.json`
- Create: `rods/retribuicao.json`
- Modify: `tests/test_rods_characterization.py`

**Vara Tranquilizante:** `luck 0.20`, `kg_max 130.0`, `control 0.35`, `can_alter timecount +60 hardcount +20`, price 7500, `unlockswithpool: "A Fonte"`.

**Retribuição:** `luck 0.04`, `kg_max 18.0`, `control -0.35`, 4 abilities: `can_slash` (0.22, power 1), `can_dupe` (0.13), `can_greed` (0.13), `can_pierce` (0.20). devcoffe tribute: `unlockswithpool: "Cafeteria"`, `counts_for_bestiary_completion: false`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rods_characterization.py`:

```python
def test_vara_tranquilizante_loads_alter_fields(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "vara_tranquilizante.json",
        {
            "name": "Vara Tranquilizante",
            "luck": 0.20,
            "kg_max": 130.0,
            "control": 0.35,
            "description": "A nascente acalma até os peixes mais agitados. E também quem a segura.",
            "price": 7500,
            "unlocked_default": False,
            "unlockswithpool": "A Fonte",
            "can_alter": True,
            "timecount": 60,
            "hardcount": 20,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Vara Tranquilizante"
    assert rod.can_alter is True
    assert rod.timecount == pytest.approx(60.0)
    assert rod.hardcount == pytest.approx(20.0)
    assert rod.unlocks_with_pool == "A Fonte"


def test_retribuicao_loads_four_abilities(tmp_path: Path) -> None:
    _write_rod(
        tmp_path,
        "retribuicao.json",
        {
            "name": "Retribuição",
            "luck": 0.04,
            "kg_max": 250.0,
            "control": -0.1,
            "description": "Retribuição deve ser espalhada!",
            "price": 0,
            "unlocked_default": False,
            "unlockswithpool": "Cafeteria",
            "counts_for_bestiary_completion": False,
            "can_slash": True,
            "slash_chance": 0.22,
            "slash_power": 1,
            "can_dupe": True,
            "dupe_chance": 0.13,
            "can_greed": True,
            "greed_chance": 0.13,
            "can_pierce": True,
            "pierce_chance": 0.20,
        },
    )
    rod = load_rods(tmp_path)[0]
    assert rod.name == "Retribuição"
    assert rod.can_slash is True
    assert rod.slash_chance == pytest.approx(0.22)
    assert rod.can_dupe is True
    assert rod.dupe_chance == pytest.approx(0.13)
    assert rod.can_greed is True
    assert rod.greed_chance == pytest.approx(0.13)
    assert rod.can_pierce is True
    assert rod.pierce_chance == pytest.approx(0.20)
    assert rod.counts_for_bestiary_completion is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_rods_characterization.py::test_vara_tranquilizante_loads_alter_fields tests/test_rods_characterization.py::test_retribuicao_loads_four_abilities -v
```

Expected: FAIL

- [ ] **Step 3: Create `rods/vara_tranquilizante.json`**

```json
{
  "name": "Vara Tranquilizante",
  "luck": 0.20,
  "kg_max": 130.0,
  "control": 0.35,
  "description": "A nascente acalma até os peixes mais agitados. E também quem a segura.",
  "price": 7500,
  "unlocked_default": false,
  "unlockswithpool": "A Fonte",
  "can_alter": true,
  "timecount": 60,
  "hardcount": 20
}
```

- [ ] **Step 4: Create `rods/retribuicao.json`**

```json
{
  "name": "Retribuição",
  "luck": 0.04,
  "kg_max": 250.0,
  "control": -0.1,
  "description": "Retribuição deve ser espalhada!",
  "price": 0,
  "unlocked_default": false,
  "unlockswithpool": "Cafeteria",
  "counts_for_bestiary_completion": false,
  "can_slash": true,
  "slash_chance": 0.22,
  "slash_power": 1,
  "can_dupe": true,
  "dupe_chance": 0.13,
  "can_greed": true,
  "greed_chance": 0.13,
  "can_pierce": true,
  "pierce_chance": 0.20
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_rods_characterization.py::test_vara_tranquilizante_loads_alter_fields tests/test_rods_characterization.py::test_retribuicao_loads_four_abilities -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add rods/vara_tranquilizante.json rods/retribuicao.json tests/test_rods_characterization.py
git commit -m "content: add Vara Tranquilizante and Retribuicao rods"
```

---

## Task 7: Retribuição Crafting Recipe

**Files:**
- Create: `crafting/receita_retribuicao/receita_retribuicao.json`
- Modify: `tests/test_requirements_characterization.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_requirements_characterization.py`:

```python
def test_retribuicao_crafting_recipe_loads_correctly(tmp_path: Path) -> None:
    import json as _json
    from utils.crafting import load_crafting_definitions

    craft_dir = tmp_path / "receita_retribuicao"
    craft_dir.mkdir()
    (craft_dir / "receita_retribuicao.json").write_text(
        _json.dumps({
            "id": "retribuicao_craft",
            "rod_name": "Retribuição",
            "name": "As Quatro Formas",
            "description": "Cada fragmento carrega uma punição diferente. Reúna-os e espalhe a retribuição.",
            "unlock": {
                "mode": "all",
                "requirements": [
                    {"type": "unlock_pool", "pool_name": "Cafeteria"},
                ],
            },
            "craft": {
                "requirements": [
                    {"type": "fish_with_mutation", "fish_name": "Gladio Escaldante", "mutation_name": "Carmesim", "count": 1},
                    {"type": "fish_with_mutation", "fish_name": "Peixe Tres-Olhos", "mutation_name": "Espiral", "count": 1},
                    {"type": "fish_with_mutation", "fish_name": "Lagosta Cristal", "mutation_name": "Cristalizado", "count": 1},
                    {"type": "fish_with_mutation", "fish_name": "Enguia Ancia", "mutation_name": "Profundo", "count": 1},
                    {"type": "fish", "fish_name": "Cafe", "count": 1},
                ],
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    defs = load_crafting_definitions(tmp_path)
    assert len(defs) == 1
    d = defs[0]
    assert d.rod_name == "Retribuição"
    assert d.id == "retribuicao_craft"
    fish_names = {r.fish_name for r in d.craft_requirements if hasattr(r, "fish_name")}
    assert "Cafe" in fish_names
    assert len(d.craft_requirements) == 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_requirements_characterization.py::test_retribuicao_crafting_recipe_loads_correctly -v
```

Expected: FAIL

- [ ] **Step 3: Create `crafting/receita_retribuicao/receita_retribuicao.json`**

```json
{
  "id": "retribuicao_craft",
  "rod_name": "Retribuição",
  "name": "As Quatro Formas",
  "description": "Cada fragmento carrega uma punição diferente. Reúna-os e espalhe a retribuição.",
  "unlock": {
    "mode": "all",
    "requirements": [
      {
        "type": "unlock_pool",
        "pool_name": "Cafeteria"
      }
    ]
  },
  "craft": {
    "requirements": [
      {
        "type": "fish_with_mutation",
        "fish_name": "Gladio Escaldante",
        "mutation_name": "Carmesim",
        "count": 1
      },
      {
        "type": "fish_with_mutation",
        "fish_name": "Peixe Tres-Olhos",
        "mutation_name": "Espiral",
        "count": 1
      },
      {
        "type": "fish_with_mutation",
        "fish_name": "Lagosta Cristal",
        "mutation_name": "Cristalizado",
        "count": 1
      },
      {
        "type": "fish_with_mutation",
        "fish_name": "Enguia Ancia",
        "mutation_name": "Profundo",
        "count": 1
      },
      {
        "type": "fish",
        "fish_name": "Cafe",
        "count": 1
      }
    ]
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_requirements_characterization.py::test_retribuicao_crafting_recipe_loads_correctly -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add crafting/receita_retribuicao/ tests/test_requirements_characterization.py
git commit -m "content: add Retribuicao crafting recipe"
```

---

## Task 8: GrandReef Hunt — Coroa de Espinhos

**Files:**
- Create: `hunts/coroa_de_espinhos/hunt.json`
- Modify: `tests/test_events_hunts_characterization.py`

The Crown-of-Thorns starfish is a real-world coral reef predator — fitting thematically. Moderate decay (the reef is large), boosts Epic/Legendary, 6-minute window, 10-minute cooldown.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_events_hunts_characterization.py`:

```python
def test_coroa_de_espinhos_hunt_loads_for_grandreef(tmp_path: Path) -> None:
    import json as _json
    hunt_dir = tmp_path / "coroa_de_espinhos"
    hunt_dir.mkdir()
    payload = {
        "name": "Coroa de Espinhos",
        "description": "Uma forma estrelada de proporções absurdas avança pelo recife. Cada coral que toca desaparece. O recife está em silêncio.",
        "pool_name": "Grande Recife",
        "duration_minutes": 6,
        "check_interval_seconds": 60,
        "disturbance_per_catch": 2,
        "disturbance_max": 1800,
        "rarity_chances": {"Epico": 6, "Lendario": 4},
        "cooldown_minutes": 10,
        "disturbance_decay_per_check": 3,
    }
    (hunt_dir / "hunt.json").write_text(_json.dumps(payload), encoding="utf-8")
    hunts = load_hunts(tmp_path)
    h = next(x for x in hunts if x.name == "Coroa de Espinhos")
    assert h.pool_name == "Grande Recife"
    assert h.rarity_weights.get("Lendario", 0) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_coroa_de_espinhos_hunt_loads_for_grandreef -v
```

Expected: FAIL

- [ ] **Step 3: Create `hunts/coroa_de_espinhos/hunt.json`**

```json
{
  "name": "Coroa de Espinhos",
  "description": "Uma forma estrelada de proporções absurdas avança pelo recife. Cada coral que toca desaparece. O recife está em silêncio.",
  "pool_name": "Grande Recife",
  "duration_minutes": 6,
  "check_interval_seconds": 60,
  "disturbance_per_catch": 2,
  "disturbance_max": 1800,
  "rarity_chances": {
    "Epico": 6,
    "Lendario": 4
  },
  "cooldown_minutes": 10,
  "disturbance_decay_per_check": 3
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_events_hunts_characterization.py::test_coroa_de_espinhos_hunt_loads_for_grandreef -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add hunts/coroa_de_espinhos/ tests/test_events_hunts_characterization.py
git commit -m "content: add Coroa de Espinhos hunt to Grande Recife"
```

---

## Task 9: README — Update 1.7 Changelog

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update version and add changelog block**

In `README.md`, change `Versao atual: \`1.6\`` to `Versao atual: \`1.7\`` and add the following block above `### Update 1.6`:

```markdown
### Update 1.7: Deserto Taara

- Nova pool desbloqueavel: `Deserto Taara`, com 10 peixes e acesso por level 9 + mutação `Arenoso`.
- Nova sub-pool: `A Fonte`, oásis subterrâneo desbloqueado dentro de Taara.
- Nova mutação universal: `Arenoso` (0.22%, +1.1x XP, +1.15x gold).
- 2 novas varas com `can_alter`:
  - `Ouro Fervente` — sequências longas, tempo reduzido, alto retorno econômico. Desbloqueada por missão.
  - `Vara Tranquilizante` — mais tempo, leve aumento de teclas. Comprada em A Fonte.
- Nova vara tributo adicionada à Cafeteria:
  - `Retribuição` — homenagem aos jogadores. Stats ruins, 4 habilidades: Slash, Dupe, Greed e Pierce.
- Nova hunt: `Coroa de Espinhos`, uma estrela-do-mar colossal invade o Grande Recife.
- 3 novas missões encadeadas: `Marcas de Areia`, `Abaixo da Areia`, `Calor que Forja`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for version 1.7 Deserto Taara"
```

---

## Self-Review

**Spec coverage:**
| Requirement | Task |
|---|---|
| Arenoso mutation (0.22%, +1.1x XP, +1.15x gold) | Task 1 |
| Deserto Taara pool + 10 fish | Task 2 |
| A Fonte pool + 10 fish | Task 3 |
| Taara unlock mission (level 9 + Arenoso) | Task 4 |
| A Fonte unlock mission (70% Taara + 2 Arenoso) | Task 4 |
| Ouro Fervente rod unlock mission (Legendary + Incinerado fish + earn 5000) | Task 4 |
| Ouro Fervente rod (can_alter -25t/+50k, can_greed 18%) | Task 5 |
| Vara Tranquilizante rod (can_alter +60t/+20k, buyable at A Fonte) | Task 6 |
| Retribuição rod (4 abilities, devcoffe tribute) | Task 6 |
| Retribuição crafting recipe (As Quatro Formas) | Task 7 |
| Coroa de Espinhos GrandReef hunt | Task 8 |
| README 1.7 changelog | Task 9 |

**Gaps found and resolved:** Retribuição crafting recipe was missing from the original plan — added as Task 7. All 12 spec items are now covered.

**Placeholder scan:** No TBDs, TODOs, or vague steps found.

**Type consistency:** `load_missions` used in Task 4 tests — verify this function exists in `utils.missions` and is exported before running. The existing test file `test_requirements_characterization.py` likely already imports it; confirm the import is present or add it.
