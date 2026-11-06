"""Polecenia: dzis, kolejka, mecz, ranking, nazwy, pobierz.  Uruchamianie: python -m smaczki POLECENIE …"""
import argparse
import datetime as dt
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

from . import config as C
from .data_loader import BladDanych, Mecz, pobierz_archiwum, zbierz
from .report import Pozycja, powiadomienie, raport_html, raport_txt
from .rules import karta_meczu, ostatni_u_gospodarza, ranking, smaczki

if hasattr(sys.stdout, "reconfigure"):  # polskie znaki w konsoli Windows
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def wczytaj_env(plik=".env"):
    """Proste wczytanie KLUCZ=wartość z .env (bez nadpisywania ustawionych zmiennych)."""
    if not os.path.exists(plik):
        return
    with open(plik, encoding="utf-8") as f:
        for linia in f:
            linia = linia.strip()
            if linia and not linia.startswith("#") and "=" in linia:
                k, v = linia.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _data(s):
    return dt.date.fromisoformat(s)


def _info(dane):
    return {"koniec": dane.hist.Date.max(), "zrodlo": dane.zrodlo, "ostrzezenia": dane.ostrzezenia,
            "tylko_archiwum": dane.tylko_archiwum, "niedopasowane": dane.nazwy.niedopasowane}


def _pozycje(dane, terminarz, dzis):
    """Smaczki dla listy meczów; dla każdego meczu tylko historia sprzed jego daty."""
    przed = {}
    out = []
    for m in terminarz:
        h, v = dane.nazwy(m.home), dane.nazwy(m.away)
        dzien = m.data.date() if m.data else None
        if dzien not in przed:
            przed[dzien] = dane.hist if dzien is None else dane.hist[dane.hist.Date < pd.Timestamp(dzien)]
        hist = przed[dzien]
        ref = pd.Timestamp(dzien) if dzien else pd.Timestamp(dzis)
        out.append(Pozycja(m.data, m.liga, h, v, smaczki(hist, h, v, ref), ostatni_u_gospodarza(hist, h, v)))
    return out


def _plik_meczow(sciezka):
    p = pd.read_csv(sciezka, dtype=str).fillna("")
    if not {"home", "away"} <= set(p.columns):
        sys.exit(f"{sciezka}: potrzebne kolumny home,away (opcjonalnie date,liga).")
    out = []
    for r in p.itertuples():
        d = None
        tekst = getattr(r, "date", "").strip()
        if tekst:
            d = pd.to_datetime(tekst, dayfirst="." in tekst, errors="coerce")
            d = None if pd.isna(d) else d.to_pydatetime()
        out.append(Mecz(d, getattr(r, "liga", ""), r.home.strip(), r.away.strip()))
    return out


def _zapisz(sciezka, tekst):
    os.makedirs(os.path.dirname(sciezka) or ".", exist_ok=True)
    with open(sciezka, "w", encoding="utf-8") as f:
        f.write(tekst)


def _ostrzez_nazwy(dane):
    if dane.nazwy.niedopasowane:
        print("OSTRZEŻENIE: brak dopasowania w archiwum dla: " + ", ".join(sorted(dane.nazwy.niedopasowane))
              + " – jeśli to znany klub, dopisz alias w smaczki/names.py.", file=sys.stderr)


