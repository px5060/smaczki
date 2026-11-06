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
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--accent:#b4232c;--chip:#efece4;--star:#b77900}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;
--accent:#f0656d;--chip:#2b2a27;--star:#f2b443}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:680px;margin:0 auto;padding:16px 16px 40px}
h1{font-size:1.5rem;margin:.2rem 0 .1rem}
.sub{color:var(--muted);font-size:.85rem;margin:0 0 .8rem}
.warn{background:#fff3cd;color:#5c4400;border-radius:10px;padding:.6rem .8rem;font-size:.85rem;margin:.5rem 0}
@media (prefers-color-scheme:dark){.warn{background:#3d3210;color:#f5e2a8}}
h2{font-size:1.05rem;margin:1.6rem 0 .6rem;padding-bottom:.3rem;border-bottom:1px solid var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.8rem .9rem;margin:.6rem 0}
.card.star{border-color:var(--star);box-shadow:0 0 0 1px var(--star) inset}
.top{display:flex;gap:.5rem;align-items:center;font-size:.8rem;color:var(--muted)}
.chip{background:var(--chip);border-radius:999px;padding:.1rem .55rem;color:var(--ink)}
.badge{margin-left:auto;color:var(--star);font-weight:600}
.teams{font-size:1.1rem;font-weight:650;margin:.35rem 0 .15rem}
.last{font-size:.8rem;color:var(--muted);margin-bottom:.35rem}
ul{margin:.2rem 0 0;padding-left:1.1rem}
li{margin:.25rem 0}
li.mocny{font-weight:600}
.reszta{font-size:.85rem;color:var(--muted);margin:.6rem 0 0}
.empty{color:var(--muted)}
footer{margin-top:2rem;font-size:.8rem;color:var(--muted)}
"""


def _karta(p):
    e = html.escape
    gw = '<span class="badge">★ długa historia</span>' if p.dluga_historia else ""
    godz = f"{p.data:%H:%M}" if p.data and (p.data.hour, p.data.minute) != (0, 0) else ""
    fakty = "".join(f'<li class="{"mocny" if f.waga >= C.PROG_DNIA else ""}">{e(f.tekst)}</li>'
                    for f in p.fakty[:C.MAKS_FAKTOW])
    return (f'<div class="card{" star" if p.dluga_historia else ""}">'
            f'<div class="top"><span class="chip">{e(p.liga)}</span><span>{godz}</span>{gw}</div>'
            f'<div class="teams">{e(p.h)} – {e(p.v)}</div>'
            f'<div class="last">{e(_ostatni_txt(p))}</div><ul>{fakty}</ul></div>')


def raport_html(pozycje, info, dzis, od, do):
    e = html.escape
    dni = sorted({p.dzien for p in pozycje if p.dzien}) or []
    sekcje = []
    for dzien in dni:
        dnia = sorted([p for p in pozycje if p.dzien == dzien], key=lambda p: -p.waga)
        ze = [p for p in dnia if p.fakty]
        bez = [p for p in dnia if not p.fakty]
        czesci = [f"<h2>{e(naglowek_dnia(dzien, dzis))}</h2>"]
        czesci += [_karta(p) for p in ze] or ['<p class="empty">Brak smaczków w meczach tego dnia.</p>']
        if bez:
            lista = "; ".join(f"{p.h} – {p.v}" for p in sorted(bez, key=lambda p: p.data or dt.datetime.max))
            czesci.append(f'<p class="reszta">Bez smaczków: {e(lista)}.</p>')
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
Tylko mecze ligowe; „u drużyny X” = mecze, w których X był gospodarzem.<br>
Źródła: {e(info['zrodlo'])}. Wygenerowano {teraz}.</footer>
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
