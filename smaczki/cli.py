"""Polecenia: dzis, kolejka, mecz, ranking, nazwy, pobierz.  Uruchamianie: python -m smaczki POLECENIE …

Kraje i ligi: plik ligi.json (włączone kraje i poziomy), jednorazowo --ligi spain,italy albo kody lig (E0,D2,SC0).
"""
import argparse
import datetime as dt
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

from . import config as C
from . import kopia, skutecznosc
from .data_loader import (BladDanych, Mecz, pobierz_archiwum, wczytaj_archiwum, wlaczone_ligi,
                          wybierz_ligi, zbierz, zbierz_kraje)
from .names import Nazwy
from .report import Pozycja, ostateczny_tekst, powiadomienie, raport_html, raport_txt, typ_tekst
from .rules import (fmt, karta_meczu, ostatni_u_gospodarza, ranking, smaczki, stawki_sezonow, wyniki_pary,
                    zakres_kraju)

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


TERMINARZ = {"football-data.co.uk": "football-data.co.uk, plik fixtures.csv (mecze najbliższych dni)",
             "API-Football": "API-Football, terminarz sezonu (statusy NS/TBD)"}


def _info_kraju(dane):
    h = dane.hist
    zrodla = {z: (len(g), g.Date.min(), g.Date.max(), sorted(set(g.Season)))
              for z, g in h.groupby("zrodlo", sort=False)}
    zrodla = dict(sorted(zrodla.items(), key=lambda x: x[1][1]))
    return {"kraj": dane.kraj, "nazwa": dane.nazwa_kraju, "zakres": zakres_kraju(dane.kraj, dane.poziomy),
            "koniec": h.Date.max(), "pierwszy": h.Date.min(), "liczba": len(h), "zrodla": zrodla,
            "uzupelnione": dane.uzupelnione, "ligi": dane.ligi, "tylko_archiwum": dane.tylko_archiwum,
            "niedopasowane": {n: dane.nazwy.kandydaci(n) for n in sorted(dane.nazwy.niedopasowane)},
            "ostrzezenia": dane.ostrzezenia}


def _info(dane, wlasny_plik=None):
    """Informacje o danych do raportu; dane – Dane albo lista Dane (po jednym na kraj)."""
    lista = dane if isinstance(dane, list) else [dane]
    kraje = [_info_kraju(d) for d in lista]
    wiele = len(kraje) > 1
    pierwszy = lista[0]
    biezace = next((d.biezace for d in lista if d.biezace), None)
    pobrano = max((d.pobrano for d in lista if d.pobrano), default=None)
    zrodlo = next((d.zrodlo for d in lista if d.biezace), pierwszy.zrodlo)
    ostrz = [(f"{k['nazwa']}: {o}" if wiele else o) for k in kraje for o in k["ostrzezenia"]]
    return {"koniec": max(k["koniec"] for k in kraje), "pierwszy": min(k["pierwszy"] for k in kraje),
            "liczba": sum(k["liczba"] for k in kraje), "zrodla": kraje[0]["zrodla"] if not wiele else {},
            "zrodlo": zrodlo, "ostrzezenia": ostrz, "tylko_archiwum": all(d.tylko_archiwum for d in lista),
            "niedopasowane": {(k["nazwa"], k["kraj"]): k["niedopasowane"] for k in kraje if k["niedopasowane"]},
            "uzupelnione": kraje[0]["uzupelnione"] if not wiele else [],
            "pobrano": pobrano, "zrodlo_biezace": biezace, "skutecznosc": skutecznosc.wczytaj(), "kraje": kraje,
            "zrodlo_terminarza": f"własny plik {wlasny_plik}" if wlasny_plik else TERMINARZ.get(biezace, "")}


