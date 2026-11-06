"""Reguły smaczków (brief, pkt 4), pełna karta pary (tryb "mecz") i ranking passy gości."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C


@dataclass(order=True)
class Fakt:
    waga: float
    tekst: str


def fmt(d):
    return pd.Timestamp(d).strftime("%d.%m.%Y")


def mecze(n):
    """Polska odmiana: 1 mecz, 2 mecze, 5 meczów, 22 mecze, 112 meczów."""
    n = int(n)
    if n == 1:
        return "1 mecz"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} mecze"
    return f"{n} meczów"


def meczach(n):
    """Miejscownik: w 1 meczu, w 5 meczach."""
    return "1 meczu" if int(n) == 1 else f"{int(n)} meczach"


def lat(n):
    n = int(n)
    return "roku" if n == 1 else f"{n} lat"


def wyniki(df, druzyna):
    """Tablica 'W'/'R'/'P' z perspektywy drużyny (kolejność jak w df)."""
    dom = df.home.to_numpy() == druzyna
    hg, vg = df.hgoal.to_numpy(), df.vgoal.to_numpy()
    g, s = np.where(dom, hg, vg), np.where(dom, vg, hg)
    return np.where(g > s, "W", np.where(g == s, "R", "P"))


def seria(w, warunek):
    """Długość bieżącej serii od ostatniego meczu wstecz."""
    n = 0
    for x in reversed(w):
        if not warunek(x):
            break
        n += 1
    return n


def _lata(od, ref):
    return (pd.Timestamp(ref) - pd.Timestamp(od)).days / 365.25


def smaczki(hist, h, v, ref=None):
    """Lista Fakt (najciekawsze pierwsze) dla meczu h (gospodarz) – v (gość).

    hist – historia ligowa sprzed meczu; ref – data meczu (do liczenia "od X lat"), domyślnie koniec historii.
    """
    ref = pd.Timestamp(ref) if ref is not None else hist.Date.max()
    out = []
    boisko = hist[(hist.home == h) & (hist.visitor == v)]
    h2h = hist[((hist.home == h) & (hist.visitor == v)) | ((hist.home == v) & (hist.visitor == h))]

    if len(h2h) == 0:
        out.append(Fakt(30, "Pierwszy ligowy mecz tych drużyn w historii."))
    else:
        ostatni = h2h.Date.iloc[-1]
        przerwa = _lata(ostatni, ref)
        if przerwa >= C.MIN_PRZERWA_LAT:
            out.append(Fakt(przerwa, f"Pierwszy ligowy mecz tych drużyn od {lat(przerwa)} (ostatni: {fmt(ostatni)})."))

    if len(boisko):
        w = wyniki(boisko, h)  # z perspektywy gospodarza: P = wygrana gościa
        n = len(w)

        # --- gość u tego gospodarza ---
        wyg_g = boisko[boisko.vgoal > boisko.hgoal]
        if len(wyg_g) == 0:
            if n >= C.MIN_MECZOW_GOSC_NIGDY:
                out.append(Fakt(40 + n, f"{v} NIGDY nie wygrał ligowo u {h} ({mecze(n)} od {boisko.Date.iloc[0].year} r.)."))
        else:
            r = wyg_g.iloc[-1]
            lata_ = _lata(r.Date, ref)
            ile = int((boisko.Date > r.Date).sum())
            if lata_ >= C.MIN_LAT_BEZ_WYGRANEJ and ile >= C.MIN_MECZOW_OD_WYGRANEJ:
                out.append(Fakt(lata_, f"{v} nie wygrał u {h} od {lat(lata_)} – ostatnio {fmt(r.Date)} "
                                       f"({r.hgoal}:{r.vgoal}); od tego czasu {mecze(ile)} bez wygranej."))

        bez_por = seria(w, lambda x: x != "W")
        if bez_por >= C.MIN_SERIA_GOSC_BEZ_PORAZKI:
            out.append(Fakt(4 * bez_por, f"{v} bez porażki u {h} w {bez_por} ostatnich meczach ligowych."))
        wyg_z_rzedu = seria(w, lambda x: x == "P")
        if wyg_z_rzedu >= C.MIN_SERIA_GOSC_WYGRANE:
            out.append(Fakt(6 * wyg_z_rzedu, f"{v} wygrał u {h} {wyg_z_rzedu} razy z rzędu."))

        # --- gospodarz u siebie z tym rywalem ---
        wyg_h = boisko[boisko.hgoal > boisko.vgoal]
        if len(wyg_h) == 0:
            if n >= C.MIN_MECZOW_GOSP_NIGDY:
                out.append(Fakt(35 + n, f"{h} NIGDY nie wygrał ligowo u siebie z {v} ({mecze(n)})."))
        else:
            od = wyg_h.Date.iloc[-1]
            lata_ = _lata(od, ref)
            ile = int((boisko.Date > od).sum())
            if ile >= C.MIN_MECZOW_GOSP_BEZ_WYGRANEJ or (lata_ >= C.MIN_LAT_BEZ_WYGRANEJ
                                                         and ile >= C.MIN_MECZOW_OD_WYGRANEJ):
                kiedy = f"od {lat(lata_)} – ostatnio {fmt(od)}" if lata_ >= C.MIN_LAT_BEZ_WYGRANEJ else f"od {fmt(od)}"
                out.append(Fakt(max(lata_, 4 * ile), f"{h} nie wygrał u siebie z {v} {kiedy} ({mecze(ile)})."))
        wyg_h_z_rzedu = seria(w, lambda x: x == "W")
        if wyg_h_z_rzedu >= C.MIN_SERIA_GOSP_WYGRANE:
            out.append(Fakt(3 * wyg_h_z_rzedu, f"{h} wygrał u siebie z {v} {wyg_h_z_rzedu} razy z rzędu."))

    # --- bieżąca forma (wszyscy rywale) ---
    for druz, kol, gdzie in [(h, "home", "u siebie"), (v, "visitor", "na wyjeździe")]:
        m = hist[hist[kol] == druz]
        if not len(m):
            continue
        w = wyniki(m, druz)
        for warunek, opis in [(lambda x: x != "P", "bez porażki"), (lambda x: x != "W", "bez wygranej")]:
            n = seria(w, warunek)
            if n >= C.MIN_FORMA:
                out.append(Fakt(1.5 * n, f"{druz} {opis} {gdzie} w {n} meczach ligowych z rzędu."))

    out.sort(reverse=True)
    return out


def ostatni_u_gospodarza(hist, h, v):
    boisko = hist[(hist.home == h) & (hist.visitor == v)]
    return boisko.iloc[-1] if len(boisko) else None


def wyniki_pary(hist, h, v, forma=10):
    """Mecze, na których opierają się smaczki (od najnowszego): u gospodarza, rewanże, forma obu drużyn."""
    return {
        "u_gosp": hist[(hist.home == h) & (hist.visitor == v)].iloc[::-1],
        "rewanze": hist[(hist.home == v) & (hist.visitor == h)].iloc[::-1],
        "forma_h": hist[hist.home == h].tail(forma).iloc[::-1],
        "forma_v": hist[hist.visitor == v].tail(forma).iloc[::-1],
    }


# ---------- tryb "mecz": pełna karta pary ----------

def _opis(r):
    return f"{r.home} – {r.visitor} {r.hgoal}:{r.vgoal} ({fmt(r.Date)}, poziom {r.tier})"


def karta_meczu(hist, h, v, ref=None):
    """Pełny zestaw informacji o parze (lista linii)."""
    out = []
    boisko = hist[(hist.home == h) & (hist.visitor == v)]
    if len(boisko):
        w = list(wyniki(boisko, h))
        out.append(f"Mecze ligowe u {h}: {mecze(len(w))} od {boisko.Date.iloc[0].year} r. – "
                   f"{w.count('W')} wygranych gospodarzy, {w.count('R')} remisów, {w.count('P')} wygranych {v}.")
        wyg_g = boisko[boisko.vgoal > boisko.hgoal]
        if len(wyg_g):
            r = wyg_g.iloc[-1]
            od = int((boisko.Date > r.Date).sum())
            out.append(f"Ostatnia wygrana {v} u {h}: {fmt(r.Date)} ({r.hgoal}:{r.vgoal}); " +
                       (f"od tego czasu {mecze(od)} bez wygranej gości." if od else "to był ostatni mecz u gospodarza."))
        else:
            out.append(f"{v} NIGDY nie wygrał ligowo u {h} (pierwszy mecz: {fmt(boisko.Date.iloc[0])}).")
        wyg_h = boisko[boisko.hgoal > boisko.vgoal]
        if len(wyg_h):
            r = wyg_h.iloc[-1]
            od = int((boisko.Date > r.Date).sum())
            out.append(f"Ostatnia wygrana {h} u siebie z {v}: {fmt(r.Date)} ({r.hgoal}:{r.vgoal})" +
                       (f"; od tego czasu {mecze(od)} bez wygranej." if od else "."))
        else:
            out.append(f"{h} NIGDY nie wygrał ligowo u siebie z {v}.")
        for war, opis in [(lambda x: x != "P", f"{h} bez porażki u siebie z {v}"),
                          (lambda x: x == "W", f"{h} wygrywa u siebie z {v}"),
                          (lambda x: x != "W", f"{v} bez porażki u {h}"),
                          (lambda x: x == "P", f"{v} wygrywa u {h}")]:
            n = seria(w, war)
            if n >= 2:
                out.append(f"Seria: {opis} w {meczach(n)} z rzędu.")
        bramki = boisko.hgoal + boisko.vgoal
        out.append(f"Średnio {bramki.mean():.2f} gola na mecz u {h}; 0:0 w {meczach((bramki == 0).sum())}.")
        roznica = boisko.hgoal - boisko.vgoal
        if roznica.max() > 0:
            out.append(f"Najwyższa wygrana {h} u siebie: {_opis(boisko.loc[roznica.idxmax()])}.")
        if roznica.min() < 0:
            out.append(f"Najwyższa wygrana {v} u {h}: {_opis(boisko.loc[roznica.idxmin()])}.")
        out.append(f"Ostatni mecz u {h}: {_opis(boisko.iloc[-1])}.")
    else:
        out.append(f"{v} nigdy nie grał ligowo u {h} (w tych danych).")

    h2h = hist[((hist.home == h) & (hist.visitor == v)) | ((hist.home == v) & (hist.visitor == h))]
    if len(h2h):
        w = list(wyniki(h2h, h))
        out.append(f"Bilans wszystkich meczów ligowych: {h} {w.count('W')}–{w.count('R')}–{w.count('P')} {v} "
                   f"({mecze(len(w))} od {h2h.Date.iloc[0].year} r.).")
        for war, opis in [(lambda x: x != "W", f"{h} bez wygranej z {v}"),
                          (lambda x: x != "P", f"{h} bez porażki z {v}")]:
            n = seria(w, war)
            if n >= 4:
                out.append(f"{opis} w {n} ostatnich meczach.")

    for druz, kol, gdzie in [(h, "home", "u siebie"), (v, "visitor", "na wyjeździe")]:
        m = hist[hist[kol] == druz].tail(10)
        if len(m):
            forma = "".join(wyniki(m, druz)).replace("W", "W ").replace("R", "R ").replace("P", "P ").strip()
            out.append(f"Forma {druz} {gdzie} (ostatnie {len(m)}, od najstarszego): {forma}")
    return out


# ---------- ranking: najdłuższe passy gości bez wygranej ----------

def ranking(hist, top=25, tier=None, min_mecze=C.RANKING_MIN_MECZOW, lat_wstecz=C.RANKING_LAT):
    """Pary gospodarz–gość, w których gość najdłużej nie wygrał (pary grające ze sobą w ostatnich N latach)."""
    koniec = hist.Date.max()
    granica = koniec - pd.Timedelta(days=int(lat_wstecz * 365.25))
    h2h_ostatni = {}
    for (a, b), d in hist.groupby(["home", "visitor"]).Date.max().items():
        klucz = tuple(sorted((a, b)))
        h2h_ostatni[klucz] = max(h2h_ostatni.get(klucz, d), d)
    wiersze = []
    for (h, v), g in hist.groupby(["home", "visitor"], sort=False):
        if len(g) < min_mecze or h2h_ostatni[tuple(sorted((h, v)))] < granica:
            continue
        if tier is not None and g.tier.iloc[-1] != tier:
            continue
        wyg = g[g.vgoal > g.hgoal]
        if len(wyg):
            od = wyg.Date.iloc[-1]
            meczow = int((g.Date > od).sum())
            tekst = f"{v} nie wygrał u {h} od {lat(_lata(od, koniec))} ({mecze(meczow)}; ostatnio {fmt(od)})"
        else:
            od = g.Date.iloc[0]
            tekst = f"{v} NIGDY nie wygrał u {h} ({mecze(len(g))} od {od.year} r.)"
        wiersze.append((_lata(od, koniec), tekst))
    wiersze.sort(reverse=True)
    return [tekst for _, tekst in wiersze[:top]]
