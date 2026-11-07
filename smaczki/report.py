"""Raporty: tekst (konsola / plik), strona HTML na telefon i treść powiadomienia."""
import datetime as dt
import html
from dataclasses import dataclass, field

import pandas as pd

from . import config as C
from .rules import (TypWspolny, fmt, klucz_wyboru, kurs_typu, mecze, odmiana, przebieg_serii, rynek_typu,
                    serie_wczesniejsze, typ_ostateczny, typy_wspolne)

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
DNI_KROTKO = ["pn", "wt", "śr", "czw", "pt", "sob", "nd"]
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
            "września", "października", "listopada", "grudnia"]


@dataclass
class Pozycja:
    data: dt.datetime | None
    liga: str
    h: str
    v: str
    fakty: list
    ostatni: object = None  # ostatni mecz u gospodarza (wiersz historii) albo None
    wyniki: dict = None     # mecze do podglądu (rules.wyniki_pary)
    kursy: tuple = None     # aktualne średnie kursy (1, X, 2), jeśli są
    kraj: str = C.KRAJ_DOMYSLNY
    zakres: object = None   # rules.Zakres – zakres danych kraju (None = Anglia: pełna historia 4 poziomów)
    stawki: object = None   # odsetki wyników sezonów (rules.stawki_sezonow) – do wcześniejszych serii pary
    _wcz: dict = field(default_factory=dict, repr=False, compare=False)

    def mecze_ukladu(self, uklad):
        """Mecze pary chronologicznie: "u" – u gospodarza, "h2h" – wszystkie (u siebie i na wyjeździe)."""
        if not self.wyniki:
            return None
        u, rew = self.wyniki["u_gosp"], self.wyniki["rewanze"]
        return u.iloc[::-1] if uklad == "u" else pd.concat([u, rew]).sort_values("Date", kind="stable")

    def wczesniejsze(self, uklad):
        """Przerwane serie pary każdego rodzaju, które spełniały próg smaczka (rules.serie_wczesniejsze)."""
        if uklad not in self._wcz:
            df = self.mecze_ukladu(uklad)
            st = self.stawki if self.stawki is not None else pd.DataFrame(columns=["1", "X", "2", "O", "B"], dtype=float)
            self._wcz[uklad] = [] if df is None else serie_wczesniejsze(df, self.h, self.v, st, uklad)
        return self._wcz[uklad]

    @property
    def waga(self):
        return self.fakty[0].waga if self.fakty else 0

    @property
    def dluga_historia(self):
        return self.waga >= C.PROG_DNIA

    @property
    def ma_serie(self):
        """Czy w meczu jest jakaś seria (1X2, under/over, obie strzelą, dokładny wynik) – tylko takie pokazujemy."""
        return any(f.typ for f in self.fakty)

    @property
    def wspolne(self):
        return typy_wspolne(self.fakty)

    @property
    def ostateczny(self):
        return typ_ostateczny(self.fakty, self.kursy)

    @property
    def dzien(self):
        return self.data.date() if self.data else None


def termin(d):
    if d is None:
        return ""
    s = f"{DNI_KROTKO[d.weekday()]} {d:%d.%m.%Y}"
    return s + (f" {d:%H:%M}" if (d.hour, d.minute) != (0, 0) else "")


def naglowek_dnia(dzien, dzis):
    nazwa = f"{DNI[dzien.weekday()]} {dzien.day} {MIESIACE[dzien.month - 1]}"
    if dzien == dzis:
        return f"Dziś · {nazwa}"
    if dzien == dzis + dt.timedelta(days=1):
        return f"Jutro · {nazwa}"
    return nazwa[0].upper() + nazwa[1:]


def _sezony(lista):
    return ", ".join(f"{s}/{(s + 1) % 100:02d}" for s in lista)


def _opis_zakresu(p):
    return p.zakres.opis if p.zakres is not None else ""


def _ostatni_txt(p):
    if p.ostatni is None:
        if _opis_zakresu(p):
            return f"{p.v} nie grał u {p.h} w danych ({_opis_zakresu(p)})"
        return f"{p.v} jeszcze nie grał ligowo u {p.h}"
    r = p.ostatni
    return f"ostatni mecz u {p.h}: {fmt(r.Date)}, {r.hgoal}:{r.vgoal}"


def _podsumowanie(pozycje):
    ze = sum(1 for p in pozycje if p.ma_serie)
    dlugie = sum(1 for p in pozycje if p.dluga_historia)
    return (f"Meczów w terminarzu: {len(pozycje)}, z seriami (pokazane): {ze}, z długą historią (★): {dlugie}. "
            "Mecze bez żadnej serii nie są pokazywane.")


OPIS_TYPU = {"1": "wygra gospodarz", "X": "remis", "2": "wygra gość",
             "1X": "gospodarz nie przegra", "X2": "gość nie przegra", "12": "nie będzie remisu",
             "O2.5": "powyżej 2.5 bramki", "U2.5": "poniżej 2.5 bramki",
             "BTTS": "obie drużyny strzelą", "noBTTS": "co najmniej jedna nie strzeli"}
NAZWA_TYPU = {"O2.5": "Over 2.5", "U2.5": "Under 2.5", "BTTS": "BTTS tak", "noBTTS": "BTTS nie"}


def nazwa_typu(typ):
    if typ.startswith("S"):
        return f"dokładny wynik {typ[1:]}"
    return f"{NAZWA_TYPU.get(typ, typ)} ({OPIS_TYPU[typ]})"


def _procent(x):
    return f"{x * 100:+.0f}%".replace("-", "−")


RYNEK = {"1X2": "1X2", "gole": "Gole", "BTTS": "Obie strzelą", "wynik": "Wynik"}


def _krotko(typ):
    return f"wynik {typ[1:]}" if typ.startswith("S") else NAZWA_TYPU.get(typ, typ)


def typ_tekst(t, p, skut):
    """Typ meczu na rynku t (TypWspolny) z kursem i wynikiem takiego typu w przeszłości."""
    rynek = RYNEK[t.rynek]
    if t.typ is None:
        return f"{rynek}: serie się wykluczają ({', '.join(_krotko(x) for x in t.skladowe)}) – bez typu"
    czesci = [f"{rynek}: {nazwa_typu(t.typ)}"]
    if len(t.skladowe) > 1:
        rozne = list(dict.fromkeys(t.skladowe))
        czesci[0] += (f" – część wspólna serii {', '.join(_krotko(x) for x in rozne)}" if len(rozne) > 1
                      else f" – zgodny z {odmiana(len(t.skladowe), 'serią', 'seriami', 'seriami')}")
    k = kurs_typu(p.kursy, t.typ)
    if k:
        czesci.append(f"kurs ok. {k:.2f}")
    st = ((skut or {}).get("reguly") or {}).get(t.regula) if t.regula else None  # typ z jednej serii
    st = st or ((skut or {}).get("wspolne") or {}).get(t.klucz)
    if st and st.get("typow", 0) >= 30:
        typow = odmiana(st["typow"], "typ", "typy", "typów").replace(str(st["typow"]), _tys(st["typow"]), 1)
        if st.get("zwrot") is not None:
            wynik = f"zwrot {_procent(st['zwrot'])}"
        else:
            wynik = f"przeciętnie {st['przecietnie'] * 100:.0f}%, brak kursów w danych"
        czesci.append(f"w przeszłości {st['trafione'] * 100:.0f}% trafień, {wynik} ({typow} od {skut['okres'][:7]})")
    return " · ".join(czesci)