def _pozycje(dane, terminarz, dzis, mapuj=True):
    """Smaczki dla listy meczów; dla każdego meczu tylko historia sprzed jego daty.
    mapuj=False – nazwy drużyn są już nazwami z archiwum (mecze rozegrane)."""
    przed = {}
    out = []
    zakres = zakres_kraju(dane.kraj, dane.poziomy, dane.hist)
    for m in terminarz:
        h, v = (dane.nazwy(m.home), dane.nazwy(m.away)) if mapuj else (m.home, m.away)
        dzien = m.data.date() if m.data else None
        if dzien not in przed:
            przed[dzien] = dane.hist if dzien is None else dane.hist[dane.hist.Date < pd.Timestamp(dzien)]
        hist = przed[dzien]
        ref = pd.Timestamp(dzien) if dzien else pd.Timestamp(dzis)
        wyn = wyniki_pary(hist, h, v)
        out.append(Pozycja(m.data, m.liga, h, v, smaczki(hist, h, v, ref, zakres),
                           ostatni=ostatni_u_gospodarza(hist, h, v), wyniki=wyn, kursy=m.kursy,
                           kraj=dane.kraj, zakres=zakres, stawki=stawki_sezonow(hist)))
    return out


def _pozycje_minione(dane, od, do, nazwy_lig=None):
    """Mecze rozegrane od..do (już z wynikiem w danych): smaczki i typy tak, jak wyglądały rano w dniu meczu
    (historia sprzed tego dnia), plus wynik meczu – do sprawdzenia, które serie się utrzymały, a które padły."""
    h = dane.hist
    rozegrane = h[(h.Date >= pd.Timestamp(od)) & (h.Date <= pd.Timestamp(do))]
    ligi = {t: n for n, t, _ in C.KRAJE[dane.kraj].ligi.values()}
    terminarz, wyniki = [], []
    for r in rozegrane.itertuples():
        liga = ligi.get(int(r.tier), "")
        if nazwy_lig is not None and liga not in nazwy_lig:
            continue
        godz, kursy = dane.rozegrane.get((pd.Timestamp(r.Date), r.home, r.visitor), (None, None))
        data = dt.datetime.combine(pd.Timestamp(r.Date).date(), godz or dt.time(0, 0))
        terminarz.append(Mecz(data, liga, r.home, r.visitor, kursy))
        wyniki.append((int(r.hgoal), int(r.vgoal)))
    out = _pozycje(dane, terminarz, od, mapuj=False)
    for p, w in zip(out, wyniki):
        p.rezultat = w
    return out


def _liga_z_pliku(tekst):
    """Kolumna liga w pliku meczów: kod ligi (SP1), nazwa ligi (La Liga) albo kraj (spain) -> (kraj, nazwa ligi)."""
    t = (tekst or "").strip()
    if not t:
        return C.KRAJ_DOMYSLNY, ""
    if t.upper() in C.LIGA_KRAJ:
        kraj = C.LIGA_KRAJ[t.upper()]
        return kraj, C.KRAJE[kraj].ligi[t.upper()][0]
    for kraj, k in C.KRAJE.items():
        if t.lower() == kraj:
            return kraj, ""
        for nazwa, _, _ in k.ligi.values():
            if t.lower() == nazwa.lower():
                return kraj, nazwa
    sys.exit(f"Plik meczów: nieznana liga „{t}”. Podaj kod ligi ({', '.join(C.LIGA_KRAJ)}), "
             f"nazwę ligi albo kraj ({', '.join(C.KRAJE)}).")


def _plik_meczow(sciezka):
    """Mecze z pliku CSV: {kraj: [Mecz]} (kolumny home,away[,date,liga])."""
    p = pd.read_csv(sciezka, dtype=str).fillna("")
    if not {"home", "away"} <= set(p.columns):
        sys.exit(f"{sciezka}: potrzebne kolumny home,away (opcjonalnie date,liga).")
    out = {}
    for r in p.itertuples():
        d = None
        tekst = getattr(r, "date", "").strip()
        if tekst:
            d = pd.to_datetime(tekst, dayfirst="." in tekst, errors="coerce")
            d = None if pd.isna(d) else d.to_pydatetime()
        kraj, liga = _liga_z_pliku(getattr(r, "liga", ""))
        out.setdefault(kraj, []).append(Mecz(d, liga, r.home.strip(), r.away.strip()))
    return out


def _zapisz(sciezka, tekst):
    os.makedirs(os.path.dirname(sciezka) or ".", exist_ok=True)
    with open(sciezka, "w", encoding="utf-8") as f:
        f.write(tekst)


