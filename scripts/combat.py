"""Expected damage of a weapon against a target profile.

What this models: hit and wound rolls with the ±1 cap, armour and invulnerable
saves, and the weapon abilities that actually change the arithmetic — Torrent,
Twin-linked, Sustained Hits, Lethal Hits, Devastating Wounds, Anti-X, Melta,
Rapid Fire, Blast, Heavy and Lance. Damage is capped per model, since it does
not carry over.

What it does NOT model, and why the numbers are a comparison tool rather than a
prediction: Feel No Pain, cover, stratagems, reroll auras, army and detachment
rules, damage spilling within a unit, and the sequencing of mortal wounds.
Ignoring these consistently keeps weapons comparable with each other; it does
not make any single figure a forecast of a real game.
"""
import re

import dice

MODIFIER_KEYWORD = re.compile(r"^(.*?)\s+(\d)\+?$")


def parse_keywords(text):
    """'Sustained Hits 2, Anti-Infantry 4+' -> {'sustained hits': 2, 'anti-infantry': 4}.

    Lower-cased because the source is inconsistent: both 'Twin-linked' and
    'Twin-Linked' occur, as do 'Anti-Infantry' and 'Anti-INFANTRY'.
    """
    found = {}
    for part in re.split(r",\s*", text or ""):
        part = part.strip()
        if not part:
            continue
        match = MODIFIER_KEYWORD.match(part)
        if match:
            found[match.group(1).strip().lower()] = int(match.group(2))
        else:
            found[part.lower()] = True
    return found


def armour_penetration(value):
    text = str(value or "").strip()
    match = re.search(r"-?\d+", text)
    return abs(int(match.group())) if match else 0


def save_probability(save, ap, invulnerable=None):
    """Chance the target saves, taking the better of armour and invulnerable."""
    armour = save + ap
    best = armour if invulnerable is None else min(armour, invulnerable)
    if best > 6:
        return 0.0
    return (7 - max(2, best)) / 6


def critical_wound_target(keywords, target_keywords):
    """Anti-X N+ lowers the critical wound threshold against matching keywords."""
    threshold = 6
    lowered = {k.lower() for k in target_keywords or ()}
    for key, value in keywords.items():
        if key.startswith("anti-") and isinstance(value, int) and key[5:] in lowered:
            threshold = min(threshold, value)
    return threshold


def expected_damage(weapon, target, context=None):
    """Average damage one weapon profile deals to one target model profile."""
    context = {"half_range": False, "stationary": True, "charged": False,
               "target_models": 5, **(context or {})}
    keywords = parse_keywords(weapon.get("keywords"))

    attacks = dice.expected(weapon.get("attacks"), default=0.0)
    if "blast" in keywords:
        attacks += context["target_models"] // 5
    if "rapid fire" in keywords and context["half_range"]:
        attacks += keywords["rapid fire"]
    if attacks <= 0:
        return 0.0

    strength = dice.expected(weapon.get("strength"), default=0.0)
    if strength <= 0:                       # '*': set by a rule the data lacks
        return 0.0

    # --- hits -------------------------------------------------------------
    skill = dice.target_number(weapon.get("skill"))
    if "torrent" in keywords or skill is None:
        hits_normal, hits_critical = attacks, 0.0
    else:
        modifier = 1 if ("heavy" in keywords and context["stationary"]) else 0
        probability = dice.success(skill, modifier)
        critical = min(1 / 6, probability)
        hits_critical = attacks * critical
        hits_normal = attacks * (probability - critical)
    if "sustained hits" in keywords:
        hits_normal += hits_critical * keywords["sustained hits"]

    # --- wounds -----------------------------------------------------------
    modifier = 1 if ("lance" in keywords and context["charged"]) else 0
    base = dice.success(dice.wound_target(strength, target["t"]), modifier)
    critical_target = critical_wound_target(keywords, target.get("keywords"))
    critical = dice.success(critical_target)
    if "twin-linked" in keywords:
        critical = critical + (1 - base) * critical
        base = dice.reroll_failures(base)
    critical = min(critical, base)

    lethal = "lethal hits" in keywords
    rolled = hits_normal + (0.0 if lethal else hits_critical)
    wounds_critical = rolled * critical
    wounds_normal = rolled * (base - critical) + (hits_critical if lethal else 0.0)

    # --- saves and damage -------------------------------------------------
    saved = save_probability(target["sv"], armour_penetration(weapon.get("ap")),
                             target.get("invuln"))
    through = 1 - saved

    damage = weapon.get("damage")
    if "melta" in keywords and context["half_range"]:
        damage = f"{damage}+{keywords['melta']}"
    per_wound = dice.expected_capped(damage, target.get("w", 1))

    if "devastating wounds" in keywords:
        unsaved = wounds_normal * through + wounds_critical
    else:
        unsaved = (wounds_normal + wounds_critical) * through
    return unsaved * per_wound
