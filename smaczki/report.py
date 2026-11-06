"""Raporty: tekst (konsola / plik), strona HTML na telefon i treść powiadomienia."""
import datetime as dt
import html
from dataclasses import dataclass

import pandas as pd

from . import config as C
from .rules import (fmt, klucz_wyboru, kurs_typu, mecze, min_dlugosc, odmiana, przebieg_serii, rynek_typu,
                    typ_ostateczny, typy_wspolne)

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


def _ostatni_txt(p):
    if p.ostatni is None:
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
             "BTTS": "obie drużyny strzelą", "noBTTS": "co najmniej jedna nie strzeli",
             "O1.5": "co najmniej 2 gole", "U1.5": "najwyżej 1 gol", "O3.5": "co najmniej 4 gole",
             "U3.5": "najwyżej 3 gole", "GH": "gospodarz strzeli gola", "nGH": "gospodarz nie strzeli gola",
             "GA": "gość strzeli gola", "nGA": "gość nie strzeli gola"}
NAZWA_TYPU = {"O2.5": "Over 2.5", "U2.5": "Under 2.5", "BTTS": "BTTS tak", "noBTTS": "BTTS nie",
              "O1.5": "Over 1.5", "U1.5": "Under 1.5", "O3.5": "Over 3.5", "U3.5": "Under 3.5",
              "GH": "Gol gospodarza – tak", "nGH": "Gol gospodarza – nie", "GA": "Gol gościa – tak",
              "nGA": "Gol gościa – nie"}


def nazwa_typu(typ):
    if typ.startswith("S"):
        return f"dokładny wynik {typ[1:]}"
    return f"{NAZWA_TYPU.get(typ, typ)} ({OPIS_TYPU[typ]})"


def _procent(x):
    return f"{x * 100:+.0f}%".replace("-", "−")


RYNEK = {"1X2": "1X2", "gole": "Gole 2.5", "BTTS": "Obie strzelą", "wynik": "Wynik", "gole1.5": "Gole 1.5",
         "gole3.5": "Gole 3.5", "golgosp": "Gol gospodarza", "golgosc": "Gol gościa"}


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
    if info["niedopasowane"]:
        out.append("Nazwy bez dopasowania w archiwum (dopisz alias w smaczki/names.py, jeśli to znany klub): "
                   + ", ".join(sorted(info["niedopasowane"])))
    return out


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


def raport_txt(pozycje, info, tytul, wszystkie=False, po_dniach=False):
    """Raport tekstowy. po_dniach: mecze dzień po dniu i ostateczna predykcja każdego dnia;
    inaczej: wszystkie mecze od najciekawszego i jedna ostateczna predykcja na końcu."""
    skut = info.get("skutecznosc")
    linie = [f"{tytul}  (historia ligowa do {fmt(info['koniec'])}; {info['zrodlo']})"]
    if info.get("uzupelnione"):
        linie.append(f"Sezon {_sezony(info['uzupelnione'])} – brak w archiwum, uzupełniony z {info['zrodlo_biezace']}.")
    linie += ostrzezenia(info)
    linie.append("")
    if po_dniach:
        for dzien in sorted({p.dzien for p in pozycje}, key=lambda d: d or dt.date.max):
            dnia = sorted([p for p in pozycje if p.dzien == dzien], key=lambda p: -p.waga)
            linie += [f"--- {DNI[dzien.weekday()]} {dzien:%d.%m.%Y} ---" if dzien else "--- bez daty ---", ""]
            for p in dnia:
                if p.ma_serie or wszystkie:
                    linie += _mecz_txt(p, info)
            pr = predykcja(dnia)
            if pr:
                linie += _predykcja_txt(pr, skut, "OSTATECZNA PREDYKCJA DNIA")[:-2]
                linie += ["Wszystkie typy dnia (od najdłuższej serii):"]
                linie += [f"  {i}. {typ_linia(p, t)}" for i, (p, t) in enumerate(typy_dnia(dnia), 1)]
                linie += ["=" * 60, ""]
    else:
        for p in sorted(pozycje, key=lambda p: -p.waga):
            if p.ma_serie or wszystkie:
                linie += _mecz_txt(p, info)
        pr = predykcja(pozycje)
        if pr:
            linie += _predykcja_txt(pr, skut, "OSTATECZNA PREDYKCJA")
    if not pozycje:
        linie += ["Brak meczów 4 lig angielskich w tym okresie.", ""]
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
details.seria>summary::after{content:" ▾";color:var(--muted);font-weight:400}
details.seria[open]>summary::after{content:" ▴"}
details.seria .opis{font-size:.8rem;color:var(--muted);margin:.35rem 0 .3rem;font-weight:400}
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