def _ostrzez_nazwy(dane):
    """Raport niedopasowanych nazw (po każdym uruchomieniu) z najbliższymi kandydatami z archiwum."""
    for d in (dane if isinstance(dane, list) else [dane]):
        if d.nazwy.niedopasowane:
            lista = "; ".join(f"{n}" + (f" (najbliższe: {', '.join(k)})" if (k := d.nazwy.kandydaci(n)) else "")
                              for n in sorted(d.nazwy.niedopasowane))
            print(f"OSTRZEŻENIE ({d.nazwa_kraju}): brak dopasowania w archiwum dla: {lista} – jeśli to znany klub, "
                  f"dopisz alias w smaczki/aliasy/{d.kraj}.json (albo nazwę do nowe_kluby, jeśli to nowy klub).",
                  file=sys.stderr)


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

def _ligi(a):
    """(kraje -> poziomy, kody lig do terminarza albo None) z ligi.json i opcji --ligi."""
    return wybierz_ligi(wlaczone_ligi(a.plik_lig), a.ligi)


def cmd_terminarz(a, dzienny):
    dzis = _data(a.dzis) if a.dzis else dt.date.today()
    od = _data(a.od) if a.od else dzis
    do = _data(a.do) if a.do else od + dt.timedelta(days=a.dni)
    wlasne = getattr(a, "plik_meczow", None)
    kraje, kody = _ligi(a)
    if wlasne:
        z_pliku = _plik_meczow(wlasne)
        kraje = {k: kraje.get(k) or wlaczone_ligi(a.plik_lig).get(k) or None for k in C.KRAJE if k in z_pliku}
    lista = zbierz_kraje(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, od, do, kraje,
                         z_terminarzem=not wlasne)
    nazwy_lig = None if kody is None else {C.KRAJE[C.LIGA_KRAJ[k]].ligi[k][0] for k in kody}
    wstecz = getattr(a, "wstecz", 0) if not wlasne else 0
    pozycje, minione, terminarz_razem = [], [], 0
    for dane in lista:
        terminarz = z_pliku[dane.kraj] if wlasne else dane.terminarz
        if nazwy_lig is not None:
            terminarz = [m for m in terminarz if m.liga in nazwy_lig]
        terminarz_razem += len(terminarz)
        pozycje += _pozycje(dane, terminarz, dzis)
        if wstecz and not dane.tylko_archiwum:  # minione dni z wynikami (do „cofnięcia się” na stronie)
            minione += _pozycje_minione(dane, od - dt.timedelta(days=wstecz), od - dt.timedelta(days=1), nazwy_lig)
    if not terminarz_razem and not dzienny:
        print("\n".join(o for d in lista for o in d.ostrzezenia), file=sys.stderr)
        sys.exit(f"Brak meczów do rozegrania w okresie {od} – {do}.")
    _ostrzez_nazwy(lista)
    info = _info(lista, wlasne)
    tytul = f"SMACZKI {'DNIA' if dzienny else 'KOLEJKI'} {od:%d.%m.%Y} – {do:%d.%m.%Y}"
    tekst = raport_txt(pozycje, info, tytul, wszystkie=a.wszystkie, po_dniach=dzienny)
    print(tekst)
    _zapisz(a.raport, tekst)
    if a.html:
        _zapisz(a.html, raport_html(minione + pozycje, info, dzis, od, do))
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
        kand = n.kandydaci(nazwa)
        sys.exit(f"Nie znaleziono drużyny '{nazwa}' w historii ({dane.nazwa_kraju})."
                 + (f" Najbliższe: {', '.join(kand)}." if kand else ""))
    kand = [t for t in n.druzyny if nazwa.lower() in t.lower()]
    if nazwa not in n.ostatni_mecz and len(kand) > 1:
        ostatnie = sorted((n.ostatni_mecz[t] for t in kand), reverse=True)
        if (ostatnie[0] - ostatnie[1]).days < 365:
            sys.exit(f"'{nazwa}' – niejednoznaczne, podaj dokładniej: {', '.join(kand)}")
    return wynik


