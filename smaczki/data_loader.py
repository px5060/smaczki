"""Dane: archiwum engsoccerdata (1888–05.2025) + bieżące wyniki i terminarz.

Źródła bieżące:
  fd  – football-data.co.uk: darmowe pliki CSV, bez klucza (wyniki aktualizowane ok. 2 razy w tygodniu,
        terminarz najbliższych dni w fixtures.csv),
  api – API-Football v3 (klucz w API_FOOTBALL_KEY); jedno zapytanie na ligę i sezon.
"""
import csv
import datetime as dt
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import pandas as pd

from . import config as C
from .names import Nazwy

NAGLOWKI = {"User-Agent": "smaczki-meczowe/1.0 (python urllib)"}
KOLUMNY = ["Date", "Season", "home", "visitor", "hgoal", "vgoal", "tier"]
KOLUMNY_HIST = KOLUMNY + ["zrodlo"]  # zrodlo: archiwum / football-data.co.uk / API-Football


class BladDanych(Exception):
    """Błąd źródła danych – komunikat do pokazania użytkownikowi."""


@dataclass
class Mecz:
    data: dt.datetime | None  # termin w czasie polskim (albo None, gdy nieznany)
    liga: str
    home: str                 # nazwa ze źródła (mapowana później przez Nazwy)
    away: str
    kursy: tuple | None = None  # średnie kursy rynkowe (1, X, 2), jeśli źródło je podaje


@dataclass
class Dane:
    hist: pd.DataFrame
    terminarz: list
    nazwy: Nazwy
    zrodlo: str
    ostrzezenia: list = field(default_factory=list)
    tylko_archiwum: bool = False
    uzupelnione: list = field(default_factory=list)  # sezony brakujące w archiwum, dopisane ze źródła
    pobrano: dt.datetime | None = None               # kiedy pobrano dane bieżące
    biezace: str | None = None                       # nazwa źródła bieżącego (None = samo archiwum)