def ostateczny_tekst(p, skut):
    """Jeden typ na mecz: typ najdłuższej serii (potem najwyższy kurs) z kursem i wynikiem w przeszłości."""
    t = p.ostateczny
    if t is None:
        return ""
    czesci = [f"OSTATECZNY TYP: {nazwa_typu(t.typ)}"]
    czesci += [c for c in typ_tekst(t, p, skut).split(" · ")[1:]]
    return " · ".join(czesci)


def predykcja(pozycje, dzien=None):
    """Jedna ostateczna predykcja: mecz z najdłuższą serią, przy równej długości – z najwyższym kursem
    (opcjonalnie tylko z danego dnia). Zwraca (Pozycja, TypWspolny, Fakt – najdłuższa seria za typem) albo None."""
    kandydaci = []
    for p in pozycje:
        if dzien is not None and p.dzien != dzien:
            continue
        t = p.ostateczny
        if t is None:
            continue
        seria = t.fakt or max((f for f in p.fakty if f.typ and rynek_typu(f.typ) == t.rynek), key=lambda f: (f.n, f.waga))
        kandydaci.append((klucz_wyboru(t, p.kursy), p, t, seria))
    if not kandydaci:
        return None
    _, p, t, seria = max(kandydaci, key=lambda x: x[0])
    return p, t, seria


def typy_dnia(pozycje):
    """Ostateczne typy wszystkich meczów z serią: [(Pozycja, TypWspolny)] od najdłuższej serii
    (przy równej długości – od najwyższego kursu). Pierwszy = ostateczna predykcja dnia."""
    out = [(p, p.ostateczny) for p in pozycje if p.ostateczny is not None]
    return sorted(out, key=lambda x: klucz_wyboru(x[1], x[0].kursy), reverse=True)


def typ_linia(p, t):
    """Krótka linia typu meczu, np. „21:00 Derby County – Bolton Wanderers: 1X · kurs 1.52 · seria 16 meczów”."""
    godz = f"{p.data:%H:%M} " if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
    k = kurs_typu(p.kursy, t.typ)
    return (f"{godz}{p.h} – {p.v}: {_krotko(t.typ)}" + (f" · kurs {k:.2f}" if k else "")
            + f" · seria {mecze(t.najdluzsza)}")


def predykcja_tekst(pr, skut):
    """(nagłówek meczu, typ z kursem i historią, uzasadnienie)."""
    p, t, seria = pr
    nag = " ".join(x for x in [f"[{p.liga}]" if p.liga else "", termin(p.data), f"{p.h} – {p.v}"] if x)
    typ = ostateczny_tekst(p, skut).replace("OSTATECZNY TYP: ", "")
    st = (skut or {}).get("typ_dnia")
    hist = ""
    if st and st.get("zwrot") is not None:
        hist = (f"Taka predykcja (typ dnia z najdłuższej serii) w przeszłości: {st['trafione'] * 100:.0f}% trafień, "
                f"zwrot {_procent(st['zwrot'])} ({_tys(st['typow'])} dni od {skut['okres'][:7]}).")
    return nag, typ, f"Najdłuższa seria ({mecze(seria.n)}): {seria.tekst}", hist


def ostrzezenia(info):
    """Linie ostrzeżeń do nagłówka raportu."""
    out = []
    if info["tylko_archiwum"]:
        out.append(f"UWAGA: brak danych bieżących – historia kończy się {fmt(info['koniec'])}. "
                   "Sprawdź ręcznie mecze tych drużyn z ostatnich sezonów – passa mogła się przerwać.")
    out += info["ostrzezenia"]
    niedop = info["niedopasowane"]
    if isinstance(niedop, (set, list)):  # starszy format: same nazwy (Anglia)
        niedop = {("Anglia", "england"): {n: [] for n in niedop}} if niedop else {}
    for (nazwa, kraj), nazwy in niedop.items():
        lista = "; ".join(n + (f" (najbliższe: {', '.join(k)})" if k else "") for n, k in nazwy.items())
        out.append(f"Nazwy bez dopasowania w archiwum – {nazwa} (dopisz alias w smaczki/aliasy/{kraj}.json, "
                   f"jeśli to znany klub): {lista}")
    return out


def _kraje(info):
    """Kraje z raportu: [{"kraj", "nazwa", "ligi": [StanLigi]…}] (zgodność wstecz: sama Anglia)."""
    if info.get("kraje"):
        return info["kraje"]
    from .data_loader import StanLigi
    return [{"kraj": C.KRAJ_DOMYSLNY, "nazwa": C.KRAJE[C.KRAJ_DOMYSLNY].nazwa,
             "ligi": [StanLigi(k, n, t) for k, (n, t, _) in C.LIGI.items()]}]


def grupy(pozycje, info, puste_ligi=False):
    """Mecze pogrupowane po kraju i lidze (kolejność z config, w lidze od najciekawszego):
    [(kraj, [(nazwa ligi, [Pozycja])])]. puste_ligi – także ligi bez meczów."""
    out = []
    znane = set()
    for k in _kraje(info):
        mecze_kraju = [p for p in pozycje if p.kraj == k["kraj"]]
        znane.add(k["kraj"])
        nazwy = [st.nazwa for st in k["ligi"]]
        ligi = [(n, sorted([p for p in mecze_kraju if p.liga == n], key=lambda p: -p.waga)) for n in nazwy]
        inne = [p for p in mecze_kraju if p.liga not in nazwy]
        if inne:
            ligi.append(("Inne mecze", sorted(inne, key=lambda p: -p.waga)))
        ligi = [(n, m) for n, m in ligi if m or puste_ligi]
        if mecze_kraju or puste_ligi:
            out.append((k, ligi))
    reszta = [p for p in pozycje if p.kraj not in znane]
    if reszta:
        out.append(({"kraj": "", "nazwa": "Inne"}, [("Inne mecze", sorted(reszta, key=lambda p: -p.waga))]))
    return out


def stan_lig_txt(info):
    """Raport per liga: ostatni mecz w historii, dopisane mecze, ostrzeżenie o niezamkniętej luce."""
    linie = []
    for k in info.get("kraje") or []:
        for st in k["ligi"]:
            if st.koniec is None:
                continue
            linia = f"  {k['nazwa']} – {st.nazwa}: historia do {fmt(st.koniec)}"
            if st.dopisane:
                linia += f" · dopisano {st.dopisane} meczów ze źródła bieżącego"
            if st.ostrzezenie:
                linia += f" · UWAGA: {st.ostrzezenie}"
            linie.append(linia)
    return (["Stan danych per liga:"] + linie) if linie else []