def _kraj_pary(a, kraje, gospodarz, gosc):
    """Kraj, w którego archiwum obie drużyny pasują najpewniej (przy równej pewności – pierwszy z listy)."""
    if len(kraje) == 1:
        return next(iter(kraje.items()))
    najlepszy, wynik = None, -1
    for kraj, poziomy in kraje.items():
        try:
            hist = wczytaj_archiwum(a.archiwum or a.dane, kraj, poziomy)
        except BladDanych as e:
            print(f"UWAGA: {e}", file=sys.stderr)
            continue
        n = Nazwy(hist, kraj)
        jakosc = min(n.jakosc(gospodarz), n.jakosc(gosc))
        if jakosc > wynik:
            najlepszy, wynik = (kraj, poziomy), jakosc
    if najlepszy is None or wynik <= 0:
        sys.exit(f"Nie znaleziono pary '{gospodarz}' – '{gosc}' w archiwach: {', '.join(kraje)}. "
                 "Podaj kraj: --ligi spain")
    return najlepszy


def cmd_mecz(a):
    dzis = dt.date.today()
    kraj, poziomy = _kraj_pary(a, _ligi(a)[0], a.gospodarz, a.gosc)
    dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis, dzis,
                  z_terminarzem=False, kraj=kraj, poziomy=poziomy)
    for o in dane.ostrzezenia:
        print("UWAGA: " + o)
    zakres = zakres_kraju(kraj, dane.poziomy, dane.hist)
    h, v = _znajdz(dane, a.gospodarz), _znajdz(dane, a.gosc)
    kraj_txt = "" if kraj == C.KRAJ_DOMYSLNY else f"{dane.nazwa_kraju}; "
    print(f"=== {h} – {v} ===  ({kraj_txt}historia ligowa do {dane.hist.Date.max():%d.%m.%Y}; {dane.zrodlo})")
    fakty = smaczki(dane.hist, h, v, pd.Timestamp(dzis), zakres)
    if fakty:
        print("Smaczki:")
        skut = skutecznosc.wczytaj()
        for f in fakty:
            print(("  ★ " if f.waga >= C.PROG_DNIA else "  • ") + f.tekst + (f"  [{f.typ}]" if f.typ else ""))
        poz = Pozycja(None, "", h, v, fakty, kraj=kraj, zakres=zakres)
        for t in poz.wspolne:
            print(f"  ⇒ Typ meczu – {typ_tekst(t, poz, skut)}")
        if ostateczny_tekst(poz, skut):
            print(f"  ★ {ostateczny_tekst(poz, skut)}")
    print("Karta pary:")
    for linia in karta_meczu(dane.hist, h, v, zakres=zakres):
        print("  • " + linia)
    if a.wyniki:
        u = wyniki_pary(dane.hist, h, v)["u_gosp"]
        print(f"Wszystkie mecze ligowe u {h} z {v} (od najnowszego; ° = wynik spoza archiwum engsoccerdata):")
        for r in u.itertuples():
            znak = "1" if r.hgoal > r.vgoal else ("X" if r.hgoal == r.vgoal else "2")
            stopien = "" if r.zrodlo == "archiwum" else "°"
            print(f"  {fmt(r.Date)}{stopien:1} {r.hgoal}:{r.vgoal}  {znak}  poziom {r.tier}")
    if dane.tylko_archiwum:
        print("(Bez danych bieżących – sprawdź ręcznie ostatnie sezony.)")


def cmd_ranking(a):
    dzis = dt.date.today()
    kraje = _ligi(a)[0] if a.ligi else {C.KRAJ_DOMYSLNY: wlaczone_ligi(a.plik_lig).get(C.KRAJ_DOMYSLNY)}
    for kraj, poziomy in kraje.items():
        dane = zbierz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis, dzis,
                      z_terminarzem=False, kraj=kraj, poziomy=poziomy)
        for o in dane.ostrzezenia:
            print("UWAGA: " + o)
        ligi = {t: n for n, t, _ in C.KRAJE[kraj].ligi.values()}
        if a.tier and a.tier not in dane.poziomy:
            print(f"{dane.nazwa_kraju}: brak poziomu {a.tier} w danych (są: {', '.join(map(str, dane.poziomy))}).")
            continue
        liga = f", {ligi[a.tier]}" if a.tier else ""
        kraj_txt = "" if kraj == C.KRAJ_DOMYSLNY else f"{dane.nazwa_kraju}: "
        zakres = zakres_kraju(kraj, dane.poziomy, dane.hist)
        print(f"=== {kraj_txt}Najdłuższe passy gości bez wygranej u danego rywala{liga} "
              f"(pary grające ze sobą w ostatnich {C.RANKING_LAT} latach; historia do {dane.hist.Date.max():%d.%m.%Y}"
              + (f"; {zakres.opis}" if zakres.opis else "") + ") ===")
        for linia in ranking(dane.hist, a.top, a.tier, zakres=zakres):
            print("• " + linia)


