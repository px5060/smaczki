"""Dopasowanie nazw drużyn z API-Football / football-data.co.uk do nazw z archiwum engsoccerdata.

Aliasy są osobno dla każdego kraju (smaczki/aliasy/<kraj>.json), bo ten sam skrót może znaczyć różne kluby
w różnych krajach. Plik ma sekcje:
  aliasy      – nazwa ze źródła -> nazwa w archiwum (gdy automat nie trafia albo trafiłby źle),
  archiwum    – ujednolicenie nazw w samym archiwum: ten sam klub zapisany pod kilkoma nazwami
                (zmiana nazwy, inna pisownia) -> jedna nazwa, żeby historia pary się nie rozpadała,
  nowe_kluby  – nazwy ze źródeł, które NIE są klubem z archiwum (np. nowy klub o podobnej nazwie jak dawny);
                takie nazwy nie są dopasowywane automatycznie,
  uwagi       – wyjaśnienia (tylko dla ludzi).
"""
import difflib
import json
import os
import unicodedata

import pandas as pd

KATALOG_ALIASOW = os.path.join(os.path.dirname(__file__), "aliasy")
PROG_PODOBIENSTWA = 0.75
PROG_KANDYDATOW = 0.5  # raport niedopasowanych nazw: najbliższe nazwy z archiwum od tego podobieństwa

# litery, których nie rozkłada normalizacja Unicode
_ZNAKI = str.maketrans({"ß": "ss", "ø": "o", "Ø": "O", "ı": "i", "ł": "l", "Ł": "L", "æ": "ae", "Æ": "AE",
                        "đ": "d", "Đ": "D", "œ": "oe", "Œ": "OE", "ð": "d", "þ": "th"})


def bez_znakow(nazwa):
    """Usuwa znaki diakrytyczne: „Atlético Madrid” -> „Atletico Madrid”, „1. FC Köln” -> „1. FC Koln”."""
    s = str(nazwa).translate(_ZNAKI)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _klucz(nazwa):
    return " ".join(bez_znakow(nazwa).lower().split())


def wczytaj_aliasy(kraj="england"):
    """Słownik z pliku aliasy/<kraj>.json (pusty, jeśli pliku nie ma)."""
    plik = os.path.join(KATALOG_ALIASOW, f"{kraj}.json")
    if not os.path.exists(plik):
        return {}
    with open(plik, encoding="utf-8") as f:
        return json.load(f)


# Aliasy Anglii (zgodność wstecz: testy i stare skrypty importują ALIASY z tego modułu)
ALIASY = wczytaj_aliasy("england").get("aliasy", {})


class Nazwy:
    """Wywołanie nazwy(n) zwraca nazwę z archiwum; nieznane nazwy zbiera w self.niedopasowane.

    Kolejność: alias -> dokładna zgodność (także bez znaków diakrytycznych) -> nazwa zawarta w nazwie z archiwum
    -> podobieństwo tekstu; przy kilku kandydatach wygrywa klub, który grał najpóźniej.
    """

    def __init__(self, hist, kraj="england", aliasy=None):
        ostatni = pd.concat([hist[["home", "Date"]].rename(columns={"home": "t"}),
                             hist[["visitor", "Date"]].rename(columns={"visitor": "t"})])
        self.kraj = kraj
        self.ostatni_mecz = ostatni.groupby("t").Date.max().to_dict()
        self.druzyny = sorted(self.ostatni_mecz)
        dane = wczytaj_aliasy(kraj) if aliasy is None else aliasy
        self.aliasy = {_klucz(k): v for k, v in dane.get("aliasy", {}).items()}
        self.nowe_kluby = {_klucz(n) for n in dane.get("nowe_kluby", [])}
        self._po_kluczu = {}
        for t in self.druzyny:
            self._po_kluczu.setdefault(_klucz(t), []).append(t)
        self._bez_znakow = {t: bez_znakow(t) for t in self.druzyny}
        self._cache = {}
        self.niedopasowane = set()
        self.nowe = set()  # nazwy z listy nowe_kluby, które się pojawiły

    def __call__(self, nazwa):
        nazwa = str(nazwa).strip()
        if nazwa not in self._cache:
            self._cache[nazwa] = self._dopasuj(nazwa)
        return self._cache[nazwa]

    def _najpozniej(self, kand):
        return max(kand, key=lambda t: self.ostatni_mecz[t])

    def _dopasuj(self, nazwa):
        k = _klucz(nazwa)
        if nazwa in self.ostatni_mecz:
            return nazwa if k not in self.aliasy else self.aliasy[k]
        if k in self.aliasy:
            return self.aliasy[k]
        if k in self.nowe_kluby:
            self.nowe.add(nazwa)
            return nazwa  # znany nowy klub bez historii w archiwum
        if k in self._po_kluczu:  # ta sama nazwa, inna wielkość liter / znaki diakrytyczne
            return self._najpozniej(self._po_kluczu[k])
        # 1) nazwa zawarta w nazwie z archiwum ("Luton" -> "Luton Town"); kilka kandydatów -> grał najpóźniej
        kand = [t for t in self.druzyny if k in self._bez_znakow[t].lower()]
        if kand:
            return self._najpozniej(kand)
        # 2) podobieństwo tekstu; bierzemy najbliższą nazwę (przy remisie – grała najpóźniej)
        n = bez_znakow(nazwa)
        podobne = difflib.get_close_matches(n, list(self._bez_znakow.values()), n=3, cutoff=PROG_PODOBIENSTWA)
        if podobne:
            najlepsza = difflib.SequenceMatcher(None, n, podobne[0]).ratio()
            remis = [t for t in self.druzyny
                     if self._bez_znakow[t] in podobne and difflib.SequenceMatcher(None, n, self._bez_znakow[t]).ratio() == najlepsza]
            return self._najpozniej(remis)
        self.niedopasowane.add(nazwa)
        return nazwa  # nowy klub bez historii w archiwum

    def jakosc(self, nazwa):
        """Pewność dopasowania (do wyboru kraju w trybie „mecz”): 3 – alias albo ta sama nazwa,
        2 – nazwa zawarta w nazwie z archiwum, 1 – podobieństwo tekstu, 0 – brak."""
        nazwa = str(nazwa).strip()
        k = _klucz(nazwa)
        if nazwa in self.ostatni_mecz or k in self.aliasy or k in self._po_kluczu:
            return 3
        if k in self.nowe_kluby:
            return 0
        if any(k in self._bez_znakow[t].lower() for t in self.druzyny):
            return 2
        return 1 if self(nazwa) in self.ostatni_mecz else 0

    def kandydaci(self, nazwa, n=3):
        """Najbliższe nazwy z archiwum dla nazwy bez dopasowania (do raportu: łatwiej dopisać alias)."""
        b = bez_znakow(nazwa)
        wynik = difflib.get_close_matches(b, list(self._bez_znakow.values()), n=n, cutoff=PROG_KANDYDATOW)
        slowa = {s for s in b.lower().replace(".", " ").split() if len(s) >= 4}
        for t in self.druzyny:  # wspólne słowo (np. nazwa miasta), jeśli podobieństwo całości jest małe
            if len(wynik) < n and t not in wynik and slowa & set(self._bez_znakow[t].lower().replace(".", " ").split()):
                wynik.append(self._bez_znakow[t])
        odwrotnie = {v: t for t, v in self._bez_znakow.items()}
        return [odwrotnie.get(x, x) for x in wynik[:n]]

    def mapa(self):
        """Słownik {nazwa ze źródła: nazwa w archiwum} dla wszystkich dotąd sprawdzonych nazw."""
        return dict(sorted(self._cache.items()))