def _mecz_txt(p, info):
    gw = "  ★" if p.dluga_historia else ""
    nag = " ".join(x for x in [f"[{p.liga}]" if p.liga else "", termin(p.data)] if x)
    linie = [f"{nag}  {p.h} – {p.v}{gw}" if nag else f"{p.h} – {p.v}{gw}", f"   ({_ostatni_txt(p)})"]
    for f in p.fakty[:C.MAKS_FAKTOW]:
        linie.append(f"   • {f.tekst}" + (f"  [{_krotko(f.typ)}]" if f.typ else ""))
    for t in p.wspolne:
        linie.append(f"   ⇒ Typ meczu – {typ_tekst(t, p, info.get('skutecznosc'))}")
    ost = ostateczny_tekst(p, info.get("skutecznosc"))
    if ost:
        linie.append(f"   ★ {ost}")
    return linie + [""]


def _predykcja_txt(pr, skut, tytul):
    nag, typ, why, hist = predykcja_tekst(pr, skut)
    return (["=" * 60, f"{tytul}: {nag}", f"   {typ}", f"   {why}"] + ([f"   {hist}"] if hist else [])
            + ["=" * 60, ""])


def _grupy_txt(pozycje, info, wszystkie):
    """Mecze pogrupowane po kraju i lidze, w grupie od najciekawszego."""
    linie = []
    wiele = len(_kraje(info)) > 1
    for k, ligi in grupy(pozycje, info):
        blok = []
        for nazwa, mecze_ligi in ligi:
            pokazane = [p for p in mecze_ligi if p.ma_serie or wszystkie]
            if pokazane:
                blok += [f"· {nazwa} ·", ""] + [x for p in pokazane for x in _mecz_txt(p, info)]
        if blok:
            linie += ([f"== {k['nazwa']} ==", ""] if wiele else []) + blok
    return linie


def raport_txt(pozycje, info, tytul, wszystkie=False, po_dniach=False):
    """Raport tekstowy pogrupowany po kraju i lidze (w grupie od najciekawszego). po_dniach: dzień po dniu
    i ostateczna predykcja każdego dnia; inaczej: jedna ostateczna predykcja na końcu."""
    skut = info.get("skutecznosc")
    linie = [f"{tytul}  (historia ligowa do {fmt(info['koniec'])}; {info['zrodlo']})"]
    if info.get("uzupelnione"):
        linie.append(f"Sezon {_sezony(info['uzupelnione'])} – brak w archiwum, uzupełniony z {info['zrodlo_biezace']}.")
    for k in info.get("kraje") or []:
        if len(info["kraje"]) > 1 and k.get("uzupelnione"):
            linie.append(f"{k['nazwa']}: sezon {_sezony(k['uzupelnione'])} – brak w archiwum, uzupełniony z "
                         f"{info['zrodlo_biezace']}.")
    linie += ostrzezenia(info)
    linie += stan_lig_txt(info)
    linie.append("")
    if po_dniach:
        for dzien in sorted({p.dzien for p in pozycje}, key=lambda d: d or dt.date.max):
            dnia = sorted([p for p in pozycje if p.dzien == dzien], key=lambda p: -p.waga)
            linie += [f"--- {DNI[dzien.weekday()]} {dzien:%d.%m.%Y} ---" if dzien else "--- bez daty ---", ""]
            linie += _grupy_txt(dnia, info, wszystkie)
            pr = predykcja(dnia)
            if pr:
                linie += _predykcja_txt(pr, skut, "OSTATECZNA PREDYKCJA DNIA")[:-2]
                linie += ["Wszystkie typy dnia (od najdłuższej serii):"]
                linie += [f"  {i}. {typ_linia(p, t)}" for i, (p, t) in enumerate(typy_dnia(dnia), 1)]
                linie += ["=" * 60, ""]
    else:
        linie += _grupy_txt(pozycje, info, wszystkie)
        pr = predykcja(pozycje)
        if pr:
            linie += _predykcja_txt(pr, skut, "OSTATECZNA PREDYKCJA")
    if not pozycje:
        linie += ["Brak meczów włączonych lig w tym okresie.", ""]
    linie.append(_podsumowanie(pozycje))
    return "\n".join(linie)


# ---------- strona HTML ----------

