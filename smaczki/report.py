"""Raporty: tekst (konsola / plik), strona HTML na telefon i treść powiadomienia."""
import datetime as dt
import html
from dataclasses import dataclass

from . import config as C
from .rules import fmt, mecze

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

    @property
    def waga(self):
        return self.fakty[0].waga if self.fakty else 0

    @property
    def dluga_historia(self):
        return self.waga >= C.PROG_DNIA

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
    ze = sum(1 for p in pozycje if p.fakty)
    dlugie = sum(1 for p in pozycje if p.dluga_historia)
    return f"Meczów w terminarzu: {len(pozycje)}, ze smaczkami: {ze}, z długą historią (★): {dlugie}."


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


def raport_txt(pozycje, info, tytul, wszystkie=False, po_dniach=False):
    linie = [f"{tytul}  (historia ligowa do {fmt(info['koniec'])}; {info['zrodlo']})"]
    if info.get("uzupelnione"):
        linie.append(f"Sezon {_sezony(info['uzupelnione'])} – brak w archiwum, uzupełniony z {info['zrodlo_biezace']}.")
    linie += ostrzezenia(info)
    linie.append("")
    if po_dniach:
        kolejnosc = sorted(pozycje, key=lambda p: (p.dzien or dt.date.max, -p.waga))
    else:
        kolejnosc = sorted(pozycje, key=lambda p: -p.waga)
    for p in kolejnosc:
        if not p.fakty and not wszystkie:
            continue
        gw = "  ★" if p.dluga_historia else ""
        nag = " ".join(x for x in [f"[{p.liga}]" if p.liga else "", termin(p.data)] if x)
        linie.append(f"{nag}  {p.h} – {p.v}{gw}" if nag else f"{p.h} – {p.v}{gw}")
        linie.append(f"   ({_ostatni_txt(p)})")
        for f in p.fakty[:C.MAKS_FAKTOW]:
            linie.append(f"   • {f.tekst}")
        linie.append("")
    if not pozycje:
        linie.append("Brak meczów 4 lig angielskich w tym okresie.")
        linie.append("")
    linie.append(_podsumowanie(pozycje))
    return "\n".join(linie)


# ---------- strona HTML ----------