def cmd_nazwy(a):
    """Kontrola dopasowania: nazwy z bieżącego źródła (wyniki i terminarz na 14 dni) -> nazwy w archiwum."""
    dzis = dt.date.today()
    lista = zbierz_kraje(a.archiwum or a.dane, os.path.join(a.dane, "cache"), a.zrodlo, dzis, dzis,
                         dzis + dt.timedelta(days=14), _ligi(a)[0])
    for dane in lista:
        print(f"===== {dane.nazwa_kraju} (aliasy: smaczki/aliasy/{dane.kraj}.json)")
        for o in dane.ostrzezenia:
            print("UWAGA: " + o)
        for m in dane.terminarz:
            dane.nazwy(m.home), dane.nazwy(m.away)
        for zrodlowa, archiwum in dane.nazwy.mapa().items():
            if zrodlowa in dane.nazwy.niedopasowane:
                kand = dane.nazwy.kandydaci(zrodlowa)
                print(f"!! {zrodlowa:28} (brak w archiwum – nowy klub?" + (f" najbliższe: {', '.join(kand)}" if kand else "")
                      + ")")
            elif zrodlowa in dane.nazwy.nowe:
                print(f"+  {zrodlowa:28} (nowy klub bez historii w danych – lista nowe_kluby)")
            else:
                print(f"{'= ' if zrodlowa == archiwum else '->'} {zrodlowa:28} {archiwum}")


def cmd_skutecznosc(a):
    """Przelicza skuteczność typów na historii z kursami i zapisuje smaczki/skutecznosc.json."""
    print("Liczę skuteczność typów (kilka minut; pierwsze uruchomienie pobiera ok. 100 plików z kursami) …")
    wynik, _ = skutecznosc.policz(a.archiwum or a.dane, os.path.join(a.dane, "cache"), od_sezonu=a.od_sezonu)
    skutecznosc.zapisz(wynik)
    def wiersz(nazwa, st):
        kurs = f"śr. kurs {st['kurs']:5.2f}  zwrot {st['zwrot'] * 100:+6.1f}%" if st.get("zwrot") is not None \
            else "brak kursów"
        print(f"  {nazwa:14} {st['typow']:6d} typów  trafione {st['trafione'] * 100:5.1f}% "
              f"(przeciętnie {st['przecietnie'] * 100:4.1f}%)  {kurs}")
    print(f"Sezony {wynik['okres']}, {wynik['meczow']} meczów z kursami.\nNa ślepo (każdy mecz):")
    for k, st in wynik["bazowe"].items():
        wiersz(k, st)
    print("Typy zgodne z seriami (u = mecze u gospodarza, h2h = wszystkie mecze pary):")
    for k, st in sorted(wynik["reguly"].items()):
        wiersz(k, st)
    print("Typ meczu (część wspólna serii):")
    for k, st in sorted(wynik["wspolne"].items()):
        wiersz(k, st)
    wiersz("1X2 razem", wynik["wspolny_1X2"])
    print("Ostateczny typ (jeden na mecz):")
    for k, st in sorted(wynik["ostateczny_rynki"].items()):
        wiersz(k, st)
    wiersz("z kursem", wynik["ostateczny_z_kursem"])
    wiersz("z kursem, ★", wynik["ostateczny_gwiazdka"])
    wiersz("typ dnia", wynik["typ_dnia"])
    print(f"Zapisano {skutecznosc.PLIK}")


def cmd_kopia(a):
    """Kopia danych źródłowych w jednym ZIP-ie (do przechowania u siebie) albo przywrócenie z kopii."""
    if a.przywroc:
        n = kopia.przywroc(a.przywroc, a.dane)
        print(f"Przywrócono {n} plików z {a.przywroc} do {a.dane}/.")
        return
    plik = a.plik or f"kopia_danych_{dt.date.today():%Y-%m-%d}.zip"
    n, rozmiar = kopia.utworz(a.dane, _ligi(a)[0], plik)
    print(f"Kopia gotowa: {plik} ({n} plików, {rozmiar / 1e6:.1f} MB). Przechowuj ją u siebie, nie publikuj.")