CSS = """
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--accent:#b4232c;--chip:#efece4;
--star:#b77900;--zebra:#f8f7f3;--ziel:#d9f2d5;--nieb:#d9e6fa}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;
--accent:#f0656d;--chip:#2b2a27;--star:#f2b443;--zebra:#252522;--ziel:#1e4426;--nieb:#1c3255}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:680px;margin:0 auto;padding:16px 16px 40px}
h1{font-size:1.5rem;margin:.2rem 0 .1rem}
.sub{color:var(--muted);font-size:.85rem;margin:0 0 .8rem}
.warn{background:#fff3cd;color:#5c4400;border-radius:10px;padding:.6rem .8rem;font-size:.85rem;margin:.5rem 0}
@media (prefers-color-scheme:dark){.warn{background:#3d3210;color:#f5e2a8}}
h2{font-size:1.05rem;margin:1.6rem 0 .6rem;padding-bottom:.3rem;border-bottom:1px solid var(--line)}
h3{font-size:.9rem;color:var(--muted);font-weight:600;margin:1.1rem 0 .3rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.8rem .9rem;margin:.6rem 0}
.card.star{border-color:var(--star);box-shadow:0 0 0 1px var(--star) inset}
.card.plain{padding:.6rem .9rem}
.card.plain .teams{font-size:1rem}
.top{display:flex;gap:.5rem;align-items:center;font-size:.8rem;color:var(--muted)}
.chip{background:var(--chip);border-radius:999px;padding:.1rem .55rem;color:var(--ink)}
.badge{margin-left:auto;color:var(--star);font-weight:600}
.teams{font-size:1.1rem;font-weight:650;margin:.35rem 0 .15rem}
.last{font-size:.8rem;color:var(--muted);margin-bottom:.35rem}
ul{margin:.2rem 0 0;padding-left:1.1rem}
li{margin:.25rem 0}
li.mocny{font-weight:600}
.tag{font-weight:500;font-size:.72rem;color:var(--muted);background:var(--chip);border-radius:6px;
padding:0 .35rem;white-space:nowrap}
.typy{background:var(--chip);border-radius:10px;padding:.5rem .65rem;margin:.55rem 0 .1rem;font-size:.82rem}
.typy b{display:block;font-size:.78rem;color:var(--muted);margin-bottom:.15rem}
.typy div{margin:.15rem 0}
.typy details.ost{margin-top:.45rem;padding-top:.4rem;border-top:1px solid var(--line);font-weight:650;color:var(--ink)}
.kal{display:flex;gap:.4rem;overflow-x:auto;padding:.2rem 0 .5rem;margin:.6rem 0 .2rem;-webkit-overflow-scrolling:touch}
.kal button{flex:0 0 auto;min-width:3.6rem;display:flex;flex-direction:column;align-items:center;gap:.05rem;
border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:12px;padding:.4rem .5rem;
font:inherit;cursor:pointer}
.kal button .dn{font-size:.72rem;color:var(--muted);text-transform:uppercase}
.kal button .dd{font-weight:700;font-size:1rem}
.kal button .ile{font-size:.7rem;color:var(--star);white-space:nowrap}
.kal button.akt{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.liga{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:.55rem 0;padding:0 .8rem}
.liga>summary{display:flex;justify-content:space-between;align-items:center;gap:.5rem;padding:.75rem 0;
margin:0;color:var(--ink);font-size:1rem;font-weight:650;list-style:none}
.liga>summary::-webkit-details-marker{display:none}
.liga>summary::after{content:"▾";color:var(--muted);margin-left:.3rem}
.liga[open]>summary::after{content:"▴"}
.liga>summary span:first-child{white-space:nowrap}
.liga>summary .lic{margin-left:auto;font-size:.72rem;font-weight:500;color:var(--muted);white-space:nowrap}
.liga .card .chip{display:none}
.liga[open]{padding-bottom:.6rem}
.liga .card{margin:.5rem 0}
.liga.pusta{display:flex;justify-content:space-between;padding:.75rem .8rem;color:var(--muted)}
.liga.pusta .lic{font-size:.75rem}
.kafle{display:grid;grid-template-columns:repeat(auto-fit,minmax(6.4rem,1fr));gap:.5rem;margin:.6rem 0 .4rem}
.kafel{display:flex;flex-direction:column;align-items:flex-start;gap:.1rem;text-align:left;font:inherit;color:var(--ink);
background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.65rem .7rem;cursor:pointer;min-width:0}
.kafel .kn{font-weight:700;font-size:.95rem}
.kafel .ile{color:var(--star);font-weight:700;font-size:1.35rem;line-height:1.2}
.kafel .km,.kafel .kd{font-size:.72rem;color:var(--muted)}
.kafel .kd{color:var(--star)}
.kafel.akt{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.kafel.pusty{cursor:default;opacity:.55}
div.kraj[hidden]{display:none}
.uw{color:var(--accent)}
section.dzien[hidden]{display:none}
.predykcja{border:2px solid var(--accent);border-radius:14px;padding:.8rem .9rem;margin:1.6rem 0 .6rem;
background:var(--card)}
.predykcja b{display:block;color:var(--accent);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}
.predykcja .pm{font-weight:650;margin:.3rem 0 .15rem}
.predykcja .pt{font-weight:650;font-size:1.05rem}
.predykcja .pw{font-size:.8rem;color:var(--muted);margin-top:.3rem}
.predykcja .lista{margin-top:.7rem;padding-top:.6rem;border-top:1px solid var(--line)}
.predykcja .lista b{display:inline;margin-right:.4rem}
.predykcja ol{margin:.35rem 0 0;padding-left:1.3rem;font-size:.86rem}
.predykcja ol li{margin:.3rem 0}
.predykcja ol li.pierwszy{font-weight:650}
details>summary{cursor:pointer;color:var(--accent);font-size:.88rem;font-weight:600;margin-top:.5rem;
list-style-position:outside;padding:.15rem 0}
details details>summary{color:var(--ink);font-weight:550;margin-top:.7rem}
details[open]>summary{margin-bottom:.35rem}
.podsum{font-size:.82rem;color:var(--muted);margin:.2rem 0 .3rem}
table{width:100%;border-collapse:collapse;font-size:.82rem;font-variant-numeric:tabular-nums}
th{text-align:left;font-weight:600;color:var(--muted);border-bottom:1px solid var(--line);padding:.2rem .3rem}
td{padding:.2rem .3rem;border-bottom:1px solid var(--line)}
tbody tr:nth-child(even){background:var(--zebra)}
td.c{text-align:center}
tr.g td{color:var(--accent);font-weight:650}
tr.teraz td{background:var(--ziel)}
tr.dawniej td{background:var(--nieb)}
.lg{display:inline-block;border-radius:6px;padding:0 .4rem;margin:.1rem .3rem .1rem 0;font-size:.75rem}
.lg.teraz{background:var(--ziel)}
.lg.dawniej{background:var(--nieb)}
details.seria>summary{color:inherit;font-size:inherit;font-weight:inherit;margin:0}
details.seria>summary{list-style:none}
details.seria>summary::-webkit-details-marker{display:none}
details.seria>summary::after{content:" ▾";color:var(--muted);font-weight:400}
details.seria[open]>summary::after{content:" ▴"}
details.seria .opis{font-size:.8rem;color:var(--muted);margin:.35rem 0 .3rem;font-weight:400}
details.fakt>summary::after,details.fakt[open]>summary::after{content:none}
details.fakt .wfakt{margin-left:-1.1rem}
@media (max-width:420px){td,th{padding:.2rem .18rem}}
details.fakt .pokaz{font-size:.72rem;font-weight:600;color:var(--accent);white-space:nowrap}
details.fakt .pokaz::after{content:" ▾"}
details.fakt[open] .pokaz::after{content:" ▴"}
details.fakt[open]{margin-bottom:.5rem}
li.mocny details.fakt table,li.mocny details.fakt .opis,li.mocny details.fakt .legenda{font-weight:400}
tr.x td{color:var(--muted)}
sup{color:var(--muted)}
.legenda{font-size:.75rem;color:var(--muted);margin:.25rem 0 0}
.empty{color:var(--muted)}
.dane{font-size:.85rem}
.dane li{margin:.35rem 0}
footer{margin-top:2rem;font-size:.8rem;color:var(--muted)}
"""

e = html.escape


def _znak(r):
    return "1" if r.hgoal > r.vgoal else ("X" if r.hgoal == r.vgoal else "2")


def _data_kom(r):
    """Data meczu; znak ° przy wynikach spoza archiwum engsoccerdata."""
    zrodlo = getattr(r, "zrodlo", "archiwum")
    return fmt(r.Date) + ("" if zrodlo == "archiwum" else "<sup>°</sup>")


def _legenda(df):
    if "zrodlo" not in df or not (df.zrodlo != "archiwum").any():
        return ""
    zrodla = ", ".join(sorted(set(df.zrodlo[df.zrodlo != "archiwum"])))
    return f'<p class="legenda">° wynik z {e(zrodla)}; pozostałe z archiwum engsoccerdata.</p>'


def _tabela_u_gospodarza(df, znaczniki=None):
    """Mecze jednej pary u tego samego gospodarza: data, wynik, 1X2 (2 = wygrana gości – wyróżniona), poziom.
    znaczniki: {indeks wiersza: klasa} – podświetlenie serii ("teraz" / "dawniej")."""
    w = []
    for r in df.itertuples():
        z = _znak(r)
        kl = ("g" if z == "2" else ("x" if z == "X" else "")) + " " + (znaczniki or {}).get(r.Index, "")
        w.append(f'<tr class="{kl.strip()}"><td>{_data_kom(r)}</td>'
                 f'<td class="c">{r.hgoal}:{r.vgoal}</td><td class="c">{z}</td><td class="c">{_ou(r)}</td>'
                 f'<td class="c">{r.tier}</td></tr>')
    return ('<table><thead><tr><th>Data</th><th>Wynik</th><th>1X2</th><th>2.5</th><th>Poz.</th></tr></thead>'
            f'<tbody>{"".join(w)}</tbody></table>' + _legenda(df))