def wyslij_ntfy(temat, tytul, tresc, url=None, znacznik=None, dzien=None):
    """Powiadomienie na telefon przez ntfy.sh (aplikacja ntfy, temat = Twoja tajna nazwa kanału)."""
    if znacznik and os.path.exists(znacznik):
        with open(znacznik, encoding="utf-8") as f:
            if str(dzien) in f.read().split():
                print("Powiadomienie na dziś już wysłane – pomijam.")
                return
    serwer = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    params = {"title": tytul, "tags": "soccer"}
    if url:
        params["click"] = url
    req = urllib.request.Request(f"{serwer}/{urllib.parse.quote(temat)}?{urllib.parse.urlencode(params)}",
                                 data=tresc.encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except OSError as e:
        print(f"OSTRZEŻENIE: nie udało się wysłać powiadomienia ntfy ({e}).", file=sys.stderr)
        return
    print(f"Wysłano powiadomienie: {tytul}")
    if znacznik:
        os.makedirs(os.path.dirname(znacznik) or ".", exist_ok=True)
        with open(znacznik, "a", encoding="utf-8") as f:
            f.write(f"{dzien}\n")


# ---------- polecenia ----------

def cmd_terminarz(a, dzienny):
    dzis = _data(a.dzis) if a.dzis else dt.date.today()
    od = _data(a.od) if a.od else dzis
    do = _data(a.do) if a.do else od + dt.timedelta(days=a.dni)
    wlasne = getattr(a, "plik_meczow", None)
    dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, od, do,
                  z_terminarzem=not wlasne)
    terminarz = _plik_meczow(wlasne) if wlasne else dane.terminarz
    if not terminarz and not dzienny:
        print("\n".join(dane.ostrzezenia), file=sys.stderr)
        sys.exit(f"Brak meczów do rozegrania w okresie {od} – {do}.")
    pozycje = _pozycje(dane, terminarz, dzis)
    _ostrzez_nazwy(dane)
    info = _info(dane)
    tytul = f"SMACZKI {'DNIA' if dzienny else 'KOLEJKI'} {od:%d.%m.%Y} – {do:%d.%m.%Y}"
    tekst = raport_txt(pozycje, info, tytul, wszystkie=a.wszystkie, po_dniach=dzienny)
    print(tekst)
    _zapisz(a.raport, tekst)
    if a.html:
        _zapisz(a.html, raport_html(pozycje, info, dzis, od, do))
        print(f"\nStrona: {a.html}")
    temat = getattr(a, "ntfy", None) or os.environ.get("NTFY_TOPIC", "").strip()
    if dzienny and temat:
        p = powiadomienie(pozycje, dzis)
        if p:
            wyslij_ntfy(temat, *p, url=os.environ.get("SMACZKI_URL") or None,
                        znacznik=os.path.join(a.dane, "ntfy_wyslane.txt"), dzien=dzis)
        else:
            print("Dziś brak smaczków z długą historią – bez powiadomienia.")


def _znajdz(dane, nazwa):
    n = dane.nazwy
    wynik = n(nazwa)
    if wynik in n.niedopasowane or wynik not in n.ostatni_mecz:
        sys.exit(f"Nie znaleziono drużyny '{nazwa}' w historii.")
    kand = [t for t in n.druzyny if nazwa.lower() in t.lower()]
    if nazwa not in n.ostatni_mecz and len(kand) > 1:
        ostatnie = sorted((n.ostatni_mecz[t] for t in kand), reverse=True)
        if (ostatnie[0] - ostatnie[1]).days < 365:
            sys.exit(f"'{nazwa}' – niejednoznaczne, podaj dokładniej: {', '.join(kand)}")
    return wynik


def cmd_mecz(a):
    dzis = dt.date.today()
    dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis, dzis,
                  z_terminarzem=False)
    for o in dane.ostrzezenia:
        print("UWAGA: " + o)
    h, v = _znajdz(dane, a.gospodarz), _znajdz(dane, a.gosc)
    print(f"=== {h} – {v} ===  (historia ligowa do {dane.hist.Date.max():%d.%m.%Y}; {dane.zrodlo})")
    fakty = smaczki(dane.hist, h, v, pd.Timestamp(dzis))
    if fakty:
        print("Smaczki:")
        for f in fakty:
            print(f"  ★ {f.tekst}" if f.waga >= C.PROG_DNIA else f"  • {f.tekst}")
    print("Karta pary:")
    for linia in karta_meczu(dane.hist, h, v):
        print("  • " + linia)
    if dane.tylko_archiwum:
        print("(Bez danych bieżących – sprawdź ręcznie ostatnie sezony.)")


def cmd_ranking(a):
    dzis = dt.date.today()
    dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis, dzis,
                  z_terminarzem=False)
    for o in dane.ostrzezenia:
        print("UWAGA: " + o)
    liga = f", {C.LIGA_PO_TIER[a.tier]}" if a.tier else ""
    print(f"=== Najdłuższe passy gości bez wygranej u danego rywala{liga} "
          f"(pary grające ze sobą w ostatnich {C.RANKING_LAT} latach; historia do {dane.hist.Date.max():%d.%m.%Y}) ===")
    for linia in ranking(dane.hist, a.top, a.tier):
        print("• " + linia)


