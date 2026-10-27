"""Tiny translation layer: tr("English text") returns the Dutch text when the UI language is Dutch.

The language is read once at start-up (Settings → Appearance; restart to apply). Strings without a translation
stay English, so adding translations is safe and incremental: just add entries to NL below.
"""
from __future__ import annotations

from ..core.paths import ui_prefs

LANG = ui_prefs().get("lang", "en")
if LANG not in ("en", "nl"):
    LANG = "en"

NL = {
    # navigation
    "Tracker": "Tracker", "Pull History": "Pull-geschiedenis", "Probability": "Kansen", "Planner": "Planner",
    "Collection": "Collectie", "Calendar": "Kalender", "Prydwen": "Prydwen", "Simulator": "Simulator",
    "Codes": "Codes", "AI": "AI", "Settings": "Instellingen",
    # menu
    "Data": "Gegevens", "Import wuwatracker JSON…": "wuwatracker-JSON importeren…",
    "Import from game…": "Importeren uit de game…", "Export…": "Exporteren…",
    "Export wuwatracker JSON…": "wuwatracker-JSON exporteren…", "Export CSV…": "CSV exporteren…",
    "Export Excel…": "Excel exporteren…", "Compare with a wuwatracker export…": "Vergelijken met een wuwatracker-export…",
    "Backups…": "Back-ups…", "Delete this account's data…": "Gegevens van dit account verwijderen…",
    "Game data": "Gamegegevens", "Check for game data updates": "Gamegegevens bijwerken",
    "Classify new content…": "Nieuwe content indelen…", "About game data…": "Over de gamegegevens…",
    "My account": "Mijn account", "Rename this account…": "Dit account een naam geven…",
    "Owned outside pulls (gifts, free units)…": "Bezit buiten pulls (cadeaus, gratis units)…",
    "App": "App", "Weekly summary…": "Weekoverzicht…", "Save share image…": "Deelafbeelding opslaan…",
    "Check for app updates": "Controleren op app-updates", "About / disclaimer…": "Over / disclaimer…",
    "Exit": "Afsluiten", "Show window": "Venster tonen", "Import now": "Nu importeren", "Quit": "Afsluiten",
    "Daily reset": "Dagelijkse reset", "Weekly reset": "Wekelijkse reset", "Monthly reset": "Maandelijkse reset",
    # common
    "Save": "Opslaan", "Add": "Toevoegen", "Delete": "Verwijderen", "Close": "Sluiten", "Cancel": "Annuleren",
    "Refresh": "Vernieuwen", "Restore": "Terugzetten", "Search…": "Zoeken…", "Owned": "In bezit",
    "Not owned": "Niet in bezit", "All": "Alles", "Resonators": "Resonators", "Weapons": "Wapens",
    "Character": "Personage", "Weapon": "Wapen", "Copies": "Kopieën", "Date": "Datum", "Note": "Notitie",
    "Source": "Bron", "Pulls": "Pulls", "Chance": "Kans", "Banner": "Banner", "live": "nu", "upcoming": "binnenkort",
    "ended": "afgelopen",
    # planner
    "Astrite planner": "Astrite-planner", "Wishlist": "Verlanglijst", "Income": "Inkomen", "What if": "Wat als",
    "Luck test": "Geluktest", "Astrite now": "Astrite nu", "Radiant Tides now": "Radiant Tides nu",
    "Forging Tides now": "Forging Tides nu", "Target date": "Doeldatum", "Income per day": "Inkomen per dag",
    "Extra Astrite before then (events, patch rewards)": "Extra Astrite tot dan (events, patchbeloningen)",
    "Copies wanted": "Gewenste kopieën", "Use my logged income": "Mijn gelogde inkomen gebruiken",
    "Pulls on that date": "Pulls op die datum", "Chance of getting it": "Kans om het te krijgen",
    "Add wish": "Wens toevoegen", "Remove": "Verwijderen", "Move up": "Omhoog", "Move down": "Omlaag",
    "Log income": "Inkomen loggen", "Today": "Vandaag",
    "Extra Astrite": "Extra Astrite", "Days until then": "Dagen tot dan", "Astrite on that date": "Astrite op die datum",
    "Expected featured copies": "Verwachte featured kopieën", "Pulls for 50 % / 90 %": "Pulls voor 50 % / 90 %",
    "Date you reach 90 %": "Datum waarop je 90 % haalt", "Still needed for 90 %": "Nog nodig voor 90 %",
    "Real featured copies": "Echte featured kopieën", "What-if featured copies": "Wat-als featured kopieën",
    "Difference": "Verschil", "Your pulls on this banner": "Jouw pulls op deze banner",
    "Average player for the same copies": "Gemiddelde speler voor dezelfde kopieën",
    "You saved (−) / spent extra (+)": "Bespaard (−) / extra uitgegeven (+)", "5★s tested": "Geteste 5★'s",
    "Your average pity": "Jouw gemiddelde pity", "Expected average pity": "Verwachte gemiddelde pity",
    "KS test p-value": "KS-test p-waarde", "Chi-square p-value": "Chi-kwadraat p-waarde",
    "Consolidated 5★ rate": "Gemiddelde 5★-kans",
    "P(featured within 80 pulls) from pity 0": "P(featured binnen 80 pulls) vanaf pity 0",
    # collection / calendar
    "Rerun tracker": "Rerun-tracker", "My events": "Mijn events", "Add event": "Event toevoegen",
    "Tier history": "Tier-geschiedenis", "Ends in": "Eindigt over", "Starts in": "Begint over",
    # settings
    "Appearance": "Weergave", "Theme": "Thema", "Language": "Taal", "Dark": "Donker", "Light": "Licht",
    "Restart the app to apply.": "Herstart de app om dit toe te passen.",
    "Automation": "Automatisch", "Data folder": "Gegevensmap",
    "Save general settings": "Algemene instellingen opslaan",
}


def tr(text: str) -> str:
    if LANG == "nl":
        return NL.get(text, text)
    return text