def _ou(r):
    return "pow." if r.hgoal + r.vgoal >= 3 else "pon."


def _bilans(df, h, v, zakres=""):
    z = [_znak(r) for r in df.itertuples()]
    return (f'<p class="podsum">{mecze(len(z))} od {df.Date.min().year} r.{" (" + e(zakres) + ")" if zakres else ""} · '
            f'wygrane {e(h)}: {z.count("1")} · remisy: {z.count("X")} · wygrane {e(v)}: {z.count("2")}</p>')


def _tabela_pary(df, h, znaczniki=None):
    """Wszystkie mecze pary (u siebie i na wyjeździe): data, gdzie, wynik, W/R/P z perspektywy h."""
    w = []
    for r in df.itertuples():
        dom = r.home == h
        g, s = (r.hgoal, r.vgoal) if dom else (r.vgoal, r.hgoal)
        wyn = "W" if g > s else ("R" if g == s else "P")
        kl = ("g" if wyn == "P" else ("x" if wyn == "R" else "")) + " " + (znaczniki or {}).get(r.Index, "")
        w.append(f'<tr class="{kl.strip()}"><td>{_data_kom(r)}</td>'
                 f'<td>{"u siebie" if dom else "wyjazd"}</td><td class="c">{r.hgoal}:{r.vgoal}</td>'
                 f'<td class="c">{wyn}</td><td class="c">{_ou(r)}</td><td class="c">{r.tier}</td></tr>')
    return ('<table><thead><tr><th>Data</th><th>Gdzie</th><th>Wynik</th><th>W/R/P</th><th>2.5</th><th>Poz.</th>'
            f'</tr></thead><tbody>{"".join(w)}</tbody></table>' + _legenda(df))


def _najdluzsza(p, uklad):
    """Najdłuższa obecna seria ze smaczków pary w danym układzie ("u" – mecze u gospodarza, "h2h" – wszystkie)."""
    ff = [f for f in p.fakty if f.typ and f.regula and f.regula.split(":")[0] == uklad]
    return max(ff, key=lambda f: (f.n, f.waga)) if ff else None


def _teraz(df_od_najnowszego, f):
    """Znaczniki „teraz” dla meczów obecnej serii f (ostatnie f.n meczów)."""
    return {i: "teraz" for i in df_od_najnowszego.index[:f.n]} if f is not None else {}


def _znaczniki(teraz, wczesniejsze):
    """Zielone – obecna seria, niebieskie – mecze wcześniejszych serii pary (poza obecną)."""
    z = dict(teraz)
    for s in wczesniejsze:
        for i in s["indeksy"]:
            z.setdefault(i, "dawniej")
    return z


def _spis_wczesniejszych(wczesniejsze):
    if not wczesniejsze:
        return '<div class="opis">Wcześniej nie było serii między tymi drużynami (od progu smaczka).</div>'
    lata = lambda s: f"{s['od'].year}–{s['do'].year}" if s["od"].year != s["do"].year else f"{s['od'].year}"
    return ('<span class="lg dawniej">wcześniejsze serie między drużynami</span>'
            f'<div class="opis">Wcześniejsze serie: {e("; ".join(lata(s) + ": " + s["tekst"] for s in wczesniejsze))}.</div>')


def _legenda_serii(f, gdzie=""):
    if f is None:
        return ""
    return (f'<p class="legenda"><span class="lg teraz">obecna seria – {mecze(f.n)}</span>{e(gdzie)}'
            f'{e(f.tekst)}</p>')


def _wyniki_html(p):
    """Rozwijany podgląd meczów pary, z których wynikają smaczki. Mecze najdłuższej obecnej serii są zaznaczone
    na zielono: w tabeli meczów u gospodarza – seria „u gospodarza”, we wszystkich meczach pary – seria
    „u siebie i na wyjeździe”."""
    if not p.wyniki:
        return ""
    u, rew = p.wyniki["u_gosp"], p.wyniki["rewanze"]
    zakres = _opis_zakresu(p)
    s_u, s_h2h = _najdluzsza(p, "u"), _najdluzsza(p, "h2h")
    czesci = []
    if len(u):
        tytul = f"Pokaż wyniki: {mecze(len(u))} u {p.h}"
        wcz = p.wczesniejsze("u")
        czesci.append(_bilans(u, p.h, p.v, zakres) + _legenda_serii(s_u, " ")
                      + _tabela_u_gospodarza(u, _znaczniki(_teraz(u, s_u), wcz))
                      + (f'<div class="legenda">{_spis_wczesniejszych(wcz)}</div>' if wcz else ""))
        if s_h2h is not None and s_u is None and len(rew):
            czesci.append('<p class="legenda">Seria ze smaczka obejmuje mecze u siebie i na wyjeździe – jest zaznaczona '
                          'w tabeli „Wszystkie mecze pary” niżej.</p>')
    else:
        tytul = "Pokaż wyniki"
        czesci.append(f'<p class="podsum">{e(_ostatni_txt(Pozycja(None, "", p.h, p.v, [], zakres=p.zakres)))}.</p>'
                      if zakres else f'<p class="podsum">{e(p.v)} nie grał jeszcze ligowo u {e(p.h)}.</p>')
    if len(rew):
        czesci.append(f"<details><summary>Rewanże: {mecze(len(rew))} u {e(p.v)}</summary>"
                      f"{_bilans(rew, p.v, p.h, zakres)}{_tabela_u_gospodarza(rew)}</details>")
    if len(rew) and len(u):
        razem = pd.concat([u, rew]).sort_values("Date", ascending=False, kind="stable")
        z = [("W" if (r.hgoal > r.vgoal) == (r.home == p.h) and r.hgoal != r.vgoal else
              ("R" if r.hgoal == r.vgoal else "P")) for r in razem.itertuples()]
        otwarta = " open" if s_h2h is not None and s_u is None else ""
        czesci.append(f"<details{otwarta}><summary>Wszystkie mecze pary: {mecze(len(razem))}, u siebie i na wyjeździe"
                      f"</summary>"
                      f'<p class="podsum">{e(p.h)} – wygrane: {z.count("W")} · remisy: {z.count("R")} · '
                      f'porażki: {z.count("P")} (W/R/P z perspektywy {e(p.h)}'
                      f'{"; " + e(zakres) if zakres else ""})</p>{_legenda_serii(s_h2h, " ")}'
                      f'{_tabela_pary(razem, p.h, _znaczniki(_teraz(razem, s_h2h), p.wczesniejsze("h2h")))}'
                      + (f'<div class="legenda">{_spis_wczesniejszych(p.wczesniejsze("h2h"))}</div>'
                         if p.wczesniejsze("h2h") else "") + '</details>')
    return f'<details class="wyniki"><summary>{e(tytul)}</summary>{"".join(czesci)}</details>'


