"""Shared name normalisation.

BSData, the Munitorum Field Manual and whatever a human types disagree on
punctuation, capitalisation and plurals. Every lookup goes through here so all
three agree on what counts as the same name.
"""
import re


def norm(text):
    """Strip everything but letters and digits, lowercased."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def name_keys(name):
    """Singular and plural variants: the MFM alternates against BSData."""
    base = norm(name)
    return (base, base + "s", base.rstrip("s"))
