"""Skuteczność typów zgodnych z seriami – test na historii z kursami (football-data.co.uk, od sezonu 2005/06).

Dla każdego meczu z kursami liczone są serie pary tylko z meczów sprzed tego meczu (jak w dniu meczu),
a dla każdej istotnej serii sprawdzane jest, czy zakład zgodny z serią wszedł i ile by zarobił/stracił
przy średnim kursie rynkowym (stawka 1). Kurs podwójnej szansy (1X, X2, 12) jest wyliczany z kursów 1X2:
prawdopodobieństwa bez marży bukmachera plus połowa marży (rules.kurs_typu). Dla "obie strzelą" i dokładnego wyniku kursów w danych nie ma – wtedy liczona jest tylko
skuteczność i porównanie z tym, jak często taki wynik pada przeciętnie w danym sezonie.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

from . import config as C
from .data_loader import (_csv_wiersze, _dekoduj, _fd_data, _fd_get, _fd_kod, kursy_z_wiersza, sezon_biezacy,
                          zbierz)
from .rules import fakty_pary, kurs_typu, stawki_sezonow, typ_ostateczny, typy_wspolne, wyniki_sezonow

PLIK = os.path.join(os.path.dirname(__file__), "skutecznosc.json")
TYPY_BAZOWE = ["1", "X", "2", "1X", "X2", "12", "O2.5", "U2.5", "BTTS", "noBTTS"]
KOLUMNY_K = ["1", "X", "2", "O2.5", "U2.5"]


def trafiony(hg, vg, typ):
    if typ == "O2.5":
        return hg + vg >= 3
    if typ == "U2.5":
        return hg + vg <= 2
    if typ == "BTTS":
        return hg > 0 and vg > 0
    if typ == "noBTTS":
        return not (hg > 0 and vg > 0)
    if typ.startswith("S"):
        a, b = typ[1:].split(":")
        return hg == int(a) and vg == int(b)
    return ("1" if hg > vg else ("X" if hg == vg else "2")) in typ


def przecietnie(st, sezon, typ):
    """Jak często taki wynik padał przeciętnie w sezonie (wszystkie mecze 4 lig)."""
    if typ.startswith("S"):
        a, b = typ[1:].split(":")
        return wyniki_sezonow(st).get((sezon, int(a), int(b)), C.WYNIK_DOMYSLNY)
    if sezon not in st.index:
        return np.nan
    r = st.loc[sezon]
    if typ in ("O2.5", "U2.5"):
        return r["O"] if typ == "O2.5" else 1 - r["O"]
    if typ in ("BTTS", "noBTTS"):
        return r["B"] if typ == "BTTS" else 1 - r["B"]
    return sum(r[c] for c in typ)


def kursy_sezonu(sezon, cache_dir, biezacy):
    """Średnie kursy rynkowe wszystkich meczów 4 lig w sezonie (nazwy ze źródła)."""
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
                                **{c: k.get(c, np.nan) for c in KOLUMNY_K}})
    return pd.DataFrame(wiersze)


def _statystyka(df):
    if not len(df):
        return None
    z_kursem = df[df.kurs.notna()]
    return {"typow": int(len(df)), "trafione": round(float(df.traf.mean()), 4),
            "przecietnie": round(float(df.przec.mean()), 4),
            "kurs": round(float(z_kursem.kurs.mean()), 3) if len(z_kursem) else None,
            "zwrot": round(float(z_kursem.zysk.mean()), 4) if len(z_kursem) >= 0.9 * len(df) else None}


def _kursy(r):
    return {c: getattr(r, f"k_{i}") for i, c in enumerate(KOLUMNY_K) if not pd.isna(getattr(r, f"k_{i}"))}


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
    kursy = kursy.rename(columns={c: f"k_{i}" for i, c in enumerate(KOLUMNY_K)})
    mecze_k = hist.merge(kursy, on=["Date", "home", "visitor"], how="inner")

    klucz = np.where(hist.home < hist.visitor, hist.home + "|" + hist.visitor, hist.visitor + "|" + hist.home)
    grupy = {k: g for k, g in hist.groupby(klucz, sort=False)}
    rekordy, wspolne, ostateczne = [], [], []
    for i, r in enumerate(mecze_k.itertuples()):
        if postep and i % 5000 == 0:
            print(f"  {i}/{len(mecze_k)} meczów …", flush=True)
        g = grupy[r.home + "|" + r.visitor if r.home < r.visitor else r.visitor + "|" + r.home]
        przed = g[g.Date < r.Date]
        if not len(przed):
            continue
        k = _kursy(r)
        fakty = [f for f in fakty_pary(przed, r.home, r.visitor, r.Date, st) if f.typ]
        for j, f in enumerate(fakty):
            kurs = kurs_typu(k, f.typ)
            traf = trafiony(r.hgoal, r.vgoal, f.typ)
            rekordy.append({"regula": f.regula, "typ": f.typ, "n": f.n, "gwiazdka": f.waga >= C.PROG_DNIA,
                            "glowny": j == 0, "traf": traf, "przec": przecietnie(st, r.Season, f.typ),
                            "kurs": kurs, "zysk": None if kurs is None else ((kurs - 1) if traf else -1.0)})
        gwiazdka = bool(fakty) and fakty[0].waga >= C.PROG_DNIA
        ost = typ_ostateczny(fakty, k)
        if ost is not None:
            kurs = kurs_typu(k, ost.typ)
            traf = trafiony(r.hgoal, r.vgoal, ost.typ)
            ostateczne.append({"data": r.Date, "najdl": ost.najdluzsza, "kurs_sort": kurs or 0.0,
                               "klucz": ost.klucz, "rynek": ost.rynek, "gwiazdka": gwiazdka, "traf": traf,
                               "przec": przecietnie(st, r.Season, ost.typ), "kurs": kurs,
                               "zysk": None if kurs is None else ((kurs - 1) if traf else -1.0)})
        for t in typy_wspolne(fakty):
            if t.typ is None:
                wspolne.append({"klucz": f"{t.rynek}:sprzeczne", "rynek": t.rynek, "gwiazdka": gwiazdka,
                                "traf": np.nan, "przec": np.nan, "kurs": None, "zysk": None})
                continue
            kurs = kurs_typu(k, t.typ)
            traf = trafiony(r.hgoal, r.vgoal, t.typ)
            wspolne.append({"klucz": t.klucz, "rynek": t.rynek, "gwiazdka": gwiazdka, "traf": traf,
                            "przec": przecietnie(st, r.Season, t.typ), "kurs": kurs,
                            "zysk": None if kurs is None else ((kurs - 1) if traf else -1.0)})
    r = pd.DataFrame(rekordy)
    r["kurs"] = pd.to_numeric(r.kurs)
    r["zysk"] = pd.to_numeric(r.zysk)
    w = pd.DataFrame(wspolne)
    w["kurs"] = pd.to_numeric(w.kurs)
    w["zysk"] = pd.to_numeric(w.zysk)
    o = pd.DataFrame(ostateczne)
    o["kurs"] = pd.to_numeric(o.kurs)
    o["zysk"] = pd.to_numeric(o.zysk)
    sprzeczne = w[w.klucz.str.endswith(":sprzeczne")]
    w = w[~w.klucz.str.endswith(":sprzeczne")].copy()
    w["traf"] = w.traf.astype(bool)

    # punkt odniesienia: ten sam zakład na każdy mecz z kursami
    bazowe = {}
    for typ in TYPY_BAZOWE:
        kursy_t = [kurs_typu(_kursy(x), typ) for x in mecze_k.itertuples()]
        t = [trafiony(a, b, typ) for a, b in zip(mecze_k.hgoal, mecze_k.vgoal)]
        df = pd.DataFrame({"traf": t, "kurs": pd.to_numeric(pd.Series(kursy_t, dtype="float")),
                           "przec": [przecietnie(st, s, typ) for s in mecze_k.Season]})
        df["zysk"] = np.where(df.kurs.isna(), np.nan, np.where(df.traf, df.kurs - 1, -1.0))
        bazowe[typ] = _statystyka(df)

    glowny = r[r.glowny & r.kurs.notna()]
    wynik = {
        "okres": f"{od_sezonu}/{(od_sezonu + 1) % 100:02d}–{s_biez}/{(s_biez + 1) % 100:02d}",
        "policzono": dzis.isoformat(),
        "meczow": int(len(mecze_k)),
        "reguly": {k: _statystyka(g) for k, g in r.groupby("regula")},
        "reguly_gwiazdka": {k: _statystyka(g) for k, g in r[r.gwiazdka].groupby("regula")},
        "typy": {k: _statystyka(g) for k, g in r[~r.typ.str.startswith("S")].groupby("typ")},
        "glowny_typ": _statystyka(glowny),
        "glowny_typ_gwiazdka": _statystyka(glowny[glowny.gwiazdka]),
        "wspolne": {k: _statystyka(g) for k, g in w.groupby("klucz")},
        "wspolny_1X2": _statystyka(w[w.rynek == "1X2"]),
        "wspolny_1X2_gwiazdka": _statystyka(w[(w.rynek == "1X2") & w.gwiazdka]),
        "wspolny_gole": _statystyka(w[w.rynek == "gole"]),
        "sprzeczne": {k: int(n) for k, n in sprzeczne.groupby("rynek").size().items()},
        "ostateczny": _statystyka(o),
        "ostateczny_z_kursem": _statystyka(o[o.kurs.notna()]),
        "ostateczny_gwiazdka": _statystyka(o[o.gwiazdka & o.kurs.notna()]),
        "ostateczny_rynki": {k: _statystyka(g) for k, g in o.groupby("rynek")},
        # jedna predykcja na dzień: mecz z najdłuższą serią, przy równej długości – z najwyższym kursem
        "typ_dnia": _statystyka(o.sort_values(["data", "najdl", "kurs_sort"]).groupby("data").tail(1)
                                .pipe(lambda d: d[d.kurs.notna()])),
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