def seria_html(p, t, z_opisem=True):
    """Mecze pary, z których wynika typ t (TypWspolny z regułą serii): obecna seria na zielono, wcześniejsze serie
    między drużynami (każdego rodzaju, które spełniały próg smaczka) na niebiesko; od najnowszego meczu.
    z_opisem=False – bez powtórzenia tekstu smaczka (gdy jest już nad tabelą)."""
    if not p.wyniki or not t.regula:
        return ""
    uklad, rodzaj = t.regula.split(":")
    df = p.mecze_ukladu(uklad)
    if df is None or not len(df):
        return ""
    wynik = tuple(int(x) for x in t.typ[1:].split(":")) if rodzaj == "S" else None
    etykiety, _ = przebieg_serii(df, p.h, rodzaj, wynik)
    teraz = {i: "teraz" for i, et in zip(df.index, etykiety) if et == "teraz"}
    wcz = p.wczesniejsze(uklad)
    znaczniki = _znaczniki(teraz, wcz)
    gdzie = f"mecze u {p.h} z {p.v}" if uklad == "u" else f"wszystkie mecze {p.h} z {p.v} (u siebie i na wyjeździe)"
    if _opis_zakresu(p):
        gdzie += f" – {_opis_zakresu(p)}"
    legenda = f'<span class="lg teraz">obecna seria – {mecze(len(teraz))}</span>' + _spis_wczesniejszych(wcz)
    nowe = df.iloc[::-1]
    tabela = _tabela_u_gospodarza(nowe, znaczniki) if uklad == "u" else _tabela_pary(nowe, p.h, znaczniki)
    opis = f'<div class="opis">{e(t.fakt.tekst) + " " if t.fakt and z_opisem else ""}Pokazane: {e(gdzie)}.</div>'
    return opis + legenda + tabela


def _typ_faktu(f):
    """Seria jednego smaczka jako TypWspolny (do tabeli serii)."""
    return TypWspolny(rynek_typu(f.typ), f.typ, [f.typ], f.waga, f.n, regula=f.regula, fakt=f)


def _fakt_html(p, f):
    """Smaczek; jeśli to seria – po kliknięciu tabela jej meczów (obecna seria zielona, wcześniejsze niebieskie)."""
    klasa = "mocny" if f.waga >= C.PROG_DNIA else ""
    tag = f' <span class="tag">{e(_krotko(f.typ))}</span>' if f.typ else ""
    tabela = seria_html(p, _typ_faktu(f), z_opisem=False) if f.typ and f.regula else ""
    if not tabela:
        return f'<li class="{klasa}">{e(f.tekst)}{tag}</li>'
    return (f'<li class="{klasa}"><details class="seria fakt"><summary>{e(f.tekst)}{tag} '
            f'<span class="pokaz">mecze serii</span></summary><div class="wfakt">{tabela}</div></details></li>')


def _karta(p, skut=None):
    gw = '<span class="badge">★ długa historia</span>' if p.dluga_historia else ""
    godz = f"{p.data:%H:%M}" if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
    fakty = "".join(_fakt_html(p, f) for f in p.fakty[:C.MAKS_FAKTOW])
    typy = "".join(f"<div>{e(typ_tekst(t, p, skut))}</div>" for t in p.wspolne)
    ost = ostateczny_tekst(p, skut)
    if ost:
        typy += (f'<details class="seria ost"><summary>{e(ost)}</summary>'
                 f'{seria_html(p, p.ostateczny)}</details>')
    if typy:
        fakty_html_typy = f'<div class="typy"><b>Typ meczu</b>{typy}</div>'
    else:
        fakty_html_typy = ""
    klasa = "card star" if p.dluga_historia else ("card" if p.fakty else "card plain")
    return (f'<div class="{klasa}">'
            f'<div class="top"><span class="chip">{e(p.liga)}</span><span>{godz}</span>{gw}</div>'
            f'<div class="teams">{e(p.h)} – {e(p.v)}</div>'
            f'<div class="last">{e(_ostatni_txt(p))}</div>'
            + (f"<ul>{fakty}</ul>" if fakty else "") + fakty_html_typy + _wyniki_html(p) + "</div>")


def _tys(n):
    return f"{n:,}".replace(",", "\u00a0")


def _mecze_tys(n):
    return f"{_tys(n)} {mecze(n).split(' ', 1)[1]}"


def _dane_html(info):
    """Rozwijana sekcja: skąd są dane i jak są kompletne."""
    pobrano = f" (pobrano {info['pobrano']:%d.%m.%Y %H:%M})" if info.get("pobrano") else ""
    li = []
    if info.get("zrodlo_biezace"):
        li.append(f"<b>Najbliższe mecze:</b> {e(info['zrodlo_terminarza'])}{pobrano}. Godziny w czasie polskim.")
    kraje = info.get("kraje") or []
    if len(kraje) > 1:
        return _dane_html_kraje(info, li, pobrano)
    li.append(f"<b>Historia:</b> {_mecze_tys(info['liczba'])} ligowych z 4 najwyższych poziomów, "
              f"od {fmt(info['pierwszy'])} do {fmt(info['koniec'])}:")
    for nazwa, (n, od, do, sezony) in info["zrodla"].items():
        if nazwa == "archiwum":
            li.append(f"archiwum engsoccerdata (github.com/jalapic/engsoccerdata): {_mecze_tys(n)}, "
                      f"{fmt(od)} – {fmt(do)}.")
        else:
            li.append(f"{e(nazwa)}: {_mecze_tys(n)}, sezony {_sezony(sezony)} (ostatni wynik {fmt(do)}).")
    if info.get("uzupelnione"):
        li.append(f"Archiwum nie ma sezonu {_sezony(info['uzupelnione'])} – uzupełniony z {e(info['zrodlo_biezace'])}.")
    li.append("Kompletność: archiwum ma wszystkie sezony ligowe od 1888/89 (od 1892 dwie ligi, od 1920 trzy, "
              "od 1958 cztery). Przerwy to lata wojen (1915–1919, 1939–1946), kiedy ligi nie grano. Niepełne z przyczyn "
              "historycznych: 2019/20 w League One i Two (sezon przerwany przez COVID-19), 1961/62 (wycofanie "
              "Accrington Stanley), 1919/20 (wykluczenie Leeds City), 1931/32 (wycofanie Wigan Borough), "
              "1973/74 (jeden nierozegrany mecz). Baraże i puchary nie są uwzględnione.")
    li.append("Kontrola: w sezonach 1993/94, 2000/01, 2010/11 i 2020/21–2024/25 wyniki i daty z archiwum zgadzają się "
              "z football-data.co.uk (1 różnica na ok. 16 tys. meczów: Bristol Rovers – Barnet 26.03.1994).")
    li += _stan_lig_html(info)
    li += _skutecznosc_html(info)
    return ('<details class="dane"><summary>Skąd dane i czy są kompletne</summary><ul>'
            + "".join(f"<li>{x}</li>" for x in li) + "</ul></details>")