def cmd_nazwy(a):
    """Kontrola dopasowania: nazwy z bieżącego źródła -> nazwy w archiwum."""
    dzis = dt.date.today()
    dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis,
                  dzis + dt.timedelta(days=14))
    for o in dane.ostrzezenia:
        print("UWAGA: " + o)
    for m in dane.terminarz:
        dane.nazwy(m.home), dane.nazwy(m.away)
    for zrodlowa, archiwum in dane.nazwy.mapa().items():
        znak = "!!" if zrodlowa in dane.nazwy.niedopasowane else ("= " if zrodlowa == archiwum else "->")
        print(f"{znak} {zrodlowa:28} {archiwum if znak != '!!' else '(brak w archiwum – nowy klub?)'}")


def cmd_pobierz(a):
    plik = pobierz_archiwum(a.archiwum or a.dane, wymus=a.wymus)
    print(f"Archiwum gotowe: {plik}")


def main(argv=None):
    wczytaj_env()
    ap = argparse.ArgumentParser(prog="python -m smaczki", description="Smaczki meczowe – 4 ligi angielskie.")
    wspolne = argparse.ArgumentParser(add_help=False)
    wspolne.add_argument("--dane", default="dane", help="folder na archiwum i cache (domyślnie dane)")
    wspolne.add_argument("--archiwum", help="własna ścieżka do england.csv albo engsoccerdata/data-raw")
    wspolne.add_argument("--zrodlo", default="auto", choices=["auto", "fd", "api", "brak"],
                         help="dane bieżące: auto (API-Football, gdy jest klucz, inaczej football-data.co.uk), "
                              "fd, api albo brak (samo archiwum)")
    sub = ap.add_subparsers(dest="polecenie")

    def terminarzowe(p, dni, raport):
        p.add_argument("--dni", type=int, default=dni, help=f"ile dni do przodu (domyślnie {dni})")
        p.add_argument("--od", help="data początkowa RRRR-MM-DD")
        p.add_argument("--do", help="data końcowa RRRR-MM-DD")
        p.add_argument("--dzis", help=argparse.SUPPRESS)  # do testów: udawana data dzisiejsza
        p.add_argument("--raport", default=raport, help=f"plik raportu tekstowego (domyślnie {raport})")
        p.add_argument("--wszystkie", action="store_true", help="pokaż też mecze bez smaczków")

    p = sub.add_parser("dzis", parents=[wspolne], help="mecze dziś i jutro + strona HTML i powiadomienie")
    terminarzowe(p, 1, "raport_dzis.txt")
    p.add_argument("--html", default="site/index.html", help="strona HTML (domyślnie site/index.html)")
    p.add_argument("--ntfy", help="temat ntfy.sh do powiadomień (albo zmienna NTFY_TOPIC)")

    p = sub.add_parser("kolejka", parents=[wspolne], help="terminarz na N dni albo z pliku CSV")
    terminarzowe(p, 7, "raport_kolejka.txt")
    p.add_argument("--plik-meczow", help="CSV z kolumnami home,away[,date,liga] zamiast terminarza ze źródła")
    p.add_argument("--html", help="opcjonalnie także strona HTML")

    p = sub.add_parser("mecz", parents=[wspolne], help="pełna informacja o jednej parze")
    p.add_argument("gospodarz")
    p.add_argument("gosc")

    p = sub.add_parser("ranking", parents=[wspolne], help="najdłuższe passy gości bez wygranej")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="tylko pary, których ostatni mecz był w tej lidze")

    sub.add_parser("nazwy", parents=[wspolne], help="kontrola dopasowania nazw drużyn")
    p = sub.add_parser("pobierz", parents=[wspolne], help="pobierz archiwum engsoccerdata")
    p.add_argument("--wymus", action="store_true", help="pobierz ponownie, nawet jeśli plik już jest")

    a = ap.parse_args(argv)
    try:
        if a.polecenie in (None, "dzis"):
            if a.polecenie is None:
                a = ap.parse_args(["dzis"] + (argv or sys.argv[1:]))
            cmd_terminarz(a, dzienny=True)
        elif a.polecenie == "kolejka":
            cmd_terminarz(a, dzienny=False)
        elif a.polecenie == "mecz":
            cmd_mecz(a)
        elif a.polecenie == "ranking":
            cmd_ranking(a)
        elif a.polecenie == "nazwy":
            cmd_nazwy(a)
        elif a.polecenie == "pobierz":
            cmd_pobierz(a)
    except BladDanych as e:
        sys.exit(f"BŁĄD: {e}")