def _pobierz(url, naglowki=None, timeout=60):
    req = urllib.request.Request(url, headers={**NAGLOWKI, **(naglowki or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def sezon_biezacy(dzis):
    """Rok rozpoczęcia bieżącego sezonu (2026/27 -> 2026)."""
    return dzis.year if dzis.month >= 7 else dzis.year - 1


def opis_sezonu(s):
    return f"{s}/{(s + 1) % 100:02d}"


# ---------- archiwum engsoccerdata ----------

def sciezka_archiwum(sciezka):
    """Przyjmuje plik england.csv albo folder, w którym leży (dane/ lub engsoccerdata/data-raw)."""
    if sciezka.lower().endswith(".csv"):
        return sciezka
    return os.path.join(sciezka, "england.csv")


def pobierz_archiwum(sciezka, wymus=False):
    plik = sciezka_archiwum(sciezka)
    if os.path.exists(plik) and not wymus:
        return plik
    os.makedirs(os.path.dirname(plik) or ".", exist_ok=True)
    print(f"Pobieram archiwum engsoccerdata (ok. 15 MB) do {plik} …", flush=True)
    try:
        dane = _pobierz(C.ARCHIWUM_URL, timeout=300)
    except (urllib.error.URLError, OSError) as e:
        raise BladDanych(f"Nie udało się pobrać archiwum engsoccerdata ({e}). Pobierz ręcznie "
                         f"{C.ARCHIWUM_URL} i zapisz jako {plik}.") from e
    tmp = plik + ".tmp"
    with open(tmp, "wb") as f:
        f.write(dane)
    os.replace(tmp, plik)
    return plik


def wczytaj_archiwum(sciezka):
    plik = pobierz_archiwum(sciezka)
    d = pd.read_csv(plik, usecols=KOLUMNY, low_memory=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date", "hgoal", "vgoal"]).copy()
    d["hgoal"] = d["hgoal"].astype(int)
    d["vgoal"] = d["vgoal"].astype(int)
    d["tier"] = pd.to_numeric(d["tier"], errors="coerce").fillna(0).astype(int)
    d["Season"] = pd.to_numeric(d["Season"], errors="coerce").fillna(0).astype(int)
    d["zrodlo"] = "archiwum"
    return d.sort_values("Date", kind="stable").reset_index(drop=True)


# ---------- football-data.co.uk ----------

def _fd_kod(sezon):
    return f"{sezon % 100:02d}{(sezon + 1) % 100:02d}"  # 2026 -> "2627"


def _dekoduj(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _csv_wiersze(tekst):
    """Wiersze CSV jako słowniki; odporne na nadmiarowe/brakujące pola w pojedynczych wierszach."""
    r = csv.reader(io.StringIO(tekst))
    naglowek = [h.strip().lstrip("﻿") for h in next(r, [])]
    for w in r:
        if any(x.strip() for x in w):
            yield {k: (w[i].strip() if i < len(w) else "") for i, k in enumerate(naglowek)}


def _fd_data(s):
    for f in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(s.strip(), f)
        except ValueError:
            pass
    return None


def _int(s):
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


KOLUMNY_KURSOW = [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA")]  # średnie rynkowe (od 2019 / 2005–2019)


def kursy_z_wiersza(w):
    """Średnie kursy 1X2 z wiersza football-data.co.uk albo None."""
    for kol in KOLUMNY_KURSOW:
        try:
            k = tuple(float(w.get(c, "")) for c in kol)
        except ValueError:
            continue
        if all(x > 1.0 for x in k):
            return k
    return None


def _fd_get(url):
    try:
        return _pobierz(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise BladDanych(f"football-data.co.uk: błąd HTTP {e.code} dla {url}.") from e
    except (urllib.error.URLError, OSError) as e:
        raise BladDanych(f"football-data.co.uk jest niedostępne ({e}).") from e


def fd_wyniki(sezon, cache_dir, biezacy):
    """Zakończone mecze 4 lig w sezonie. Zakończone sezony czytane z cache, bieżący pobierany zawsze."""
    wiersze = []
    for div, (_, tier, _) in C.LIGI.items():
        plik = os.path.join(cache_dir, f"fd_{_fd_kod(sezon)}_{div}.csv")
        if not biezacy and os.path.exists(plik):
            with open(plik, "rb") as f:
                raw = f.read()
        else:
            raw = _fd_get(f"{C.FD_URL}/mmz4281/{_fd_kod(sezon)}/{div}.csv")
            if raw is None:
                continue  # sezon jeszcze nieopublikowany (np. w lipcu)
            if not biezacy:  # do cache trafia tylko sezon pobrany po jego zakończeniu
                os.makedirs(cache_dir, exist_ok=True)
                with open(plik, "wb") as f:
                    f.write(raw)
        for w in _csv_wiersze(_dekoduj(raw)):
            d, hg, vg = _fd_data(w.get("Date", "")), _int(w.get("FTHG")), _int(w.get("FTAG"))
            if d is None or hg is None or vg is None:
                continue
            wiersze.append({"Date": pd.Timestamp(d.date()), "Season": sezon, "home": w["HomeTeam"],
                            "visitor": w["AwayTeam"], "hgoal": hg, "vgoal": vg, "tier": tier})
    return pd.DataFrame(wiersze, columns=KOLUMNY)


def fd_terminarz(od, do):
    """Mecze 4 lig z fixtures.csv w zakresie dat (daty brytyjskie, godziny przeliczone na polskie)."""
    raw = _fd_get(f"{C.FD_URL}/fixtures.csv")
    if raw is None:
        raise BladDanych("football-data.co.uk: brak pliku fixtures.csv.")
    return fd_terminarz_z_tekstu(_dekoduj(raw), od, do)


def fd_terminarz_z_tekstu(tekst, od, do):
    out = []
    for w in _csv_wiersze(tekst):
        if w.get("Div") not in C.LIGI:
            continue
        d = _fd_data(w.get("Date", ""))
        if d is None or not (od <= d.date() <= do):
            continue
        godz = w.get("Time", "")
        if ":" in godz:
            hh, mm = godz.split(":")[:2]
            d = d.replace(hour=int(hh), minute=int(mm)) + dt.timedelta(hours=C.FD_PRZESUNIECIE_GODZIN)
        out.append(Mecz(d, C.LIGI[w["Div"]][0], w["HomeTeam"], w["AwayTeam"], kursy_z_wiersza(w)))
    return out


def fd_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem=True):
    wyniki = [fd_wyniki(s, cache_dir, s == s_biez) for s in sezony]
    wyniki = pd.concat([w for w in wyniki if len(w)], ignore_index=True) if any(len(w) for w in wyniki) \
        else pd.DataFrame(columns=KOLUMNY)
    terminarz = fd_terminarz(od, do) if z_terminarzem else []
    return wyniki, terminarz


# ---------- API-Football v3 ----------

def _api_konfig():
    klucz = os.environ.get("API_FOOTBALL_KEY", "").strip()
    host = os.environ.get("API_FOOTBALL_HOST", "").strip() or C.API_HOST_DOMYSLNY
    if "rapidapi" in host:  # klucz z RapidAPI: inny host i nagłówki
        return klucz, f"https://{host}/v3/fixtures", {"x-rapidapi-key": klucz, "x-rapidapi-host": host}
    return klucz, f"https://{host}/fixtures", {"x-apisports-key": klucz}


def klucz_api():
    return _api_konfig()[0]


def _api_bledy(bledy, params):
    if isinstance(bledy, dict):
        tekst = "; ".join(f"{k}: {v}" for k, v in bledy.items())
    else:
        tekst = "; ".join(map(str, bledy))
    rada = ""
    if "plan" in tekst.lower() or "season" in tekst.lower():
        rada = (" Twój plan API-Football nie obejmuje tego sezonu (darmowy plan ma tylko starsze sezony)"
                " – użyj --zrodlo fd (football-data.co.uk, bez klucza).")
    elif "token" in tekst.lower() or "key" in tekst.lower():
        rada = " Sprawdź klucz w API_FOOTBALL_KEY (i API_FOOTBALL_HOST, jeśli klucz jest z RapidAPI)."
    elif "limit" in tekst.lower() or "requests" in tekst.lower():
        rada = " Wyczerpany dzienny limit zapytań – spróbuj jutro albo użyj --zrodlo fd."
    liga = params.get("league")
    return f"API-Football odrzuciło zapytanie (liga {liga}, sezon {opis_sezonu(params['season'])}): {tekst}.{rada}"


def api_zapytanie(params):
    _, url, nagl = _api_konfig()
    try:
        raw = _pobierz(url + "?" + urllib.parse.urlencode(params), nagl)
    except urllib.error.HTTPError as e:
        powod = "zły klucz albo host" if e.code in (401, 403) else ("limit zapytań" if e.code == 429 else e.reason)
        raise BladDanych(f"API-Football: błąd HTTP {e.code} ({powod}).") from e
    except (urllib.error.URLError, OSError) as e:
        raise BladDanych(f"API-Football jest niedostępne ({e}).") from e
    dane = json.loads(raw)
    if dane.get("errors"):
        raise BladDanych(_api_bledy(dane["errors"], params))
    return dane.get("response", [])


def api_sezon(liga_id, sezon, cache_dir, biezacy):
    plik = os.path.join(cache_dir, f"api_{liga_id}_{sezon}.json")
    if not biezacy and os.path.exists(plik):
        with open(plik, encoding="utf-8") as f:
            return json.load(f)
    odp = api_zapytanie({"league": liga_id, "season": sezon, "timezone": C.API_STREFA})
    if not biezacy:
        os.makedirs(cache_dir, exist_ok=True)
        with open(plik, "w", encoding="utf-8") as f:
            json.dump(odp, f)
    return odp


def api_rozdziel(odpowiedzi, od, do):
    """[(fixture, tier, nazwa_ligi, sezon)] -> (DataFrame zakończonych meczów, terminarz NS/TBD z zakresu dat)."""
    wyniki, terminarz = [], []
    for f, tier, liga, sezon in odpowiedzi:
        status = f["fixture"]["status"]["short"]
        data = dt.datetime.fromisoformat(f["fixture"]["date"][:19])
        h, v = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
        if status in C.API_ZAKONCZONE and f["goals"]["home"] is not None:
            wyniki.append({"Date": pd.Timestamp(data.date()), "Season": sezon, "home": h, "visitor": v,
                           "hgoal": int(f["goals"]["home"]), "vgoal": int(f["goals"]["away"]), "tier": tier})
        elif status in C.API_DO_ROZEGRANIA and od <= data.date() <= do:
            terminarz.append(Mecz(data, liga, h, v))
    return pd.DataFrame(wyniki, columns=KOLUMNY), terminarz


def api_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem=True):
    odpowiedzi = []
    for nazwa, tier, liga_id in C.LIGI.values():
        for s in sezony:
            odpowiedzi += [(f, tier, nazwa, s) for f in api_sezon(liga_id, s, cache_dir, s == s_biez)]
    wyniki, terminarz = api_rozdziel(odpowiedzi, od, do)
    return wyniki, (terminarz if z_terminarzem else [])


# ---------- wszystko razem ----------

OPIS_ZRODLA = {"fd": "football-data.co.uk", "api": "API-Football"}


def zbierz(archiwum, cache_dir, zrodlo, dzis, od, do, z_terminarzem=True):
    """Archiwum + wyniki od sezonu 2025/26 + terminarz. Przy błędzie źródła: ostrzeżenie i samo archiwum."""
    hist = wczytaj_archiwum(archiwum)
    nazwy = Nazwy(hist)
    ostrz = []
    if zrodlo == "auto":
        kolejnosc = ["api", "fd"] if klucz_api() else ["fd"]
    elif zrodlo == "brak":
        kolejnosc = []
    else:
        kolejnosc = [zrodlo]
    s_biez = sezon_biezacy(dzis)
    luki = luki_archiwum(hist)
    sezony = luki + list(range(C.PIERWSZY_SEZON_PO_ARCHIWUM, s_biez + 1))
    for z in kolejnosc:
        try:
            if z == "api":
                if not klucz_api():
                    raise BladDanych("Brak klucza API-Football: ustaw API_FOOTBALL_KEY (zmienna albo plik .env).")
                wyniki, term = api_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem)
            else:
                wyniki, term = fd_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem)
        except BladDanych as e:
            ostrz.append(str(e))
            continue
        uzupelnione = [s for s in luki if len(wyniki) and (wyniki.Season == s).any()]
        for s in luki:
            if s not in uzupelnione:
                ostrz.append(f"Archiwum nie ma sezonu {opis_sezonu(s)}, a {OPIS_ZRODLA[z]} go nie zwróciło – "
                             "smaczki obejmujące ten sezon mogą być nieścisłe.")
        if len(wyniki):
            wyniki = wyniki.assign(home=wyniki.home.map(nazwy), visitor=wyniki.visitor.map(nazwy),
                                   zrodlo=OPIS_ZRODLA[z])
            hist = pd.concat([hist, wyniki[KOLUMNY_HIST]], ignore_index=True).sort_values("Date", kind="stable") \
                .reset_index(drop=True)
        opis = f"archiwum engsoccerdata + {OPIS_ZRODLA[z]} (od sezonu {opis_sezonu(C.PIERWSZY_SEZON_PO_ARCHIWUM)})"
        return Dane(hist, term, nazwy, opis, ostrz, uzupelnione=uzupelnione, pobrano=dt.datetime.now(),
                    biezace=OPIS_ZRODLA[z])
    if luki:
        ostrz.append("Archiwum nie ma sezonu " + ", ".join(map(opis_sezonu, luki)) +
                     " – bez danych bieżących nie da się go uzupełnić.")
    return Dane(hist, [], nazwy, "samo archiwum engsoccerdata", ostrz, tylko_archiwum=True)


def luki_archiwum(hist):
    """Sezony bez ani jednego meczu w archiwum (od 1993/94 – tyle sięga football-data.co.uk) do jego końca.

    engsoccerdata nie ma całego sezonu 2022/23; jeśli autorzy go dopiszą, nic nie będzie uzupełniane.
    """
    if "Season" not in hist or not len(hist):
        return []
    ostatni = int(hist.Season.max())
    jest = set(hist.Season.unique())
    return [s for s in range(C.LUKI_OD_SEZONU, ostatni + 1) if s not in jest]
