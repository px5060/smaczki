"""Skuteczność typów zgodnych z seriami – test na historii z kursami (football-data.co.uk, od sezonu 2005/06).

Dla każdego meczu z kursami liczone są serie pary tylko z meczów sprzed tego meczu (jak w dniu meczu),
a dla każdej istotnej serii sprawdzane jest, czy zakład zgodny z serią wszedł i ile by zarobił/stracił
przy średnim kursie rynkowym (stawka 1). Kurs podwójnej szansy (1X, X2, 12) jest wyliczany z kursów 1X2:
1 / (1/k_a + 1/k_b).
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

from . import config as C
from .data_loader import (_csv_wiersze, _dekoduj, _fd_data, _fd_get, _fd_kod, kursy_z_wiersza, sezon_biezacy,
                          zbierz)
from .rules import fakty_pary, stawki_sezonow

PLIK = os.path.join(os.path.dirname(__file__), "skutecznosc.json")
OPIS_TYPU = {"1": "wygra gospodarz", "X": "remis", "2": "wygra gość",
             "1X": "gospodarz nie przegra", "X2": "gość nie przegra", "12": "nie będzie remisu"}


def kurs_typu(k1, kx, k2, typ):
    k = {"1": k1, "X": kx, "2": k2}
    if len(typ) == 1:
        return k[typ]
    a, b = k[typ[0]], k[typ[1]]
    return 1.0 / (1.0 / a + 1.0 / b)  # kurs podwójnej szansy z kursów 1X2


def trafiony(hg, vg, typ):
    return ("1" if hg > vg else ("X" if hg == vg else "2")) in typ


def kursy_sezonu(sezon, cache_dir, biezacy):
    """Kursy 1X2 (średnie rynkowe) wszystkich meczów 4 lig w sezonie, nazwy ze źródła."""
    wiersze = []
    for div in C.LIGI:
        plik = os.path.join(cache_dir, f"fd_{_fd_kod(sezon)}_{div}.csv")
        if not biezacy and os.path.exists(plik):
            with open(plik, "rb") as f:
                raw = f.read()
        else:
            raw = _fd_get(f"{C.FD_URL}/mmz4281/{_fd_kod(sezon)}/{div}.csv")
            if raw is None:
                continue
            if not biezacy:
                os.makedirs(cache_dir, exist_ok=True)
                with open(plik, "wb") as f:
                    f.write(raw)
        for w in _csv_wiersze(_dekoduj(raw)):
            d, k = _fd_data(w.get("Date", "")), kursy_z_wiersza(w)
            if d is not None and k is not None:
                wiersze.append({"Date": pd.Timestamp(d.date()), "home": w["HomeTeam"], "visitor": w["AwayTeam"],
                                "k1": k[0], "kx": k[1], "k2": k[2]})
    return pd.DataFrame(wiersze)


def _statystyka(df):
    if not len(df):
        return None
    return {"typow": int(len(df)), "trafione": round(float(df.traf.mean()), 4),
            "kurs": round(float(df.kurs.mean()), 3), "zwrot": round(float(df.zysk.mean()), 4)}


def policz(archiwum, cache_dir, od_sezonu=2005, dzis=None, postep=True):
    dzis = dzis or dt.date.today()
    dane = zbierz(archiwum, cache_dir, "fd", dzis, dzis, dzis, z_terminarzem=False)
    hist, nazwy = dane.hist, dane.nazwy
    st = stawki_sezonow(hist)
    s_biez = sezon_biezacy(dzis)
    kursy = pd.concat([kursy_sezonu(s, cache_dir, s == s_biez) for s in range(od_sezonu, s_biez + 1)],
                      ignore_index=True)
    kursy["home"] = kursy.home.map(nazwy)
    kursy["visitor"] = kursy.visitor.map(nazwy)
    mecze_k = hist.merge(kursy, on=["Date", "home", "visitor"], how="inner")

    klucz = np.where(hist.home < hist.visitor, hist.home + "|" + hist.visitor, hist.visitor + "|" + hist.home)
    grupy = {k: g for k, g in hist.groupby(klucz, sort=False)}
    rekordy = []
    for i, r in enumerate(mecze_k.itertuples()):
        if postep and i % 5000 == 0:
            print(f"  {i}/{len(mecze_k)} meczów …", flush=True)
        g = grupy[r.home + "|" + r.visitor if r.home < r.visitor else r.visitor + "|" + r.home]
        przed = g[g.Date < r.Date]
        if not len(przed):
            continue
        fakty = [f for f in fakty_pary(przed, r.home, r.visitor, r.Date, st) if f.typ]
        for j, f in enumerate(fakty):
            kurs = kurs_typu(r.k1, r.kx, r.k2, f.typ)
            traf = trafiony(r.hgoal, r.vgoal, f.typ)
            rekordy.append({"regula": f.regula, "typ": f.typ, "n": f.n, "gwiazdka": f.waga >= C.PROG_DNIA,
                            "glowny": j == 0, "traf": traf, "kurs": kurs, "zysk": (kurs - 1) if traf else -1.0})
    r = pd.DataFrame(rekordy)

    # punkt odniesienia: ten sam zakład na każdy mecz z kursami
    bazowe = {}
    for typ in OPIS_TYPU:
        k = np.array([kurs_typu(a, b, c, typ) for a, b, c in zip(mecze_k.k1, mecze_k.kx, mecze_k.k2)])
        t = np.array([trafiony(a, b, typ) for a, b in zip(mecze_k.hgoal, mecze_k.vgoal)])
        bazowe[typ] = _statystyka(pd.DataFrame({"traf": t, "kurs": k, "zysk": np.where(t, k - 1, -1.0)}))

    wynik = {
        "okres": f"{od_sezonu}/{(od_sezonu + 1) % 100:02d}–{s_biez}/{(s_biez + 1) % 100:02d}",
        "policzono": dzis.isoformat(),
        "meczow": int(len(mecze_k)),
        "reguly": {k: _statystyka(g) for k, g in r.groupby("regula")},
        "reguly_gwiazdka": {k: _statystyka(g) for k, g in r[r.gwiazdka].groupby("regula")},
        "typy": {k: _statystyka(g) for k, g in r.groupby("typ")},
        "glowny_typ": _statystyka(r[r.glowny]),
        "glowny_typ_gwiazdka": _statystyka(r[r.glowny & r.gwiazdka]),
        "bazowe": bazowe,
    }
    return wynik, r


def zapisz(wynik, plik=PLIK):
    with open(plik, "w", encoding="utf-8") as f:
        json.dump(wynik, f, ensure_ascii=False, indent=1)


def wczytaj(plik=PLIK):
    try:
        with open(plik, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