def _stan_lig_html(info):
    out = []
    for k in info.get("kraje") or []:
        czesci = []
        for st in k["ligi"]:
            if st.koniec is None:
                continue
            c = f"{e(st.nazwa)} do {fmt(st.koniec)}" + (f" (+{_tys(st.dopisane)} ze źródła bieżącego)" if st.dopisane else "")
            if st.ostrzezenie:
                c += f' – <span class="uw">{e(st.ostrzezenie)}</span>'
            czesci.append(c)
        if czesci:
            out.append(f"<b>Stan danych – {e(k['nazwa'])}:</b> " + "; ".join(czesci) + ".")
    return out


def _dane_html_kraje(info, li, pobrano):
    """Sekcja „Skąd dane” dla kilku krajów: zakres i kompletność każdego kraju, stan lig, skuteczność."""
    li.append(f"<b>Historia:</b> {_mecze_tys(info['liczba'])} ligowych z {len(info['kraje'])} krajów "
              "(archiwum engsoccerdata, github.com/jalapic/engsoccerdata, do maja–czerwca 2025, potem "
              f"{e(info.get('zrodlo_biezace') or 'brak danych bieżących')}). Smaczek „nigdy” tylko tam, gdzie archiwum "
              "ma całą historię rozgrywek; przy wycinku historii: „w żadnym z N meczów … (dane od X)”.")
    for k in info["kraje"]:
        kr = C.KRAJE[k["kraj"]]
        z = k["zakres"]
        poziomy = ", ".join(st.nazwa for st in k["ligi"])
        uz = f" Uzupełniony sezon {_sezony(k['uzupelnione'])} (brak w archiwum)." if k.get("uzupelnione") else ""
        li.append(f"<b>{e(k['nazwa'])}</b> ({e(poziomy)}): {_mecze_tys(k['liczba'])}, {fmt(k['pierwszy'])} – "
                  f"{fmt(k['koniec'])}; {'pełna historia' if kr.pelna else 'wycinek historii'}: {e(kr.uwagi)}."
                  + (f" W smaczkach: „{e(z.w)}”." if z.w else "") + uz)
    li += _stan_lig_html(info)
    li += _skutecznosc_html(info, " (test na 4 ligach angielskich)")
    return ('<details class="dane"><summary>Skąd dane i czy są kompletne</summary><ul>'
            + "".join(f"<li>{x}</li>" for x in li) + "</ul></details>")


def _skutecznosc_html(info, gdzie=""):
    li = []
    skut = info.get("skutecznosc")
    if skut and skut.get("wspolny_1X2"):
        b = {t: x for t, x in skut["bazowe"].items() if x.get("zwrot") is not None}
        g = skut.get("ostateczny_z_kursem") or skut["wspolny_1X2"]
        li.append(f"<b>Typ meczu:</b> część wspólna typów ze wszystkich serii pary (zakłada, że serie potrwają), osobno "
                  f"dla 1X2, goli i „obie strzelą”; ostateczny typ – rynek z najdłuższą serią, przy równej długości z najwyższym kursem. Sprawdzone na "
                  f"{_mecze_tys(skut['meczow'])} z sezonów {skut['okres']}{gdzie} ze średnimi kursami rynkowymi: ostateczny "
                  f"typ trafiał w {g['trafione'] * 100:.0f}% i dawał zwrot {_procent(g['zwrot'])} na postawioną "
                  "złotówkę; "
                  f"obstawianie wszystkich meczów na ślepo: od {_procent(max(x['zwrot'] for x in b.values()))} "
                  f"do {_procent(min(x['zwrot'] for x in b.values()))}. Bukmacherzy znają te serie – to nie są typy "
                  "z przewagą nad kursem.")
    return li


def _predykcja_html(pr, skut, tytul="Ostateczna predykcja dnia", typy=None):
    """Ramka predykcji dnia; typy – lista wszystkich typów dnia [(Pozycja, TypWspolny)] pod spodem."""
    nag, typ, why, hist = predykcja_tekst(pr, skut)
    lista = ""
    if typy:
        lista = ('<div class="lista"><b>Wszystkie typy dnia</b><span class="pw">od najdłuższej serii</span><ol>'
                 + "".join(f'<li class="{"pierwszy" if i == 0 else ""}"><details class="seria"><summary>'
                           + (f'<span class="tag">{e(p.liga)}</span> ' if p.liga else "")
                           + f'{e(typ_linia(p, t))}</summary>{seria_html(p, t)}</details></li>'
                           for i, (p, t) in enumerate(typy)) + "</ol></div>")
    return (f'<div class="predykcja"><b>{e(tytul)}</b><div class="pm">{e(nag)}</div>'
            f'<div class="pt">{e(typ)}</div><div class="pw">{e(why)}</div>'
            + (f'<div class="pw">{e(hist)}</div>' if hist else "") + lista + "</div>")


def _liga_html(nazwa, mecze_ligi, skut, otwarta=False):
    """Rozwijana zakładka ligi: tylko mecze z seriami, od najciekawszego. Bez serii – sam dopisek.
    otwarta – rozwinięta od razu (kraj z jedną ligą)."""
    ze = sorted([p for p in mecze_ligi if p.ma_serie], key=lambda p: -p.waga)
    if not ze:
        opis = "brak smaczków" if mecze_ligi else "brak meczów"
        return f'<div class="liga pusta"><span>{e(nazwa)}</span><span class="lic">{opis}</span></div>'
    gw = sum(1 for p in ze if p.dluga_historia)
    licznik = odmiana(len(ze), "mecz ze smaczkiem", "mecze ze smaczkami", "meczów ze smaczkami") \
        + (f" · ★{gw}" if gw else "")
    return (f'<details class="liga"{" open" if otwarta else ""}><summary><span>{e(nazwa)}</span>'
            f'<span class="lic">{e(licznik)}</span>'
            f'</summary>{"".join(_karta(p, skut) for p in ze)}</details>')


def _kafle_html(dnia, info, skut):
    """Kafelki krajów dnia (★ = liczba meczów ze smaczkami); kliknięcie kafelka pokazuje ligi kraju."""
    kafle, kraje = [], []
    for k, ligi in grupy(dnia, info, puste_ligi=True):
        mecze_kraju = [p for _, m in ligi for p in m]
        ze = sum(1 for p in mecze_kraju if p.ma_serie)
        kod = e(k["kraj"] or "inne")
        if not mecze_kraju:
            kafle.append(f'<button type="button" class="kafel pusty" data-k="{kod}" disabled>'
                         f'<span class="kn">{e(k["nazwa"])}</span><span class="km">brak meczów</span></button>')
            continue
        dlugie = sum(1 for p in mecze_kraju if p.dluga_historia)
        kafle.append(f'<button type="button" class="kafel" data-k="{kod}" aria-expanded="false">'
                     f'<span class="kn">{e(k["nazwa"])}</span><span class="ile">★ {ze}</span>'
                     f'<span class="km">{odmiana(ze, "smaczek", "smaczki", "smaczków").split(" ", 1)[1]} · '
                     f'{mecze(len(mecze_kraju))}</span>'
                     + (f'<span class="kd">{dlugie} z długą historią</span>' if dlugie else "") + "</button>")
        jedna = len(ligi) == 1
        kraje.append(f'<div class="kraj" data-k="{kod}" hidden>'
                     + "".join(_liga_html(n, m, skut, otwarta=jedna) for n, m in ligi) + "</div>")
    return f'<div class="kafle">{"".join(kafle)}</div>' + "".join(kraje)


