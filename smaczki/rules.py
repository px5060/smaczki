"""Smaczki: serie 1X2 w pojedynkach pary (u gospodarza i wszystkie mecze), karta pary i ranking."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C


@dataclass(order=True)
class Fakt:
    waga: float
    tekst: str
    szansa: float | None = field(default=None, compare=False)  # szansa na taką serię (None = nie dotyczy)
    typ: str | None = field(default=None, compare=False)       # zakład zgodny z serią: 1, X, 2, 1X, X2, 12
    regula: str | None = field(default=None, compare=False)    # np. "u:nieP" (układ:seria) – do statystyk typów
    n: int = field(default=0, compare=False)                   # długość serii


@dataclass(frozen=True)
class Zakres:
    """Zakres danych kraju w tekstach smaczków.

    w     – dopisek, gdy w danych są tylko niektóre poziomy ligowe kraju ("w 1. lidze");
            "" = wszystkie poziomy ligowe kraju (Anglia: 4 poziomy),
    pelna – archiwum ma całą historię tych rozgrywek: wolno pisać „nigdy”; inaczej (wycinek historii) seria od
            pierwszego meczu w danych to „w żadnym z N meczów od X r. (dane od X)”, a jej waga jest obniżona,
    od    – {poziom: pierwszy sezon w danych}.
    """
    w: str = ""
    pelna: bool = True
    od: tuple = ()  # ((poziom, sezon), …)

    def dane_od(self, poziom=None):
        od = dict(self.od)
        return od.get(poziom, min(od.values()) if od else None)

    @property
    def opis(self):
        """Krótki opis zakresu do bilansów i tabel ("" dla pełnej historii wszystkich poziomów)."""
        czesci = [self.w] if self.w else []
        if not self.pelna:
            czesci.append(f"dane od {self.dane_od()}")
        return ", ".join(czesci)


ANGLIA = Zakres()


def zakres_kraju(kraj, poziomy=None):
    """Zakres dla kraju z config.KRAJE i włączonych poziomów."""
    k = C.KRAJE[kraj]
    wszystkie = tuple(sorted({t for _, t, _ in k.ligi.values()}))
    poziomy = tuple(sorted(poziomy)) if poziomy else wszystkie
    if poziomy in k.w:
        w = k.w[poziomy]
    elif len(poziomy) == 1:
        w = f"na {poziomy[0]}. poziomie ligowym"
    else:
        w = "na poziomach " + ", ".join(map(str, poziomy))
    return Zakres(w, k.pelna, tuple((t, k.od_poziomu.get(t, k.od)) for t in poziomy))


# Zakład zgodny z serią (perspektywa gospodarza nadchodzącego meczu): seria trwa dalej.
TYP_ZAKLADU = {"W": "1", "R": "X", "P": "2", "nieP": "1X", "nieW": "X2", "nieR": "12",
               "O": "O2.5", "U": "U2.5", "B": "BTTS", "nB": "noBTTS"}  # + "S": "Sa:b" (dokładny wynik)


TYPY_1X2 = ("1", "X", "2", "1X", "X2", "12")


@dataclass
class TypWspolny:
    """Jeden typ meczu na danym rynku: część wspólna typów ze wszystkich serii (None = serie się wykluczają)."""
    rynek: str          # "1X2", "gole" (over/under 2.5), "BTTS", "wynik" (dokładny wynik)
    typ: str | None
    skladowe: list      # typy z poszczególnych serii, np. ["X", "X2", "1X"]
    sila: float = 0.0   # waga najmocniejszej serii za tym typem
    najdluzsza: int = 0  # liczba meczów najdłuższej serii za tym typem
    regula: str = None   # dla ostatecznego typu: reguła serii (np. "u:nieP") – do statystyk z przeszłości
    fakt: object = None  # dla ostatecznego typu: seria (Fakt), z której pochodzi

    @property
    def klucz(self):
        return "wynik" if self.rynek == "wynik" else f"{self.rynek}:{self.typ}"


def typy_wspolne(fakty):
    """Typ meczu na każdym rynku, na którym są serie. 1X2: część wspólna wyników dopuszczanych przez serie
    (np. X ∩ X2 ∩ 1X = X); pozostałe rynki: typ, jeśli wszystkie serie wskazują to samo."""
    out = []
    f1x2 = [f for f in fakty if f.typ in TYPY_1X2]
    if f1x2:
        wspolne = set("1X2")
        for f in f1x2:
            wspolne &= set(f.typ)
        out.append(TypWspolny("1X2", "".join(c for c in "1X2" if c in wspolne) or None, [f.typ for f in f1x2],
                              max(f.waga for f in f1x2), max(f.n for f in f1x2)))
    for rynek, nalezy in [("gole", lambda t: t in ("O2.5", "U2.5")), ("BTTS", lambda t: t in ("BTTS", "noBTTS")),
                          ("wynik", lambda t: t.startswith("S"))]:
        ff = [f for f in fakty if f.typ and nalezy(f.typ)]
        if ff:
            z = [f.typ for f in ff]
            out.append(TypWspolny(rynek, z[0] if len(set(z)) == 1 else None, z, max(f.waga for f in ff),
                                  max(f.n for f in ff)))
    return out


def kurs_typu(kursy, typ):
    """Kurs typu albo None (podwójna szansa wyliczana z kursów 1X2)."""
    if not kursy:
        return None
    if typ in kursy:
        return kursy[typ]
    if typ in ("1X", "X2", "12") and all(c in kursy for c in "1X2"):
        # podwójna szansa z kursów 1X2: prawdopodobieństwa bez marży + połowa marży (jak na rynku 2-wynikowym)
        suma = sum(1.0 / kursy[c] for c in "1X2")
        p = (1.0 / kursy[typ[0]] + 1.0 / kursy[typ[1]]) / suma
        return max(1.01, 1.0 / (p + (suma - 1.0) / 2))
    return None


def klucz_wyboru(t, kursy):
    """Kolejność wyboru ostatecznego typu: najdłuższa seria, potem najwyższy kurs."""
    return (t.najdluzsza, kurs_typu(kursy, t.typ) or 0.0)


def typ_ostateczny(fakty, kursy=None):
    """Jeden typ na mecz: typ najdłuższej serii (najwięcej meczów z rzędu), przy równej długości – ten z najwyższym
    kursem; dokładny wynik tylko, gdy nie ma innych serii. None, gdy brak serii z typem."""
    kolejnosc = {"1X2": 0, "gole": 1, "BTTS": 2, "wynik": 3}
    z_typem = [f for f in fakty if f.typ]
    glowne = [f for f in z_typem if rynek_typu(f.typ) != "wynik"] or z_typem
    if not glowne:
        return None
    f = max(glowne, key=lambda f: (f.n, kurs_typu(kursy, f.typ) or 0.0, -kolejnosc[rynek_typu(f.typ)], f.waga))
    return TypWspolny(rynek_typu(f.typ), f.typ, [f.typ], f.waga, f.n, regula=f.regula, fakt=f)


def rynek_typu(typ):
    if typ in TYPY_1X2:
        return "1X2"
    if typ in ("O2.5", "U2.5"):
        return "gole"
    if typ in ("BTTS", "noBTTS"):
        return "BTTS"
    return "wynik"


def typ_serii(s):
    return f"S{s.wynik[0]}:{s.wynik[1]}" if s.typ == "S" else TYP_ZAKLADU[s.typ]


def fmt(d):
    return pd.Timestamp(d).strftime("%d.%m.%Y")


def odmiana(n, jeden, dwa, piec):
    """Polska odmiana liczebników: 1 mecz, 2 mecze, 5 meczów, 22 mecze, 112 meczów."""
    n = int(n)
    if n == 1:
        return f"1 {jeden}"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} {dwa}"
    return f"{n} {piec}"


def mecze(n):
    return odmiana(n, "mecz", "mecze", "meczów")


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


# ---------- serie 1X2 ----------

# Bieżące serie (od ostatniego meczu wstecz) z perspektywy wybranej drużyny: W = wygrana, R = remis, P = porażka.
TYPY = {"W": "W", "R": "R", "P": "P", "nieP": "WR", "nieW": "RP", "nieR": "WP"}
# Seria ogólna jest pomijana, gdy tak samo długa jest seria szczegółowa w niej zawarta
# (np. "bez porażki w 6" przy "6 wygranych z rzędu") – z wyjątkiem "nigdy nie wygrał".
ZAWIERA = {"nieP": "WR", "nieW": "RP", "nieR": "WP"}

# Serie bramkowe: O = co najmniej 3 gole (over 2.5), U = najwyżej 2 (under 2.5), B = obie strzeliły,
# nB = co najmniej jedna bez gola, S = ten sam dokładny wynik.
TYPY_BRAMEK = ("O", "U", "B", "nB")

_STAWKI = {}
_WYNIKI = {}  # id(stawki) -> {(sezon, gole gosp., gole gości): odsetek}; poza .attrs, bo pandas kopiuje attrs


def stawki_sezonow(hist):
    """Odsetki w każdym sezonie (4 ligi razem): 1, X, 2, O (over 2.5), B (obie strzeliły).
    Odsetki dokładnych wyników: wyniki_sezonow(stawki)."""
    klucz = (id(hist), len(hist))
    if klucz not in _STAWKI:
        if len(_STAWKI) > 16:
            _STAWKI.clear()
        hg, vg = hist.hgoal.to_numpy(), hist.vgoal.to_numpy()
        z = np.sign(hg - vg)
        df = pd.DataFrame({"s": hist.Season.to_numpy(), "1": z > 0, "X": z == 0, "2": z < 0,
                           "O": hg + vg >= 3, "B": (hg > 0) & (vg > 0), "hg": hg, "vg": vg})
        st = df.groupby("s")[["1", "X", "2", "O", "B"]].mean()
        ile = df.groupby("s").size()
        wyn = df.groupby(["s", "hg", "vg"]).size()
        if len(_WYNIKI) > 16:
            _WYNIKI.clear()
        _WYNIKI[id(st)] = (wyn / wyn.index.get_level_values(0).map(ile).to_numpy()).to_dict()
        _STAWKI[klucz] = st
    return _STAWKI[klucz]


def wyniki_sezonow(stawki):
    return _WYNIKI.get(id(stawki), {})


@dataclass
class Seria:
    typ: str
    n: int             # długość serii
    rzadkosc: float    # -log10 szansy na taką serię przy przeciętnych wynikach sezonów, w których grano
    pierwszy: object   # pierwszy mecz serii (wiersz historii)
    przerwal: object   # ostatni mecz przed serią (z innym wynikiem); None = seria obejmuje całą historię
    wszystkie: int     # liczba meczów w tym układzie
    ogolna: object = None  # tak samo długa seria ogólna wchłonięta przez tę (np. "bez wygranej gościa")
    wynik: tuple = None    # dla serii "S": powtarzający się wynik (gole drużyny, gole rywala)

    @property
    def nigdy(self):
        return self.przerwal is None

    @property
    def od(self):
        """Data, od której trwa seria (ostatni mecz z innym wynikiem albo pierwszy mecz w historii)."""
        return (self.pierwszy if self.nigdy else self.przerwal).Date


def serie(df, druzyna, stawki):
    """Bieżące serie wszystkich typów z perspektywy drużyny w meczach df (chronologicznie)."""
    if not len(df):
        return {}
    dom = df.home.to_numpy() == druzyna
    hg, vg = df.hgoal.to_numpy(), df.vgoal.to_numpy()
    g, s = np.where(dom, hg, vg), np.where(dom, vg, hg)
    kod = np.where(g > s, "W", np.where(g == s, "R", "P"))
    sez = stawki.reindex(df.Season.to_numpy())
    p1, px, p2 = (sez[k].fillna(C.STAWKI_DOMYSLNE[k]).to_numpy() for k in ("1", "X", "2"))
    p = {"W": np.where(dom, p1, p2), "R": px, "P": np.where(dom, p2, p1)}
    n_all = len(kod)
    out = {}
    for typ, dozwolone in TYPY.items():
        n = 0
        while n < n_all and kod[n_all - 1 - n] in dozwolone:
            n += 1
        if n == 0:
            continue
        okno = slice(n_all - n, n_all)
        szansa = np.clip(sum(p[k][okno] for k in dozwolone), 1e-6, 1.0)
        out[typ] = Seria(typ, n, float(-np.log10(szansa).sum()), df.iloc[n_all - n],
                         df.iloc[n_all - n - 1] if n < n_all else None, n_all)
    for typ, szczegolowe in ZAWIERA.items():
        s_ = out.get(typ)
        rowna = [out[k] for k in szczegolowe if k in out and out[k].n == s_.n] if s_ else []
        if rowna and not (s_.nigdy and typ in ("nieP", "nieW")):
            rowna[0].ogolna = s_
            del out[typ]
    return out


def _od_konca(warunek):
    n = 0
    while n < len(warunek) and warunek[len(warunek) - 1 - n]:
        n += 1
    return n


def serie_bramek(df, druzyna, stawki):
    """Bieżące serie bramkowe w meczach df: over/under 2.5, obie strzeliły / nie, ten sam dokładny wynik."""
    if not len(df):
        return {}
    dom = df.home.to_numpy() == druzyna
    hg, vg = df.hgoal.to_numpy(), df.vgoal.to_numpy()
    sezony = df.Season.to_numpy()
    sez = stawki.reindex(sezony)
    p_o = sez["O"].fillna(C.STAWKI_DOMYSLNE["O"]).to_numpy()
    p_b = sez["B"].fillna(C.STAWKI_DOMYSLNE["B"]).to_numpy()
    btts = (hg > 0) & (vg > 0)
    warunki = {"O": (hg + vg >= 3, p_o), "U": (hg + vg <= 2, 1 - p_o), "B": (btts, p_b), "nB": (~btts, 1 - p_b)}
    g, s = np.where(dom, hg, vg), np.where(dom, vg, hg)  # wynik z perspektywy drużyny
    wynik = (int(g[-1]), int(s[-1]))
    wyniki_st = wyniki_sezonow(stawki)
    p_wyn = np.array([wyniki_st.get((se, a, b) if d else (se, b, a), C.WYNIK_DOMYSLNY)
                      for se, d, a, b in zip(sezony, dom, g, s)])
    warunki["S"] = ((g == wynik[0]) & (s == wynik[1]), p_wyn)
    n_all = len(hg)
    out = {}
    for typ, (war, p) in warunki.items():
        n = _od_konca(war)
        if n == 0:
            continue
        szansa = np.clip(p[n_all - n:], 1e-6, 1.0)
        out[typ] = Seria(typ, n, float(-np.log10(szansa).sum()), df.iloc[n_all - n],
                         df.iloc[n_all - n - 1] if n < n_all else None, n_all,
                         wynik=wynik if typ == "S" else None)
    return out


def min_dlugosc(typ):
    """Najmniejsza długość serii danego rodzaju, od której jest pokazywana."""
    return {"S": C.MIN_SERIA_WYNIKU, "O": C.MIN_SERIA_GOLI, "U": C.MIN_SERIA_GOLI,
            "B": C.MIN_SERIA_GOLI, "nB": C.MIN_SERIA_GOLI}.get(typ, C.MIN_SERIA)


def warunek_serii(df, druzyna, typ, wynik=None):
    """Czy każdy mecz df spełnia warunek serii danego rodzaju (z perspektywy drużyny)."""
    dom = df.home.to_numpy() == druzyna
    hg, vg = df.hgoal.to_numpy(), df.vgoal.to_numpy()
    g, s = np.where(dom, hg, vg), np.where(dom, vg, hg)
    if typ in TYPY:
        kod = np.where(g > s, "W", np.where(g == s, "R", "P"))
        return np.isin(kod, list(TYPY[typ]))
    if typ == "O":
        return hg + vg >= 3
    if typ == "U":
        return hg + vg <= 2
    if typ in ("B", "nB"):
        btts = (hg > 0) & (vg > 0)
        return btts if typ == "B" else ~btts
    if typ == "S":
        return (g == wynik[0]) & (s == wynik[1])
    raise ValueError(typ)


def przebieg_serii(df, druzyna, typ, wynik=None):
    """Serie danego rodzaju w meczach df (chronologicznie).

    Zwraca (etykiety, wcześniejsze): etykiety dla każdego meczu – "teraz" (obecna seria, do ostatniego meczu),
    "dawniej" (wcześniejsza, przerwana seria tego rodzaju o długości co najmniej progu) albo "";
    wcześniejsze – lista (data pierwszego, data ostatniego meczu, liczba meczów) od najnowszej.
    """
    war = warunek_serii(df, druzyna, typ, wynik)
    n_all = len(war)
    etykiety = [""] * n_all
    wczesniejsze = []
    i = 0
    while i < n_all:
        if not war[i]:
            i += 1
            continue
        j = i
        while j < n_all and war[j]:
            j += 1
        if j == n_all:
            etykiety[i:j] = ["teraz"] * (j - i)
        elif j - i >= min_dlugosc(typ):
            etykiety[i:j] = ["dawniej"] * (j - i)
            wczesniejsze.append((df.Date.iloc[i], df.Date.iloc[j - 1], j - i))
        i = j
    return etykiety, wczesniejsze[::-1]


# ---------- wcześniejsze (przerwane) serie pary – każdego rodzaju ----------

RODZAJE_WCZESNIEJSZYCH = ("W", "R", "P", "nieP", "nieW", "nieR", "O", "U", "B", "nB", "S")


def _szanse_meczow(df, druzyna, stawki):
    """Szansa każdego meczu df na wynik danego rodzaju (z perspektywy drużyny) przy typowych wynikach sezonu."""
    dom = df.home.to_numpy() == druzyna
    sez = stawki.reindex(df.Season.to_numpy())
    p1, px, p2, p_o, p_b = (pd.to_numeric(sez[k], errors="coerce").fillna(C.STAWKI_DOMYSLNE[k]).to_numpy(dtype=float)
                            for k in ("1", "X", "2", "O", "B"))
    w, p = np.where(dom, p1, p2), np.where(dom, p2, p1)
    wyn = wyniki_sezonow(stawki)
    p_s = np.array([wyn.get((se, a, b), C.WYNIK_DOMYSLNY)
                    for se, a, b in zip(df.Season.to_numpy(), df.hgoal.to_numpy(), df.vgoal.to_numpy())], dtype=float)
    return {"W": w, "R": px, "P": p, "nieP": w + px, "nieW": px + p, "nieR": w + p,
            "O": p_o, "U": 1 - p_o, "B": p_b, "nB": 1 - p_b, "S": p_s}


def _opis_wczesniejszej(typ, n, h, v, uklad, wynik=None):
    u = uklad == "u"
    if typ == "S":
        a, b = wynik
        sc = f"{a}:{b}" if a == b or u else (f"{a}:{b} dla {h}" if a > b else f"{b}:{a} dla {v}")
        return f"ten sam wynik {sc} {n} razy z rzędu"
    return {
        "W": f"{h} wygrał u siebie {n} razy z rzędu" if u else f"{h} wygrał {n} razy z rzędu",
        "P": f"{v} wygrał u {h} {n} razy z rzędu" if u else f"{v} wygrał {n} razy z rzędu",
        "R": f"{remisy(n)} z rzędu",
        "nieP": f"{v} bez wygranej u {h} – {mecze(n)}" if u else f"{v} bez wygranej z {h} – {mecze(n)}",
        "nieW": f"{h} bez wygranej u siebie – {mecze(n)}" if u else f"{h} bez wygranej z {v} – {mecze(n)}",
        "nieR": f"bez remisu – {mecze(n)}",
        "O": f"powyżej 2.5 bramki {n} razy z rzędu", "U": f"poniżej 2.5 bramki {n} razy z rzędu",
        "B": f"obie strzelały {n} razy z rzędu", "nB": f"co najmniej jedna bez gola {n} razy z rzędu",
    }[typ]


def serie_wczesniejsze(df, h, v, stawki, uklad="u"):
    """Przerwane serie pary w meczach df (chronologicznie) – każdego rodzaju, nie tylko jak obecny smaczek –
    które w chwili przerwania spełniały próg smaczka (długość od progu i rzadkość, albo „bez wygranej” od 10 lat
    i od 5 meczów). Ta sama seria szczegółowa i ogólna (np. 5 wygranych = 5 bez porażki) – tylko szczegółowa.
    Zwraca listę od najnowszej: {"typ", "od", "do" (daty pierwszego i ostatniego meczu), "n", "indeksy", "tekst"}."""
    n_all = len(df)
    if n_all < 2:
        return []
    dom = df.home.to_numpy() == h
    hg, vg = df.hgoal.to_numpy(), df.vgoal.to_numpy()
    g, sc = np.where(dom, hg, vg), np.where(dom, vg, hg)
    szanse = _szanse_meczow(df, h, stawki)
    daty = df.Date.to_numpy()
    znalezione = {}
    for typ in RODZAJE_WCZESNIEJSZYCH:
        if typ == "S":  # ten sam dokładny wynik z rzędu
            klucze = list(zip(g, sc))
            war = None
        else:
            war = warunek_serii(df, h, typ)
        i = 0
        while i < n_all:
            if typ == "S":
                j = i + 1
                while j < n_all and klucze[j] == klucze[i]:
                    j += 1
            else:
                if not war[i]:
                    i += 1
                    continue
                j = i
                while j < n_all and war[j]:
                    j += 1
            n = j - i
            if j < n_all and n >= min_dlugosc(typ):  # przerwana (nie obecna) i od progu długości
                rzadkosc = float(-np.log10(np.clip(szanse[typ][i:j], 1e-6, 1.0)).sum())
                od = daty[i - 1] if i > 0 else daty[i]
                lata = _lata(od, daty[j])
                if rzadkosc >= C.MIN_RZADKOSC or (typ in ("nieP", "nieW") and n >= C.MIN_MECZOW_OD_LAT
                                                   and lata >= C.MIN_LAT_BEZ_WYGRANEJ):
                    znalezione[(typ, i, j)] = (int(g[i]), int(sc[i])) if typ == "S" else None
            i = j
    for (typ, i, j) in list(znalezione):  # 5 wygranych = 5 bez porażki: zostaje szczegółowa
        if typ in ZAWIERA and any((k, i, j) in znalezione for k in ZAWIERA[typ]):
            del znalezione[(typ, i, j)]
    out = []
    for (typ, i, j), wynik in znalezione.items():
        out.append({"typ": typ, "od": df.Date.iloc[i], "do": df.Date.iloc[j - 1], "n": j - i,
                    "indeksy": list(df.index[i:j]), "tekst": _opis_wczesniejszej(typ, j - i, h, v, uklad, wynik)})
    return sorted(out, key=lambda x: (x["do"], x["n"]), reverse=True)


def _istotna(s, ref):
    min_n = min_dlugosc(s.typ)
    if s.n >= min_n and s.rzadkosc >= C.MIN_RZADKOSC:
        return True
    # "nie wygrał od X r." / "nigdy nie wygrał" – także przy mniejszej rzadkości, jeśli trwa długo
    if s.typ in ("nieP", "nieW") and s.n >= C.MIN_MECZOW_OD_LAT and _lata(s.od, ref) >= C.MIN_LAT_BEZ_WYGRANEJ:
        return True
    return False


def _waga(s, ref, z=ANGLIA):
    w = C.WAGA_RZADKOSCI * s.rzadkosc + C.BONUS_ZA_ROK * min(_lata(s.od, ref), C.MAKS_LAT_BONUSU)
    return w * C.WAGA_WYCINKA if _wycinek(s, z) else w


def _wycinek(s, z):
    """Seria obejmuje wszystkie mecze pary w danych, a dane to tylko wycinek historii (nie wiemy, co było wcześniej)."""
    return s.nigdy and not z.pelna


def _L(z):
    return f" {z.w}" if z.w else ""


def _od_danych(s, z):
    return f"dane od {z.dane_od(getattr(s.pierwszy, 'tier', None))}"


def _zadnym(n, z):
    """„w żadnym z 45 meczów ligowych” (bez „ligowych”, gdy jest dopisek zakresu)."""
    return f"w żadnym z {int(n)} meczów{'' if z.w else ' ligowych'}"


def remisy(n):
    return odmiana(n, "remis", "remisy", "remisów")


def _wynik(r, z_nazwami=False):
    return f"{r.home} – {r.visitor} {r.hgoal}:{r.vgoal}" if z_nazwami else f"{r.hgoal}:{r.vgoal}"


def _dopisek(s, h, v, h2h=False, z=ANGLIA):
    """Dla serii, która wchłonęła tak samo długą serię "bez wygranej": od kiedy przegrywający nie wygrał."""
    g = s.ogolna
    if g is None or g.nigdy or g.typ == "nieR":
        return ""
    r = g.przerwal
    kto, komu = (v, h) if g.typ == "nieP" else (h, v)
    if h2h:
        return f" {kto} nie wygrał z {komu}{_L(z)} od {r.Date.year} r. (ostatnio {fmt(r.Date)}, {_wynik(r, True)})."
    gdzie = f"u {h}" if g.typ == "nieP" else f"u siebie z {v}"
    return f" {kto} nie wygrał{_L(z)} {gdzie} od {r.Date.year} r. (ostatnio {fmt(r.Date)}, {_wynik(r)})."


def _od(s, z, nawias=""):
    """Końcówka serii: „ – wszystkie mecze od 1907 r.” albo „ (od 1990 r.).”; przy wycinku z zastrzeżeniem.
    nawias – dodatkowy opis do nawiasu (np. „u siebie i na wyjeździe”)."""
    rok = s.pierwszy.Date.year
    if s.nigdy:
        pocz = f" ({nawias}) – wszystkie mecze od {rok} r." if nawias else f" – wszystkie mecze od {rok} r."
        return pocz + (f" ({_od_danych(s, z)})." if _wycinek(s, z) else "")
    return f" ({nawias}, od {rok} r.)." if nawias else f" (od {rok} r.)."


def _tekst_u_gospodarza(s, h, v, z=ANGLIA):
    """Mecze h (gospodarz) z v na boisku h."""
    n, rok, L = s.n, s.pierwszy.Date.year, _L(z)
    od = _od(s, z) + _dopisek(s, h, v, z=z)
    if s.typ == "W":
        return f"{h} wygrał u siebie z {v} {n} razy z rzędu{L}{od}"
    if s.typ == "P":
        return f"{v} wygrał u {h} {n} razy z rzędu{L}{od}"
    if s.typ == "R":
        return f"{remisy(n)} z rzędu w meczach u {h} z {v}{L}{od}"
    if s.nigdy and not z.pelna:  # wycinek historii: bez „nigdy”
        dane = _od_danych(s, z)
        return {"nieP": f"{v} nie wygrał{L} u {h} {_zadnym(n, z)} od {rok} r. ({dane}).",
                "nieW": f"{h} nie wygrał{L} u siebie z {v} {_zadnym(n, z)} od {rok} r. ({dane}).",
                "nieR": f"Żaden z {int(n)} meczów u {h} z {v}{L} od {rok} r. nie skończył się remisem ({dane})."}[s.typ]
    if s.nigdy:
        ligowo = z.w or "ligowo"
        return {"nieP": f"{v} NIGDY nie wygrał {ligowo} u {h} ({mecze(n)} od {rok} r.).",
                "nieW": f"{h} NIGDY nie wygrał {ligowo} u siebie z {v} ({mecze(n)} od {rok} r.).",
                "nieR": f"Mecze u {h} z {v}{L} nigdy nie skończyły się remisem ({mecze(n)} od {rok} r.)."}[s.typ]
    r = s.przerwal
    ost = f"{fmt(r.Date)}, {_wynik(r)}"
    return {"nieP": f"{v} nie wygrał{L} u {h} od {r.Date.year} r. ({mecze(n)}) – ostatnio {ost}.",
            "nieW": f"{h} nie wygrał{L} u siebie z {v} od {r.Date.year} r. ({mecze(n)}) – ostatnio {ost}.",
            "nieR": f"Bez remisu w meczach u {h} z {v}{L} od {r.Date.year} r. ({mecze(n)}) – ostatni remis {ost}."}[s.typ]


def _tekst_h2h(s, h, v, z=ANGLIA):
    """Wszystkie mecze ligowe obu drużyn (u siebie i na wyjeździe)."""
    n, rok, L = s.n, s.pierwszy.Date.year, _L(z)
    od = _od(s, z) + _dopisek(s, h, v, h2h=True, z=z)
    gdzie = "u siebie i na wyjeździe"
    if s.typ == "W":
        return f"{h} wygrał z {v} {n} razy z rzędu{L}, {gdzie}{od}"
    if s.typ == "P":
        return f"{v} wygrał z {h} {n} razy z rzędu{L}, {gdzie}{od}"
    if s.typ == "R":
        return f"{remisy(n)} z rzędu w meczach {h} z {v}{L}, {gdzie}{od}"
    if s.nigdy and not z.pelna:  # wycinek historii: bez „nigdy”
        dane = _od_danych(s, z)
        return {"nieP": f"{v} nie wygrał z {h}{L} {_zadnym(n, z)} od {rok} r. ({gdzie}; {dane}).",
                "nieW": f"{h} nie wygrał z {v}{L} {_zadnym(n, z)} od {rok} r. ({gdzie}; {dane}).",
                "nieR": f"{h} i {v} nie zremisowali{L} {_zadnym(n, z)} od {rok} r. ({dane})."}[s.typ]
    if s.nigdy:
        wlidze = z.w or "w lidze"
        return {"nieP": f"{v} NIGDY nie wygrał z {h} {wlidze} ({mecze(n)} od {rok} r., {gdzie}).",
                "nieW": f"{h} NIGDY nie wygrał z {v} {wlidze} ({mecze(n)} od {rok} r., {gdzie}).",
                "nieR": f"{h} i {v} nigdy nie zremisowali {wlidze} ({mecze(n)} od {rok} r.)."}[s.typ]
    r = s.przerwal
    ost = f"{fmt(r.Date)}, {_wynik(r, True)}"
    return {"nieP": f"{v} nie wygrał z {h}{L} od {r.Date.year} r. ({mecze(n)}, {gdzie}) – ostatnio {ost}.",
            "nieW": f"{h} nie wygrał z {v}{L} od {r.Date.year} r. ({mecze(n)}, {gdzie}) – ostatnio {ost}.",
            "nieR": f"Bez remisu w meczach {h} z {v}{L} od {r.Date.year} r. ({mecze(n)}, {gdzie}) – "
                    f"ostatni remis {ost}."}[s.typ]


def _tekst_bramek(s, h, v, h2h=False, z=ANGLIA):
    """Serie bramkowe w meczach u gospodarza (h2h=False) albo we wszystkich meczach pary."""
    n, L = s.n, _L(z)
    if h2h:
        gdzie = f"między {h} a {v}{L}"
        od = _od(s, z, "u siebie i na wyjeździe")
    else:
        gdzie = f"u {h} z {v}{L}"
        od = _od(s, z)
    if s.typ == "S":
        a, b = s.wynik
        if not h2h or a == b:
            wynik = f"{a}:{b}"
        else:
            wynik = f"{a}:{b} dla {h}" if a > b else f"{b}:{a} dla {v}"
        return f"Ten sam wynik {wynik} w {meczach(n)} z rzędu {gdzie}{od}"
    co = {"O": "Powyżej 2.5 bramki (over)", "U": "Poniżej 2.5 bramki (under)",
          "B": "Obie drużyny strzelały", "nB": "Co najmniej jedna drużyna bez gola (BTTS nie)"}[s.typ]
    return f"{co} w {meczach(n)} z rzędu {gdzie}{od}"


def smaczki(hist, h, v, ref=None, zakres=ANGLIA):
    """Lista Fakt (najciekawsze pierwsze) dla meczu h (gospodarz) – v (gość). Tylko pojedynki tej pary.

    Bieżące serie 1, X, 2 oraz "bez wygranej" (każdej ze stron) i "bez remisu" w dwóch układach:
    mecze u gospodarza z tym rywalem i wszystkie mecze ligowe obu drużyn (u siebie i na wyjeździe).
    hist – historia ligowa sprzed meczu; ref – data meczu (do liczenia lat), domyślnie koniec historii;
    zakres – zakres danych kraju (Zakres; domyślnie Anglia: pełna historia wszystkich 4 poziomów).
    """
    ref = pd.Timestamp(ref) if ref is not None else hist.Date.max()
    h2h = hist[((hist.home == h) & (hist.visitor == v)) | ((hist.home == v) & (hist.visitor == h))]
    return fakty_pary(h2h, h, v, ref, stawki_sezonow(hist), zakres)


def pierwszy_mecz(z=ANGLIA):
    if z.pelna:
        return f"Pierwszy mecz tych drużyn {z.w} w historii." if z.w else "Pierwszy ligowy mecz tych drużyn w historii."
    return f"Pierwszy mecz tych drużyn{_L(z)} w danych (dane od {z.dane_od()})."


def fakty_pary(h2h, h, v, ref, st, zakres=ANGLIA):
    """Smaczki z samych meczów pary (h2h: chronologicznie, sprzed meczu); st – odsetki 1X2 sezonów."""
    out = []
    z = zakres
    boisko = h2h[h2h.home == h]

    if len(h2h) == 0:
        out.append(Fakt(C.WAGA_PIERWSZEGO_MECZU, pierwszy_mecz(z)))

    # wszystkie istotne serie pary: u gospodarza i we wszystkich meczach (u siebie i na wyjeździe)
    for df, tekst, uklad in [(boisko, _tekst_u_gospodarza, "u"), (h2h, _tekst_h2h, "h2h")]:
        for s in serie(df, h, st).values():
            if _istotna(s, ref):
                out.append(Fakt(_waga(s, ref, z), tekst(s, h, v, z), 10 ** -s.rzadkosc,
                                TYP_ZAKLADU[s.typ], f"{uklad}:{s.typ}", s.n))
        for s in serie_bramek(df, h, st).values():
            if _istotna(s, ref):
                out.append(Fakt(_waga(s, ref, z), _tekst_bramek(s, h, v, uklad == "h2h", z), 10 ** -s.rzadkosc,
                                typ_serii(s), f"{uklad}:{s.typ}", s.n))

    out.sort(reverse=True)
    return out


def ostatni_u_gospodarza(hist, h, v):
    boisko = hist[(hist.home == h) & (hist.visitor == v)]
    return boisko.iloc[-1] if len(boisko) else None


def wyniki_pary(hist, h, v):
    """Mecze pary, na których opierają się smaczki (od najnowszego): u gospodarza i rewanże."""
    return {
        "u_gosp": hist[(hist.home == h) & (hist.visitor == v)].iloc[::-1],
        "rewanze": hist[(hist.home == v) & (hist.visitor == h)].iloc[::-1],
    }


# ---------- tryb "mecz": pełna karta pary ----------

def _opis(r):
    return f"{r.home} – {r.visitor} {r.hgoal}:{r.vgoal} ({fmt(r.Date)}, poziom {r.tier})"


def karta_meczu(hist, h, v, ref=None, zakres=ANGLIA):
    """Pełny zestaw informacji o parze (lista linii)."""
    z = zakres
    out = []
    if z.w or not z.pelna:
        out.append(f"Zakres danych: mecze {z.w or 'ligowe wszystkich poziomów'}"
                   + ("" if z.pelna else f", tylko od {z.dane_od()} (wcześniejszej historii nie ma w danych)") + ".")
    boisko = hist[(hist.home == h) & (hist.visitor == v)]
    if len(boisko):
        w = list(wyniki(boisko, h))
        out.append(f"Mecze ligowe u {h}: {mecze(len(w))} od {boisko.Date.iloc[0].year} r. – "
                   f"{w.count('W')} wygranych gospodarzy, {remisy(w.count('R'))}, {w.count('P')} wygranych {v}.")
        wyg_g = boisko[boisko.vgoal > boisko.hgoal]
        if len(wyg_g):
            r = wyg_g.iloc[-1]
            od = int((boisko.Date > r.Date).sum())
            out.append(f"Ostatnia wygrana {v} u {h}: {fmt(r.Date)} ({r.hgoal}:{r.vgoal}); " +
                       (f"od tego czasu {mecze(od)} bez wygranej gości." if od else "to był ostatni mecz u gospodarza."))
        elif z.pelna:
            out.append(f"{v} NIGDY nie wygrał {z.w or 'ligowo'} u {h} (pierwszy mecz: {fmt(boisko.Date.iloc[0])}).")
        else:
            out.append(f"{v} nie wygrał u {h} w żadnym meczu w danych (pierwszy mecz w danych: "
                       f"{fmt(boisko.Date.iloc[0])}).")
        wyg_h = boisko[boisko.hgoal > boisko.vgoal]
        if len(wyg_h):
            r = wyg_h.iloc[-1]
            od = int((boisko.Date > r.Date).sum())
            out.append(f"Ostatnia wygrana {h} u siebie z {v}: {fmt(r.Date)} ({r.hgoal}:{r.vgoal})" +
                       (f"; od tego czasu {mecze(od)} bez wygranej." if od else "."))
        elif z.pelna:
            out.append(f"{h} NIGDY nie wygrał {z.w or 'ligowo'} u siebie z {v}.")
        else:
            out.append(f"{h} nie wygrał u siebie z {v} w żadnym meczu w danych.")
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

def ranking(hist, top=25, tier=None, min_mecze=C.RANKING_MIN_MECZOW, lat_wstecz=C.RANKING_LAT, zakres=ANGLIA):
    """Pary gospodarz–gość, w których gość najdłużej nie wygrał (pary grające ze sobą w ostatnich N latach)."""
    z = zakres
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
            if z.pelna:
                tekst = f"{v} NIGDY nie wygrał{_L(z)} u {h} ({mecze(len(g))} od {od.year} r.)"
            else:
                tekst = (f"{v} nie wygrał{_L(z)} u {h} w żadnym z {len(g)} meczów od {od.year} r. "
                         f"(dane od {z.dane_od(int(g.tier.iloc[0]))})")
        wiersze.append((_lata(od, koniec), tekst))
    wiersze.sort(reverse=True)
    return [tekst for _, tekst in wiersze[:top]]
