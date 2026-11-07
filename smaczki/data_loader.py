"""Dane: archiwum engsoccerdata (Anglia od 1888, Hiszpania od 1929, Włochy od 1929 – config.KRAJE; do 05.2025)
+ bieżące wyniki i terminarz. Każdy kraj osobno (własne archiwum, nazwy i odsetki wyników sezonów).

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
from .names import Nazwy, wczytaj_aliasy

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
    kursy: dict | None = None  # średnie kursy rynkowe {"1", "X", "2", "O2.5", "U2.5"}, jeśli źródło je podaje


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
    kraj: str = C.KRAJ_DOMYSLNY
    poziomy: tuple = (1, 2, 3, 4)
    ligi: list = field(default_factory=list)         # [StanLigi] – raport per liga: koniec historii, dopisane mecze
    rozegrane: dict = field(default_factory=dict)    # (data, gospodarz, gość) -> (godzina w Polsce, kursy) – mecze
                                                     # ze źródła bieżącego (do widoku minionych dni)

    @property
    def nazwa_kraju(self):
        return C.KRAJE[self.kraj].nazwa


@dataclass
class StanLigi:
    kod: str
    nazwa: str
    poziom: int
    koniec: object = None     # data ostatniego meczu w historii (archiwum + uzupełnienie)
    koniec_archiwum: object = None
    dopisane: int = 0         # mecze dopisane ze źródła bieżącego (od sezonu 2025/26 i w lukach archiwum)
    ostrzezenie: str = ""     # gdy luka od maja 2025 nie została zamknięta


def ligi_kraju(kraj=C.KRAJ_DOMYSLNY, poziomy=None):
    """{kod ligi: (nazwa, poziom, id API)} dla włączonych poziomów kraju."""
    ligi = C.KRAJE[kraj].ligi
    return {k: v for k, v in ligi.items() if poziomy is None or v[1] in poziomy}


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

def sciezka_archiwum(sciezka, kraj=C.KRAJ_DOMYSLNY):
    """Przyjmuje plik <kraj>.csv albo folder, w którym leży (dane/ lub engsoccerdata/data-raw).
    Dla innego kraju niż Anglia przy podanym pliku england.csv bierze <kraj>.csv z tego samego folderu."""
    if sciezka.lower().endswith(".csv"):
        return sciezka if kraj == C.KRAJ_DOMYSLNY else os.path.join(os.path.dirname(sciezka), f"{kraj}.csv")
    return os.path.join(sciezka, f"{kraj}.csv")


def pobierz_archiwum(sciezka, wymus=False, kraj=C.KRAJ_DOMYSLNY):
    plik = sciezka_archiwum(sciezka, kraj)
    if os.path.exists(plik) and not wymus:
        return plik
    os.makedirs(os.path.dirname(plik) or ".", exist_ok=True)
    url = f"{C.ARCHIWUM_BAZA}/{kraj}.csv"
    print(f"Pobieram archiwum engsoccerdata ({C.KRAJE[kraj].nazwa}) do {plik} …", flush=True)
    try:
        dane = _pobierz(url, timeout=300)
    except (urllib.error.URLError, OSError) as e:
        raise BladDanych(f"Nie udało się pobrać archiwum engsoccerdata ({e}). Pobierz ręcznie "
                         f"{url} i zapisz jako {plik}.") from e
    tmp = plik + ".tmp"
    with open(tmp, "wb") as f:
        f.write(dane)
    os.replace(tmp, plik)
    return plik


def wczytaj_archiwum(sciezka, kraj=C.KRAJ_DOMYSLNY, poziomy=None):
    """Archiwum kraju (tylko wspólne kolumny; nazwy ujednolicone sekcją "archiwum" z aliasy/<kraj>.json)."""
    plik = pobierz_archiwum(sciezka, kraj=kraj)
    d = pd.read_csv(plik, usecols=KOLUMNY, low_memory=False)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date", "hgoal", "vgoal"]).copy()
    d["hgoal"] = d["hgoal"].astype(int)
    d["vgoal"] = d["vgoal"].astype(int)
    d["tier"] = pd.to_numeric(d["tier"], errors="coerce").fillna(0).astype(int)
    d["Season"] = pd.to_numeric(d["Season"], errors="coerce").fillna(0).astype(int)
    if poziomy is not None:
        d = d[d.tier.isin(list(poziomy))].copy()
    aliasy = wczytaj_aliasy(kraj)
    ujednolic = aliasy.get("archiwum", {})
    w_sezonach = aliasy.get("archiwum_sezony", {})  # {nazwa: {sezon: właściwa nazwa}} – dwa kluby pod jedną nazwą
    for kol in ("home", "visitor"):
        d[kol] = d[kol].astype(str).str.strip()
        for nazwa, sezony in w_sezonach.items():
            for sezon, nowa in sezony.items():
                d.loc[(d[kol] == nazwa) & (d.Season == int(sezon)), kol] = nowa
        if ujednolic:
            d[kol] = d[kol].replace(ujednolic)
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


# średnie kursy rynkowe: od 2019/20 "Avg…", w latach 2005/06–2018/19 "BbAv…"
KOLUMNY_KURSOW = {("1", "X", "2"): [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA")],
                  ("O2.5", "U2.5"): [("Avg>2.5", "Avg<2.5"), ("BbAv>2.5", "BbAv<2.5")]}


def kursy_z_wiersza(w):
    """Średnie kursy {"1", "X", "2", "O2.5", "U2.5"} z wiersza football-data.co.uk albo None."""
    out = {}
    for typy, warianty in KOLUMNY_KURSOW.items():
        for kol in warianty:
            try:
                k = [float(w.get(c, "")) for c in kol]
            except ValueError:
                continue
            if all(x > 1.0 for x in k):
                out.update(zip(typy, k))
                break
    return out or None


def _fd_get(url):
    try:
        return _pobierz(url)
    except urllib.error.HTTPError as e:
        if e.code in (300, 404, 410):  # brak pliku (sezon nieopublikowany albo liga bez danych w tym sezonie)
            return None
        raise BladDanych(f"football-data.co.uk: błąd HTTP {e.code} dla {url}.") from e
    except (urllib.error.URLError, OSError) as e:
        raise BladDanych(f"football-data.co.uk jest niedostępne ({e}).") from e


def fd_wyniki(sezon, cache_dir, biezacy, ligi=None):
    """Zakończone mecze lig (domyślnie 4 angielskich) w sezonie. Zakończone sezony czytane z cache,
    bieżący pobierany zawsze."""
    wiersze = []
    for div, (_, tier, _) in (C.LIGI if ligi is None else ligi).items():
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
                            "visitor": w["AwayTeam"], "hgoal": hg, "vgoal": vg, "tier": tier,
                            "godz": w.get("Time", ""), "kursy": kursy_z_wiersza(w)})
    return pd.DataFrame(wiersze, columns=KOLUMNY + ["godz", "kursy"])


_TERMINARZ = {}  # fixtures.csv pobrany raz na uruchomienie (wspólny dla wszystkich krajów)


def fd_terminarz(od, do, ligi=None):
    """Mecze lig z fixtures.csv w zakresie dat (godziny brytyjskie przeliczone na polskie)."""
    url = f"{C.FD_URL}/fixtures.csv"
    if url not in _TERMINARZ:
        raw = _fd_get(url)
        if raw is None:
            raise BladDanych("football-data.co.uk: brak pliku fixtures.csv.")
        _TERMINARZ[url] = _dekoduj(raw)
    return fd_terminarz_z_tekstu(_TERMINARZ[url], od, do, ligi)


def fd_terminarz_z_tekstu(tekst, od, do, ligi=None):
    ligi = C.LIGI if ligi is None else ligi
    out = []
    for w in _csv_wiersze(tekst):
        if w.get("Div") not in ligi:
            continue
        d = _fd_data(w.get("Date", ""))
        if d is None or not (od <= d.date() <= do):
            continue
        godz = w.get("Time", "")
        if ":" in godz:
            hh, mm = godz.split(":")[:2]
            d = d.replace(hour=int(hh), minute=int(mm)) + dt.timedelta(hours=C.FD_PRZESUNIECIE_GODZIN)
        out.append(Mecz(d, ligi[w["Div"]][0], w["HomeTeam"], w["AwayTeam"], kursy_z_wiersza(w)))
    return out


def fd_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem=True, ligi=None):
    wyniki = [fd_wyniki(s, cache_dir, s == s_biez, ligi) for s in sezony]
    wyniki = pd.concat([w for w in wyniki if len(w)], ignore_index=True) if any(len(w) for w in wyniki) \
        else pd.DataFrame(columns=KOLUMNY)
    terminarz = fd_terminarz(od, do, ligi) if z_terminarzem else []
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


def api_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem=True, ligi=None):
    odpowiedzi = []
    for nazwa, tier, liga_id in (C.LIGI if ligi is None else ligi).values():
        for s in sezony:
            odpowiedzi += [(f, tier, nazwa, s) for f in api_sezon(liga_id, s, cache_dir, s == s_biez)]
    wyniki, terminarz = api_rozdziel(odpowiedzi, od, do)
    return wyniki, (terminarz if z_terminarzem else [])


# ---------- wszystko razem ----------

OPIS_ZRODLA = {"fd": "football-data.co.uk", "api": "API-Football"}


def zbierz(archiwum, cache_dir, zrodlo, dzis, od, do, z_terminarzem=True, kraj=C.KRAJ_DOMYSLNY, poziomy=None):
    """Archiwum kraju + wyniki od sezonu 2025/26 (i z sezonów brakujących w archiwum) + terminarz.
    Przy błędzie źródła: ostrzeżenie i samo archiwum. poziomy: włączone poziomy (None = wszystkie z config)."""
    ligi = ligi_kraju(kraj, poziomy)
    poziomy = tuple(sorted({t for _, t, _ in ligi.values()}))
    hist = wczytaj_archiwum(archiwum, kraj, poziomy)
    nazwy = Nazwy(hist, kraj)
    ostrz = []
    if zrodlo == "auto":
        kolejnosc = ["api", "fd"] if klucz_api() else ["fd"]
    elif zrodlo == "brak":
        kolejnosc = []
    else:
        kolejnosc = [zrodlo]
    s_biez = sezon_biezacy(dzis)
    luki = luki_archiwum(hist)
    luki_poz = [(s, t) for s, t in luki_poziomow(hist) if s not in luki]
    sezony = sorted(set(luki) | {s for s, _ in luki_poz}) + list(range(C.PIERWSZY_SEZON_PO_ARCHIWUM, s_biez + 1))
    # Anglia z 4 poziomami = domyślne ligi źródeł (wywołanie jak przed dodaniem innych krajów)
    kw = {} if kraj == C.KRAJ_DOMYSLNY and poziomy == (1, 2, 3, 4) else {"ligi": ligi}
    for z in kolejnosc:
        try:
            if z == "api":
                if not klucz_api():
                    raise BladDanych("Brak klucza API-Football: ustaw API_FOOTBALL_KEY (zmienna albo plik .env).")
                wyniki, term = api_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem, **kw)
            else:
                wyniki, term = fd_dane(sezony, s_biez, cache_dir, od, do, z_terminarzem, **kw)
        except BladDanych as e:
            ostrz.append(str(e))
            continue
        if len(wyniki):
            wyniki = wyniki[wyniki.tier.isin(list(poziomy))]
        uzupelnione = [s for s in luki if len(wyniki) and (wyniki.Season == s).any()]
        for s in luki:
            if s not in uzupelnione:
                ostrz.append(f"Archiwum nie ma sezonu {opis_sezonu(s)}, a {OPIS_ZRODLA[z]} go nie zwróciło – "
                             "smaczki obejmujące ten sezon mogą być nieścisłe.")
        rozegrane = {}
        if len(wyniki):
            wyniki = wyniki.assign(home=wyniki.home.map(nazwy), visitor=wyniki.visitor.map(nazwy),
                                   zrodlo=OPIS_ZRODLA[z])
            rozegrane = _rozegrane(wyniki)
            hist = dolacz(hist, wyniki, luki_poz)
        opis = f"archiwum engsoccerdata + {OPIS_ZRODLA[z]} (od sezonu {opis_sezonu(C.PIERWSZY_SEZON_PO_ARCHIWUM)})"
        d = Dane(hist, term, nazwy, opis, ostrz, uzupelnione=uzupelnione, pobrano=dt.datetime.now(),
                 biezace=OPIS_ZRODLA[z], kraj=kraj, poziomy=poziomy, rozegrane=rozegrane)
        d.ligi = stan_lig(d, ligi, s_biez)
        return d
    if luki:
        ostrz.append("Archiwum nie ma sezonu " + ", ".join(map(opis_sezonu, luki)) +
                     " – bez danych bieżących nie da się go uzupełnić.")
    d = Dane(hist, [], nazwy, "samo archiwum engsoccerdata", ostrz, tylko_archiwum=True, kraj=kraj, poziomy=poziomy)
    d.ligi = stan_lig(d, ligi, s_biez)
    return d


def _rozegrane(wyniki):
    """Godzina (polska) i kursy rozegranych meczów ze źródła bieżącego: {(data, gospodarz, gość): (godzina, kursy)}."""
    out = {}
    if "godz" not in wyniki and "kursy" not in wyniki:
        return out
    for r in wyniki.itertuples():
        g = str(getattr(r, "godz", "") or "")
        godz = None
        if ":" in g:
            hh, mm = g.split(":")[:2]
            try:
                godz = (dt.datetime(2000, 1, 1, int(hh), int(mm)) + dt.timedelta(hours=C.FD_PRZESUNIECIE_GODZIN)).time()
            except ValueError:
                godz = None
        k = getattr(r, "kursy", None)
        out[(pd.Timestamp(r.Date), r.home, r.visitor)] = (godz, k if isinstance(k, dict) else None)
    return out


def dolacz(hist, wyniki, luki_poz=()):
    """Dopisuje wyniki ze źródła bieżącego do archiwum bez duplikatów: sezon i poziom, który jest w archiwum,
    zostaje z archiwum (chyba że to luka w tym poziomie), a ta sama data i para drużyn to zawsze jeden mecz."""
    w = wyniki[KOLUMNY_HIST]
    if len(hist):
        w_archiwum = set(zip(hist.Season, hist.tier))
        zostaw = [(s, t) not in w_archiwum or (s, t) in set(luki_poz) for s, t in zip(w.Season, w.tier)]
        w = w[zostaw]
    razem = pd.concat([hist, w], ignore_index=True)
    razem = razem.drop_duplicates(["Date", "home", "visitor"], keep="first")
    return razem.sort_values("Date", kind="stable").reset_index(drop=True)


def stan_lig(dane, ligi, s_biez):
    """Raport per liga: ostatni mecz w historii, liczba dopisanych meczów, ostrzeżenie o niezamkniętej luce."""
    h = dane.hist
    out = []
    for kod, (nazwa, tier, _) in ligi.items():
        g = h[h.tier == tier]
        st = StanLigi(kod, nazwa, tier, g.Date.max() if len(g) else None)
        arch = g[g.zrodlo == "archiwum"]
        st.koniec_archiwum = arch.Date.max() if len(arch) else None
        st.dopisane = int((g.zrodlo != "archiwum").sum())
        if dane.tylko_archiwum:
            st.ostrzezenie = "brak danych bieżących – historia kończy się na archiwum"
        else:
            brak = [s for s in range(C.PIERWSZY_SEZON_PO_ARCHIWUM, s_biez + 1)
                    if not ((g.Season == s) & (g.zrodlo != "archiwum")).any()]
            if brak:
                st.ostrzezenie = (f"{dane.biezace} nie zwróciło wyników sezonu {', '.join(map(opis_sezonu, brak))} "
                                  "– luka od maja 2025 nie jest zamknięta")
        out.append(st)
    return out


def luki_archiwum(hist):
    """Sezony bez ani jednego meczu w archiwum (od 1993/94 – tyle sięga football-data.co.uk) do jego końca.

    engsoccerdata nie ma całego sezonu 2022/23 w Anglii; jeśli autorzy go dopiszą, nic nie będzie uzupełniane.
    """
    if "Season" not in hist or not len(hist):
        return []
    ostatni = int(hist.Season.max())
    jest = set(hist.Season.unique())
    od = max(C.LUKI_OD_SEZONU, int(hist.Season.min()))  # przed początkiem danych kraju to nie luka
    return [s for s in range(od, ostatni + 1) if s not in jest]


def luki_poziomow(hist):
    """(sezon, poziom) brakujące w archiwum w obrębie lat, w których dany poziom jest w danych (od 1993/94)."""
    out = []
    if not len(hist):
        return out
    for t, g in hist.groupby("tier"):
        jest = set(g.Season.unique())
        out += [(s, int(t)) for s in range(max(C.LUKI_OD_SEZONU, int(g.Season.min())), int(g.Season.max()) + 1)
                if s not in jest]
    return sorted(out)


def wlaczone_ligi(plik=None):
    """Włączone kraje i poziomy z pliku ligi.json: {kraj: (poziomy)}; brak pliku -> sama Anglia."""
    plik = plik or C.PLIK_LIG
    if not os.path.exists(plik):
        return {C.KRAJ_DOMYSLNY: (1, 2, 3, 4)}
    with open(plik, encoding="utf-8") as f:
        dane = json.load(f)
    out = {}
    for kraj, poziomy in dane.items():
        if kraj.startswith("_"):
            continue
        if kraj not in C.KRAJE:
            raise BladDanych(f"{plik}: nieznany kraj „{kraj}” (dostępne: {', '.join(C.KRAJE)}).")
        dostepne = {t for _, t, _ in C.KRAJE[kraj].ligi.values()}
        zle = set(poziomy) - dostepne
        if zle:
            raise BladDanych(f"{plik}: {kraj} nie ma w danych poziomów {sorted(zle)} (są: {sorted(dostepne)}).")
        if poziomy:
            out[kraj] = tuple(sorted(poziomy))
    return {k: out[k] for k in C.KRAJE if k in out}  # kolejność jak w config


def wybierz_ligi(wlaczone, filtr):
    """Zawężenie opcją --ligi: lista krajów (spain,italy) albo kodów lig (E0,D2,SC0).
    Zwraca (kraje -> poziomy historii, kody lig do terminarza albo None = wszystkie ligi tych krajów).
    Historia kraju obejmuje zawsze poziomy z ligi.json, nawet gdy terminarz jest zawężony do jednej ligi."""
    if not filtr:
        return wlaczone, None
    kraje, kody, same_kraje = {}, set(), True
    for x in [t.strip() for t in filtr.split(",") if t.strip()]:
        if x.lower() in C.KRAJE:
            kraj = x.lower()
            kraje[kraj] = wlaczone.get(kraj) or tuple(sorted({t for _, t, _ in C.KRAJE[kraj].ligi.values()}))
            kody |= {k for k, v in C.KRAJE[kraj].ligi.items() if v[1] in kraje[kraj]}
        elif x.upper() in C.LIGA_KRAJ:
            kraj, same_kraje = C.LIGA_KRAJ[x.upper()], False
            t = C.KRAJE[kraj].ligi[x.upper()][1]
            kraje[kraj] = tuple(sorted(set(wlaczone.get(kraj, ())) | {t}))
            kody.add(x.upper())
        else:
            raise BladDanych(f"--ligi: nieznane „{x}”. Kraje: {', '.join(C.KRAJE)}; "
                             f"kody lig: {', '.join(C.LIGA_KRAJ)}.")
    return {k: kraje[k] for k in C.KRAJE if k in kraje}, (None if same_kraje else kody)


def zbierz_kraje(archiwum, cache_dir, zrodlo, dzis, od, do, wlaczone, z_terminarzem=True):
    """zbierz() dla każdego włączonego kraju: [Dane]. Archiwa krajów pobierane przy pierwszym użyciu."""
    _TERMINARZ.clear()
    out = []
    for kraj, poziomy in wlaczone.items():
        out.append(zbierz(archiwum, cache_dir, zrodlo, dzis, od, do, z_terminarzem, kraj=kraj, poziomy=poziomy))
    return out
