"""Dice expressions and roll probabilities.

Characteristics are stored as text because that is how the source holds them:
attacks may be `4`, `D6`, `2D6+1`; damage `3` or `D6+2`; skill `3+`. Nothing
downstream can do arithmetic until this module turns them into numbers.
"""
import re

DICE = re.compile(r"^\s*(\d*)\s*[dD]\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$")
FLAT = re.compile(r"^\s*(\d+)\s*$")
TARGET = re.compile(r"^\s*(\d)\s*\+?\s*$")


def expected(expression, default=0.0):
    """Average value of `4`, `D6`, `2D6+1`. Returns `default` for `*` or junk.

    `*` appears on weapons whose value is set by a rule the data does not
    carry, so there is nothing honest to compute.
    """
    if expression is None:
        return default
    text = str(expression).strip()
    flat = FLAT.match(text)
    if flat:
        return float(flat.group(1))
    roll = DICE.match(text)
    if not roll:
        return default
    count = int(roll.group(1) or 1)
    sides = int(roll.group(2))
    modifier = int(roll.group(4) or 0)
    if roll.group(3) == "-":
        modifier = -modifier
    return count * (sides + 1) / 2 + modifier


def expected_capped(expression, cap, default=1.0):
    """Average of the expression with each outcome capped at `cap`.

    Damage does not carry over between models in a unit, so a D6+2 weapon into
    one-wound models wastes most of its roll. Capping the average would be
    wrong for dice: E[min(D6,3)] is 2.5, not min(3.5,3).
    """
    text = str(expression or "").strip()
    roll = DICE.match(text)
    if not roll:
        return min(expected(expression, default), cap)
    count = int(roll.group(1) or 1)
    sides = int(roll.group(2))
    modifier = int(roll.group(4) or 0)
    if roll.group(3) == "-":
        modifier = -modifier
    outcomes = [modifier]
    for _ in range(count):
        outcomes = [total + face for total in outcomes for face in range(1, sides + 1)]
    return sum(min(value, cap) for value in outcomes) / len(outcomes)


def is_variable(expression):
    """True when the value is a die roll rather than a fixed number."""
    return bool(DICE.match(str(expression or "").strip()))


def target_number(expression, default=None):
    """`3+` or `3` -> 3. `N/A` and blanks -> `default` (weapons that auto-hit)."""
    match = TARGET.match(str(expression or ""))
    return int(match.group(1)) if match else default


def success(target, modifier=0):
    """Probability of rolling `target`+ on a d6, with a hit/wound modifier.

    A natural 1 always fails and a natural 6 always succeeds, and modifiers are
    capped at ±1, as the core rules require.
    """
    if target is None:
        return 1.0
    adjusted = target - max(-1, min(1, modifier))
    adjusted = max(2, min(6, adjusted))
    return (7 - adjusted) / 6


def reroll_failures(probability):
    """Probability after rerolling a failed roll once (twin-linked, rerolls)."""
    return probability + (1 - probability) * probability


def wound_target(strength, toughness):
    """The 40k wound chart, as a target number."""
    if strength >= toughness * 2:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if strength * 2 <= toughness:
        return 6
    return 5