def raport_html(pozycje, info, dzis, od, do):
    """Strona: kalendarz dni u góry; po wybraniu dnia kafelki krajów (★ = liczba meczów ze smaczkami),
    po kliknięciu kafelka rozwijane zakładki lig kraju; na dole ostateczna predykcja dnia."""
    skut = info.get("skutecznosc")
    wiele = len(_kraje(info)) > 1
    dni = sorted({p.dzien for p in pozycje if p.dzien})
    przyciski, panele = [], []
    for dzien in dni:
        dnia = [p for p in pozycje if p.dzien == dzien]
        gw = sum(1 for p in dnia if p.dluga_historia)
        iso = dzien.isoformat()
        przyciski.append(
            f'<button type="button" data-d="{iso}"><span class="dn">'
            f'{"dziś" if dzien == dzis else DNI_KROTKO[dzien.weekday()]}</span>'
            f'<span class="dd">{dzien.day}.{dzien.month:02d}</span>'
            f'<span class="ile">{"★ " + str(gw) if gw else str(sum(1 for p in dnia if p.ma_serie)) + " sm."}'
            f'</span></button>')
        tresc = _kafle_html(dnia, info, skut)
        pr = predykcja(dnia)
        panele.append(f'<section class="dzien" data-d="{iso}"><h2>{e(naglowek_dnia(dzien, dzis))}</h2>'
                      + tresc
                      + (_predykcja_html(pr, skut, typy=typy_dnia(dnia)) if pr else
                         '<p class="empty">Brak serii – brak ostatecznej predykcji tego dnia.</p>')
                      + "</section>")
    bez_daty = [p for p in pozycje if not p.dzien]
    if bez_daty:
        panele.append('<section class="bezdaty"><h2>Mecze bez daty</h2>'
                      + "".join(_karta(p, skut) for p in sorted(bez_daty, key=lambda p: -p.waga)) + "</section>")
    if not pozycje:
        panele.append(f'<p class="empty">Brak meczów {"włączonych lig" if wiele else "4 lig angielskich"} '
                      f'{od:%d.%m} – {do:%d.%m.%Y}.</p>')
    kalendarz = f'<nav class="kal">{"".join(przyciski)}</nav>' if przyciski else ""
    ostrz = "".join(f'<div class="warn">{e(o)}</div>' for o in ostrzezenia(info))
    teraz = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smaczki meczowe</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚽</text></svg>">
<style>{CSS}</style></head>
<body><main>
<h1>Smaczki meczowe</h1>
<p class="sub">{_podtytul(info)}</p>
{ostrz}
{kalendarz}
{"".join(panele)}
<footer>{e(_podsumowanie(pozycje))}<br>★ = smaczek z długą historią (waga ≥ {C.PROG_DNIA}).
Tylko mecze ligowe; „u drużyny X” = mecze, w których X był gospodarzem.
W tabelach 1X2: 1 = wygrana gospodarza, X = remis, 2 = wygrana gości (wyróżniona).
{_dane_html(info)}
Wygenerowano {teraz}.</footer>
</main>
<script>
(function () {{
  var przyciski = document.querySelectorAll(".kal button");
  var panele = document.querySelectorAll("section.dzien");
  var dzien = null, kraj = "";
  function zapisz() {{
    try {{ history.replaceState(null, "", "#" + dzien + (kraj ? "/" + kraj : "")); }} catch (e) {{}}
  }}
  function kafel(s, k) {{  // jeden otwarty kraj w dniu; ponowne kliknięcie zamyka
    s.querySelectorAll(".kafel").forEach(function (b) {{
      var on = b.getAttribute("data-k") === k;
      b.classList.toggle("akt", on); b.setAttribute("aria-expanded", on ? "true" : "false");
    }});
    s.querySelectorAll("div.kraj").forEach(function (p) {{ p.hidden = p.getAttribute("data-k") !== k; }});
  }}
  function pokaz(d, k) {{
    dzien = d;
    panele.forEach(function (s) {{
      var ten = s.getAttribute("data-d") === d;
      s.hidden = !ten;
      if (ten) {{
        var b = k && s.querySelector('.kafel[data-k="' + k + '"]:not([disabled])');
        kraj = b ? k : "";
        kafel(s, kraj);
      }}
    }});
    przyciski.forEach(function (b) {{ b.classList.toggle("akt", b.getAttribute("data-d") === d); }});
    zapisz();
  }}
  document.querySelectorAll(".kafel").forEach(function (b) {{
    b.addEventListener("click", function () {{
      var k = b.getAttribute("data-k");
      kraj = kraj === k ? "" : k;
      kafel(b.closest("section"), kraj);
      zapisz();
    }});
  }});
  if (!przyciski.length) return;
  przyciski.forEach(function (b) {{ b.addEventListener("click", function () {{ pokaz(b.getAttribute("data-d"), kraj); }}); }});
  var h = location.hash.slice(1).split("/"), dni = Array.prototype.map.call(przyciski, function (b) {{ return b.getAttribute("data-d"); }});
  pokaz(dni.indexOf(h[0]) >= 0 ? h[0] : dni[0], h[1] || "");
}})();
</script>
</body></html>
"""


def _podtytul(info):
    kraje = _kraje(info)
    if len(kraje) > 1:
        return (" · ".join(e(k["nazwa"]) for k in kraje) + f"<br>historia ligowa do {fmt(info['koniec'])} "
                "(zakres danych różny w krajach – na dole) · terminarz na kolejne dni pojawia się kilka dni wcześniej")
    return ("Premier League · Championship · League One · League Two<br>"
            f"historia ligowa od 1888 do {fmt(info['koniec'])} · terminarz na kolejne dni pojawia się kilka dni wcześniej")


# ---------- powiadomienie ----------

def powiadomienie(pozycje, dzien):
    """(tytuł, treść) dla meczów danego dnia z długą historią albo None."""
    wybrane = sorted([p for p in pozycje if p.dzien == dzien and p.dluga_historia], key=lambda p: -p.waga)
    if not wybrane:
        return None
    tytul = f"Smaczki {DNI_KROTKO[dzien.weekday()]} {dzien:%d.%m}: {mecze(len(wybrane))} z długą historią"
    linie = []
    for p in wybrane:
        godz = f"{p.data:%H:%M} " if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
        f = p.fakty[0]
        t = p.ostateczny
        typ = ""
        if t:
            k = kurs_typu(p.kursy, t.typ)
            typ = f" → typ: {_krotko(t.typ)}" + (f" ({k:.2f})" if k else "")
        linie.append(f"{godz}{p.h} – {p.v}: {f.tekst}{typ}")
    pr = predykcja(pozycje, dzien)
    if pr:
        p, t, _ = pr
        k = kurs_typu(p.kursy, t.typ)
        linie.append(f"Ostateczna predykcja dnia: {p.h} – {p.v}: {_krotko(t.typ)}" + (f" ({k:.2f})" if k else ""))
    return tytul, "\n".join(linie)
