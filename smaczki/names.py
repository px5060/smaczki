"""Dopasowanie nazw drużyn z API-Football / football-data.co.uk do nazw z archiwum engsoccerdata."""
import difflib

import pandas as pd

# Nazwy, których nie da się dopasować automatycznie (albo dopasowałyby się źle).
ALIASY = {
    # API-Football
    "Wolves": "Wolverhampton Wanderers",
    "Sheffield Utd": "Sheffield United",
    "Sheffield Wed": "Sheffield Wednesday",
    "QPR": "Queens Park Rangers",
    "MK Dons": "Milton Keynes Dons",
    "Accrington ST": "Accrington",          # obecny klub (od 2006); "Accrington Stanley" w archiwum to klub 1921–1962
    "Accrington Stanley": "Accrington",
    "Bradford": "Bradford City",
    "Harrogate Town": "Harrogate Town A.F.C.",
    "Stevenage": "Stevenage Borough",
    "Sutton Utd": "Sutton United",
    "Man United": "Manchester United",      # bez aliasu difflib wskazałby Maidstone United
    "Man City": "Manchester City",
    "Spurs": "Tottenham Hotspur",
    "Dagenham & Redbridge": "Dagenham and Redbridge",
    "Brighton": "Brighton & Hove Albion",   # nie "New Brighton"
    "Bournemouth": "AFC Bournemouth",
    "Newport": "Newport County",
    # football-data.co.uk
    "Nott'm Forest": "Nottingham Forest",
    "Sheffield Weds": "Sheffield Wednesday",
    "Bristol Rvs": "Bristol Rovers",
    "Peterboro": "Peterborough United",
    "Harrogate": "Harrogate Town A.F.C.",
}

PROG_PODOBIENSTWA = 0.75


class Nazwy:
    """Wywołanie nazwy(n) zwraca nazwę z archiwum; nieznane nazwy zbiera w self.niedopasowane."""

    def __init__(self, hist):
        ostatni = pd.concat([hist[["home", "Date"]].rename(columns={"home": "t"}),
                             hist[["visitor", "Date"]].rename(columns={"visitor": "t"})])
        self.ostatni_mecz = ostatni.groupby("t").Date.max().to_dict()
        self.druzyny = sorted(self.ostatni_mecz)
        self._cache = {}
        self.niedopasowane = set()

    def __call__(self, nazwa):
        nazwa = str(nazwa).strip()
        if nazwa not in self._cache:
            self._cache[nazwa] = self._dopasuj(nazwa)
        return self._cache[nazwa]

    def _dopasuj(self, nazwa):
        if nazwa in ALIASY:
            return ALIASY[nazwa]
        if nazwa in self.ostatni_mecz:
            return nazwa
        # 1) nazwa zawarta w nazwie z archiwum ("Luton" -> "Luton Town"); kilka kandydatów -> grał najpóźniej
        kand = [t for t in self.druzyny if nazwa.lower() in t.lower()]
        if kand:
            return max(kand, key=lambda t: self.ostatni_mecz[t])
        # 2) podobieństwo tekstu; bierzemy najbliższą nazwę (przy remisie – grała najpóźniej)
        podobne = difflib.get_close_matches(nazwa, self.druzyny, n=3, cutoff=PROG_PODOBIENSTWA)
        if podobne:
            najlepsza = difflib.SequenceMatcher(None, nazwa, podobne[0]).ratio()
            remis = [t for t in podobne if difflib.SequenceMatcher(None, nazwa, t).ratio() == najlepsza]
            return max(remis, key=lambda t: self.ostatni_mecz[t])
        self.niedopasowane.add(nazwa)
        return nazwa  # nowy klub bez historii w archiwum

    def mapa(self):
        """Słownik {nazwa ze źródła: nazwa w archiwum} dla wszystkich dotąd sprawdzonych nazw."""
        return dict(sorted(self._cache.items()))