CSS = """
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--accent:#b4232c;--chip:#efece4;
--star:#b77900;--zebra:#f8f7f3}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;
--accent:#f0656d;--chip:#2b2a27;--star:#f2b443;--zebra:#252522}}
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


def _tabela_u_gospodarza(df):
    """Mecze jednej pary u tego samego gospodarza: data, wynik, 1X2 (2 = wygrana gości – wyróżniona), poziom."""
    w = []
    for r in df.itertuples():
        z = _znak(r)
        w.append(f'<tr class="{"g" if z == "2" else ("x" if z == "X" else "")}"><td>{_data_kom(r)}</td>'
                 f'<td class="c">{r.hgoal}:{r.vgoal}</td><td class="c">{z}</td><td class="c">{r.tier}</td></tr>')
    return ('<table><thead><tr><th>Data</th><th>Wynik</th><th>1X2</th><th>Poz.</th></tr></thead>'
            f'<tbody>{"".join(w)}</tbody></table>' + _legenda(df))


def _bilans(df, h, v):
    z = [_znak(r) for r in df.itertuples()]
    return (f'<p class="podsum">{mecze(len(z))} od {df.Date.min().year} r. · '
            f'wygrane {e(h)}: {z.count("1")} · remisy: {z.count("X")} · wygrane {e(v)}: {z.count("2")}</p>')


def _tabela_formy(df, druzyna, u_siebie):
    """Ostatnie mecze drużyny u siebie / na wyjeździe: data, rywal, wynik, W/R/P z jej perspektywy."""
    w = []
    for r in df.itertuples():
        g, s = (r.hgoal, r.vgoal) if u_siebie else (r.vgoal, r.hgoal)
        wyn = "W" if g > s else ("R" if g == s else "P")
        rywal = r.visitor if u_siebie else r.home
        w.append(f'<tr class="{"g" if wyn == "P" else ("x" if wyn == "R" else "")}"><td>{_data_kom(r)}</td>'
                 f'<td>{e(rywal)}</td><td class="c">{r.hgoal}:{r.vgoal}</td><td class="c">{wyn}</td></tr>')
    return ('<table><thead><tr><th>Data</th><th>Rywal</th><th>Wynik</th><th>W/R/P</th></tr></thead>'
            f'<tbody>{"".join(w)}</tbody></table>' + _legenda(df))


def _wyniki_html(p):
    """Rozwijany podgląd meczów, z których wynikają smaczki."""
    if not p.wyniki:
        return ""
    w = p.wyniki
    u, rew, fh, fv = w["u_gosp"], w["rewanze"], w["forma_h"], w["forma_v"]
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
    if len(fh) or len(fv):
        forma = ""
        if len(fh):
            forma += f"<h3>{e(p.h)} u siebie – ostatnie {len(fh)}</h3>{_tabela_formy(fh, p.h, True)}"
        if len(fv):
            forma += f"<h3>{e(p.v)} na wyjeździe – ostatnie {len(fv)}</h3>{_tabela_formy(fv, p.v, False)}"
        czesci.append(f"<details><summary>Forma: {e(p.h)} u siebie, {e(p.v)} na wyjeździe</summary>{forma}</details>")
    return f'<details class="wyniki"><summary>{e(tytul)}</summary>{"".join(czesci)}</details>'


def _karta(p):
    gw = '<span class="badge">★ długa historia</span>' if p.dluga_historia else ""
    godz = f"{p.data:%H:%M}" if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
    fakty = "".join(f'<li class="{"mocny" if f.waga >= C.PROG_DNIA else ""}">{e(f.tekst)}</li>'
                    for f in p.fakty[:C.MAKS_FAKTOW])
    klasa = "card star" if p.dluga_historia else ("card" if p.fakty else "card plain")
    return (f'<div class="{klasa}">'
            f'<div class="top"><span class="chip">{e(p.liga)}</span><span>{godz}</span>{gw}</div>'
            f'<div class="teams">{e(p.h)} – {e(p.v)}</div>'
            f'<div class="last">{e(_ostatni_txt(p))}</div>'
            + (f"<ul>{fakty}</ul>" if fakty else "") + _wyniki_html(p) + "</div>")


def _tys(n):
    return f"{n:,}".replace(",", "\u00a0")


def _dane_html(info):
    """Rozwijana sekcja: skąd są dane i jak są kompletne."""
    pobrano = f" (pobrano {info['pobrano']:%d.%m.%Y %H:%M})" if info.get("pobrano") else ""
    li = []
    if info.get("zrodlo_biezace"):
        li.append(f"<b>Najbliższe mecze:</b> {e(info['zrodlo_terminarza'])}{pobrano}. Godziny w czasie polskim.")
    li.append(f"<b>Historia:</b> {_tys(info['liczba'])} meczów ligowych 4 najwyższych poziomów, "
              f"od {fmt(info['pierwszy'])} do {fmt(info['koniec'])}:")
    for nazwa, (n, od, do, sezony) in info["zrodla"].items():
        if nazwa == "archiwum":
            li.append(f"archiwum engsoccerdata (github.com/jalapic/engsoccerdata): {_tys(n)} meczów, "
                      f"{fmt(od)} – {fmt(do)}.")
        else:
            li.append(f"{e(nazwa)}: {_tys(n)} meczów, sezony {_sezony(sezony)} (ostatni wynik {fmt(do)}).")
    if info.get("uzupelnione"):
        li.append(f"Archiwum nie ma sezonu {_sezony(info['uzupelnione'])} – uzupełniony z {e(info['zrodlo_biezace'])}.")
    li.append("Kompletność: archiwum ma wszystkie sezony ligowe od 1888/89 (od 1892 dwie ligi, od 1920 trzy, "
              "od 1958 cztery). Przerwy to lata wojen (1915–1919, 1939–1946), kiedy ligi nie grano. Niepełne z przyczyn "
              "historycznych: 2019/20 w League One i Two (sezon przerwany przez COVID-19), 1961/62 (wycofanie "
              "Accrington Stanley), 1919/20 (wykluczenie Leeds City), 1931/32 (wycofanie Wigan Borough), "
              "1973/74 (jeden nierozegrany mecz). Baraże i puchary nie są uwzględnione.")
    li.append("Kontrola: w sezonach 1993/94, 2000/01, 2010/11 i 2020/21–2024/25 wyniki i daty z archiwum zgadzają się "
              "z football-data.co.uk (1 różnica na ok. 16 tys. meczów: Bristol Rovers – Barnet 26.03.1994).")
    return ('<details class="dane"><summary>Skąd dane i czy są kompletne</summary><ul>'
            + "".join(f"<li>{x}</li>" for x in li) + "</ul></details>")


def raport_html(pozycje, info, dzis, od, do):
    dni = sorted({p.dzien for p in pozycje if p.dzien})
    sekcje = []
    for dzien in dni:
        dnia = sorted([p for p in pozycje if p.dzien == dzien], key=lambda p: -p.waga)
        ze = [p for p in dnia if p.fakty]
        bez = sorted([p for p in dnia if not p.fakty], key=lambda p: p.data or dt.datetime.max)
        czesci = [f"<h2>{e(naglowek_dnia(dzien, dzis))}</h2>"]
        czesci += [_karta(p) for p in ze] or ['<p class="empty">Brak smaczków w meczach tego dnia.</p>']
        if bez:
            czesci.append("<h3>Pozostałe mecze (bez smaczków)</h3>" + "".join(_karta(p) for p in bez))
        sekcje.append("".join(czesci))
    bez_daty = [p for p in pozycje if not p.dzien]
    if bez_daty:
        sekcje.append("<h2>Mecze bez daty</h2>" + "".join(_karta(p) for p in sorted(bez_daty, key=lambda p: -p.waga)))
    if not pozycje:
        sekcje.append(f'<p class="empty">Brak meczów 4 lig angielskich {od:%d.%m} – {do:%d.%m.%Y}.</p>')
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
{od:%d.%m} – {do:%d.%m.%Y} · historia ligowa od 1888 do {fmt(info['koniec'])}</p>
{ostrz}
{"".join(sekcje)}
<footer>{e(_podsumowanie(pozycje))}<br>★ = smaczek z długą historią (waga ≥ {C.PROG_DNIA}).
Tylko mecze ligowe; „u drużyny X” = mecze, w których X był gospodarzem.
W tabelach 1X2: 1 = wygrana gospodarza, X = remis, 2 = wygrana gości (wyróżniona).
{_dane_html(info)}
Wygenerowano {teraz}.</footer>
</main></body></html>
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
        linie.append(f"{godz}{p.h} – {p.v}: {p.fakty[0].tekst}")
    return tytul, "\n".join(linie)