def _bilans(df, h, v):
    z = [_znak(r) for r in df.itertuples()]
    return (f'<p class="podsum">{mecze(len(z))} od {df.Date.min().year} r. · '
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


def _wyniki_html(p):
    """Rozwijany podgląd meczów pary, z których wynikają smaczki."""
    if not p.wyniki:
        return ""
    u, rew = p.wyniki["u_gosp"], p.wyniki["rewanze"]
    czesci = []
    if len(u):
        tytul = f"Pokaż wyniki: {mecze(len(u))} u {p.h}"
        czesci.append(_bilans(u, p.h, p.v) + _tabela_u_gospodarza(u))
    else:
        tytul = "Pokaż wyniki"
        czesci.append(f'<p class="podsum">{e(p.v)} nie grał jeszcze ligowo u {e(p.h)}.</p>')
    if len(rew):
        czesci.append(f"<details><summary>Rewanże: {mecze(len(rew))} u {e(p.v)}</summary>"
                      f"{_bilans(rew, p.v, p.h)}{_tabela_u_gospodarza(rew)}</details>")
    if len(rew) and len(u):
        razem = pd.concat([u, rew]).sort_values("Date", ascending=False, kind="stable")
        z = [("W" if (r.hgoal > r.vgoal) == (r.home == p.h) and r.hgoal != r.vgoal else
              ("R" if r.hgoal == r.vgoal else "P")) for r in razem.itertuples()]
        czesci.append(f"<details><summary>Wszystkie mecze pary: {mecze(len(razem))}, u siebie i na wyjeździe</summary>"
                      f'<p class="podsum">{e(p.h)} – wygrane: {z.count("W")} · remisy: {z.count("R")} · '
                      f'porażki: {z.count("P")} (W/R/P z perspektywy {e(p.h)})</p>{_tabela_pary(razem, p.h)}</details>')
    return f'<details class="wyniki"><summary>{e(tytul)}</summary>{"".join(czesci)}</details>'


def seria_html(p, t):
    """Mecze pary, z których wynika typ t (TypWspolny z regułą serii): obecna seria na zielono,
    wcześniejsze przerwane serie tego samego rodzaju na niebiesko; od najnowszego meczu."""
    if not p.wyniki or not t.regula:
        return ""
    uklad, rodzaj = t.regula.split(":")
    u, rew = p.wyniki["u_gosp"], p.wyniki["rewanze"]
    df = u.iloc[::-1] if uklad == "u" else pd.concat([u, rew]).sort_values("Date", kind="stable")
    if not len(df):
        return ""
    wynik = tuple(int(x) for x in t.typ[1:].split(":")) if rodzaj == "S" else None
    etykiety, wczesniejsze = przebieg_serii(df, p.h, rodzaj, wynik)
    znaczniki = {i: et for i, et in zip(df.index, etykiety) if et}
    teraz = sum(1 for et in etykiety if et == "teraz")
    gdzie = f"mecze u {p.h} z {p.v}" if uklad == "u" else f"wszystkie mecze {p.h} z {p.v} (u siebie i na wyjeździe)"
    legenda = f'<span class="lg teraz">obecna seria – {mecze(teraz)}</span>'
    if wczesniejsze:
        spis = ", ".join(f"{od.year}–{do.year} ({mecze(n)})" if od.year != do.year else f"{od.year} ({mecze(n)})"
                         for od, do, n in wczesniejsze)
        legenda += (f'<span class="lg dawniej">wcześniejsze serie tego rodzaju (od {mecze(min_dlugosc(rodzaj))})'
                    f'</span><div class="opis">Wcześniejsze serie: {e(spis)}.</div>')
    else:
        legenda += f'<div class="opis">Wcześniej nie było takiej serii (od {mecze(min_dlugosc(rodzaj))}).</div>'
    nowe = df.iloc[::-1]
    tabela = _tabela_u_gospodarza(nowe, znaczniki) if uklad == "u" else _tabela_pary(nowe, p.h, znaczniki)
    opis = f'<div class="opis">{e(t.fakt.tekst) + " " if t.fakt else ""}Pokazane: {e(gdzie)}.</div>'
    return opis + legenda + tabela


def _karta(p, skut=None):
    gw = '<span class="badge">★ długa historia</span>' if p.dluga_historia else ""
    godz = f"{p.data:%H:%M}" if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
    fakty = "".join(f'<li class="{"mocny" if f.waga >= C.PROG_DNIA else ""}">{e(f.tekst)}'
                    + (f' <span class="tag">{e(_krotko(f.typ))}</span>' if f.typ else "") + "</li>"
                    for f in p.fakty[:C.MAKS_FAKTOW])
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
    skut = info.get("skutecznosc")
    if skut and skut.get("wspolny_1X2"):
        b = {t: x for t, x in skut["bazowe"].items() if x.get("zwrot") is not None}
        g = skut.get("ostateczny_z_kursem") or skut["wspolny_1X2"]
        li.append(f"<b>Typ meczu:</b> część wspólna typów ze wszystkich serii pary (zakłada, że serie potrwają), osobno "
                  f"dla 1X2, goli i „obie strzelą”; ostateczny typ – rynek z najdłuższą serią, przy równej długości z najwyższym kursem. Sprawdzone na "
                  f"{_mecze_tys(skut['meczow'])} z sezonów {skut['okres']} ze średnimi kursami rynkowymi: ostateczny "
                  f"typ trafiał w {g['trafione'] * 100:.0f}% i dawał zwrot {_procent(g['zwrot'])} na postawioną "
                  "złotówkę; "
                  f"obstawianie wszystkich meczów na ślepo: od {_procent(max(x['zwrot'] for x in b.values()))} "
                  f"do {_procent(min(x['zwrot'] for x in b.values()))}. Bukmacherzy znają te serie – to nie są typy "
                  "z przewagą nad kursem.")
    return ('<details class="dane"><summary>Skąd dane i czy są kompletne</summary><ul>'
            + "".join(f"<li>{x}</li>" for x in li) + "</ul></details>")


LIGI_KOLEJNOSC = [nazwa for nazwa, _, _ in C.LIGI.values()]


def _predykcja_html(pr, skut, tytul="Ostateczna predykcja dnia", typy=None):
    """Ramka predykcji dnia; typy – lista wszystkich typów dnia [(Pozycja, TypWspolny)] pod spodem."""
    nag, typ, why, hist = predykcja_tekst(pr, skut)
    lista = ""
    if typy:
        lista = ('<div class="lista"><b>Wszystkie typy dnia</b><span class="pw">od najdłuższej serii</span><ol>'
                 + "".join(f'<li class="{"pierwszy" if i == 0 else ""}"><details class="seria"><summary>'
                           f'{e(typ_linia(p, t))}</summary>{seria_html(p, t)}</details></li>'
                           for i, (p, t) in enumerate(typy)) + "</ol></div>")
    return (f'<div class="predykcja"><b>{e(tytul)}</b><div class="pm">{e(nag)}</div>'
            f'<div class="pt">{e(typ)}</div><div class="pw">{e(why)}</div>'
            + (f'<div class="pw">{e(hist)}</div>' if hist else "") + lista + "</div>")


def _liga_html(nazwa, mecze_ligi, skut):
    """Rozwijana zakładka ligi: tylko mecze z seriami, od najciekawszego. Bez serii – sam dopisek."""
    ze = sorted([p for p in mecze_ligi if p.ma_serie], key=lambda p: -p.waga)
    if not ze:
        opis = "brak smaczków" if mecze_ligi else "brak meczów"
        return f'<div class="liga pusta"><span>{e(nazwa)}</span><span class="lic">{opis}</span></div>'
    gw = sum(1 for p in ze if p.dluga_historia)
    licznik = odmiana(len(ze), "mecz ze smaczkiem", "mecze ze smaczkami", "meczów ze smaczkami") \
        + (f" · ★{gw}" if gw else "")
    return (f'<details class="liga"><summary><span>{e(nazwa)}</span><span class="lic">{e(licznik)}</span>'
            f'</summary>{"".join(_karta(p, skut) for p in ze)}</details>')


def raport_html(pozycje, info, dzis, od, do):
    """Strona: kalendarz dni u góry, po wybraniu dnia rozwijane zakładki 4 lig i ostateczna predykcja dnia."""
    skut = info.get("skutecznosc")
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
        ligi = [(n, [p for p in dnia if p.liga == n]) for n in LIGI_KOLEJNOSC]
        inne = [p for p in dnia if p.liga not in LIGI_KOLEJNOSC]
        if inne:
            ligi.append(("Inne mecze", inne))
        pr = predykcja(dnia)
        panele.append(f'<section class="dzien" data-d="{iso}"><h2>{e(naglowek_dnia(dzien, dzis))}</h2>'
                      + "".join(_liga_html(n, m, skut) for n, m in ligi)
                      + (_predykcja_html(pr, skut, typy=typy_dnia(dnia)) if pr else
                         '<p class="empty">Brak serii – brak ostatecznej predykcji tego dnia.</p>')
                      + "</section>")
    bez_daty = [p for p in pozycje if not p.dzien]
    if bez_daty:
        panele.append('<section class="bezdaty"><h2>Mecze bez daty</h2>'
                      + "".join(_karta(p, skut) for p in sorted(bez_daty, key=lambda p: -p.waga)) + "</section>")
    if not pozycje:
        panele.append(f'<p class="empty">Brak meczów 4 lig angielskich {od:%d.%m} – {do:%d.%m.%Y}.</p>')
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
<p class="sub">Premier League · Championship · League One · League Two<br>
historia ligowa od 1888 do {fmt(info['koniec'])} · terminarz na kolejne dni pojawia się kilka dni wcześniej</p>
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
  if (!przyciski.length) return;
  function pokaz(d) {{
    panele.forEach(function (s) {{ s.hidden = s.getAttribute("data-d") !== d; }});
    przyciski.forEach(function (b) {{ b.classList.toggle("akt", b.getAttribute("data-d") === d); }});
    try {{ history.replaceState(null, "", "#" + d); }} catch (e) {{}}
  }}
  przyciski.forEach(function (b) {{ b.addEventListener("click", function () {{ pokaz(b.getAttribute("data-d")); }}); }});
  var h = location.hash.slice(1), dni = Array.prototype.map.call(przyciski, function (b) {{ return b.getAttribute("data-d"); }});
  pokaz(dni.indexOf(h) >= 0 ? h : dni[0]);
}})();
</script>
</body></html>
"""


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