def cmd_pobierz(a):
    for kraj in _ligi(a)[0]:
        plik = pobierz_archiwum(a.archiwum or a.dane, wymus=a.wymus, kraj=kraj)
        print(f"Archiwum gotowe: {plik}")


def main(argv=None):
    wczytaj_env()
    ap = argparse.ArgumentParser(prog="python -m smaczki", description="Smaczki meczowe – serie w pojedynkach par (Anglia i inne ligi z ligi.json).")
    wspolne = argparse.ArgumentParser(add_help=False)
    wspolne.add_argument("--dane", default="dane", help="folder na archiwum i cache (domyślnie dane)")
    wspolne.add_argument("--archiwum", help="własna ścieżka do folderu z plikami krajów (england.csv, spain.csv …), "
                                            "np. engsoccerdata/data-raw")
    wspolne.add_argument("--ligi", help="zawężenie do krajów albo lig, np. spain,italy albo E0,D2,SC0 "
                                        "(domyślnie wszystko z ligi.json)")
    wspolne.add_argument("--plik-lig", default=C.PLIK_LIG, help=f"plik z włączonymi ligami (domyślnie {C.PLIK_LIG})")
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

    p = sub.add_parser("dzis", parents=[wspolne],
                       help="mecze od dziś na tydzień (kalendarz na stronie HTML) + powiadomienie o dzisiejszych")
    terminarzowe(p, 6, "raport_dzis.txt")
    p.add_argument("--html", default="site/index.html", help="strona HTML (domyślnie site/index.html)")
    p.add_argument("--wstecz", type=int, default=C.DNI_WSTECZ,
                   help=f"ile minionych dni pokazać na stronie z wynikami i oceną serii (domyślnie {C.DNI_WSTECZ})")
    p.add_argument("--ntfy", help="temat ntfy.sh do powiadomień (albo zmienna NTFY_TOPIC)")

    p = sub.add_parser("kolejka", parents=[wspolne], help="terminarz na N dni albo z pliku CSV")
    terminarzowe(p, 7, "raport_kolejka.txt")
    p.add_argument("--plik-meczow", help="CSV z kolumnami home,away[,date,liga] zamiast terminarza ze źródła; "
                                         "liga = kod ligi (E0, SP1, D2 …), nazwa ligi albo kraj; puste = Anglia")
    p.add_argument("--html", help="opcjonalnie także strona HTML")

    p = sub.add_parser("mecz", parents=[wspolne], help="pełna informacja o jednej parze")
    p.add_argument("gospodarz")
    p.add_argument("gosc")
    p.add_argument("--wyniki", action="store_true", help="wypisz też wszystkie mecze u gospodarza")

    p = sub.add_parser("ranking", parents=[wspolne], help="najdłuższe passy gości bez wygranej")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="tylko pary, których ostatni mecz był w tej lidze "
                                                                     "(kraj: --ligi, domyślnie Anglia)")

    sub.add_parser("nazwy", parents=[wspolne], help="kontrola dopasowania nazw drużyn")
    p = sub.add_parser("skutecznosc", parents=[wspolne], help="przelicz skuteczność typów na historii z kursami")
    p.add_argument("--od-sezonu", type=int, default=2005, help="pierwszy sezon testu (domyślnie 2005 = 2005/06)")
    p = sub.add_parser("kopia", parents=[wspolne],
                       help="kopia danych źródłowych w jednym ZIP-ie (archiwa + football-data.co.uk) albo przywrócenie")
    p.add_argument("--plik", help="nazwa pliku ZIP (domyślnie kopia_danych_RRRR-MM-DD.zip)")
    p.add_argument("--przywroc", metavar="ZIP", help="przywróć dane z kopii do folderu --dane")
    p = sub.add_parser("pobierz", parents=[wspolne], help="pobierz archiwa engsoccerdata włączonych krajów")
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
        elif a.polecenie == "skutecznosc":
            cmd_skutecznosc(a)
        elif a.polecenie == "kopia":
            cmd_kopia(a)
        elif a.polecenie == "pobierz":
            cmd_pobierz(a)
    except BladDanych as e:
        sys.exit(f"BŁĄD: {e}")
