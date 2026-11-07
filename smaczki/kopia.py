"""Kopia danych źródłowych w jednym pliku ZIP – do przechowania u siebie (prywatnie), gdyby źródła przestały działać.

W kopii: archiwa engsoccerdata włączonych krajów (dane/<kraj>.csv), wszystkie pliki sezonów football-data.co.uk
włączonych lig od 1993/94 (dane/cache/fd_*.csv, bieżący sezon jako *_ostatni.csv) i ostatni terminarz.
Przywrócenie: python -m smaczki kopia --przywroc plik.zip (rozpakowuje do folderu dane/; aplikacja czyta stamtąd,
a gdy źródło nie działa, używa ostatniej zapisanej kopii bieżącego sezonu).
"""
import datetime as dt
import os
import re
import zipfile

from . import config as C
from .data_loader import BladDanych, _fd_kod, fd_terminarz, fd_wyniki, ligi_kraju, pobierz_archiwum, sezon_biezacy

# tylko takie pliki są zapisywane do kopii i z niej przywracane
WZOR = re.compile(r"^(?:[a-z]+\.csv|cache/fd_\d{4}_[A-Z0-9]+(?:_ostatni)?\.csv|cache/fixtures_ostatni\.csv)$")

OPIS = """Smaczki meczowe – kopia danych źródłowych ({data})

Zawartość:
- <kraj>.csv – archiwum engsoccerdata (https://github.com/jalapic/engsoccerdata, licencja GPL >= 2,
  autor: James Curley i współpracownicy): mecze ligowe do maja 2025.
- cache/fd_<sezon>_<liga>.csv – pliki z football-data.co.uk (https://www.football-data.co.uk): wyniki i kursy
  sezonów; *_ostatni.csv – bieżący sezon w wersji z dnia kopii; fixtures_ostatni.csv – ostatni terminarz.

Kopia do prywatnego użytku – nie publikuj jej (dane należą do ich autorów).
Przywrócenie: w folderze aplikacji  python -m smaczki kopia --przywroc {nazwa}
"""


def utworz(dane_dir, kraje, plik_zip, dzis=None, od_sezonu=C.LUKI_OD_SEZONU, postep=print):
    """Pobiera brakujące pliki (zakończone sezony do cache, bieżący jako kopię) i pakuje wszystko do plik_zip.
    kraje – {kraj: poziomy}. Zwraca (liczba plików, rozmiar ZIP w bajtach)."""
    dzis = dzis or dt.date.today()
    cache = os.path.join(dane_dir, "cache")
    s_biez = sezon_biezacy(dzis)
    for kraj, poziomy in kraje.items():
        pobierz_archiwum(dane_dir, kraj=kraj)
        ligi = ligi_kraju(kraj, poziomy)
        postep(f"{C.KRAJE[kraj].nazwa}: pliki football-data.co.uk {', '.join(ligi)} od {od_sezonu}/{(od_sezonu + 1) % 100:02d} …")
        for s in range(od_sezonu, s_biez):
            fd_wyniki(s, cache, False, ligi)  # brakujące zakończone sezony trafiają do cache
        fd_wyniki(s_biez, cache, True, ligi)  # bieżący sezon – zapisany jako *_ostatni.csv
    try:
        fd_terminarz(dzis, dzis, None, cache)  # zapisuje fixtures_ostatni.csv
    except BladDanych as e:
        postep(f"Terminarz pominięty: {e}")
    pliki = [f"{kraj}.csv" for kraj in kraje]
    for kraj, poziomy in kraje.items():
        for kod in ligi_kraju(kraj, poziomy):
            for s in range(od_sezonu, s_biez + 1):
                for nazwa in (f"fd_{_fd_kod(s)}_{kod}.csv", f"fd_{_fd_kod(s)}_{kod}_ostatni.csv"):
                    if os.path.exists(os.path.join(cache, nazwa)):
                        pliki.append(f"cache/{nazwa}")
    if os.path.exists(os.path.join(cache, "fixtures_ostatni.csv")):
        pliki.append("cache/fixtures_ostatni.csv")
    os.makedirs(os.path.dirname(os.path.abspath(plik_zip)), exist_ok=True)
    with zipfile.ZipFile(plik_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("CZYTAJ.txt", OPIS.format(data=dzis.strftime("%d.%m.%Y"), nazwa=os.path.basename(plik_zip)))
        for nazwa in pliki:
            z.write(os.path.join(dane_dir, nazwa), nazwa)
    return len(pliki), os.path.getsize(plik_zip)


def przywroc(plik_zip, dane_dir):
    """Rozpakowuje kopię do dane_dir (tylko znane pliki danych, bez ścieżek spoza folderu). Zwraca liczbę plików."""
    n = 0
    with zipfile.ZipFile(plik_zip) as z:
        for info in z.infolist():
            nazwa = info.filename
            if info.is_dir() or not WZOR.match(nazwa):
                continue
            cel = os.path.join(dane_dir, *nazwa.split("/"))
            os.makedirs(os.path.dirname(cel), exist_ok=True)
            tmp = cel + ".tmp"
            with z.open(info) as zrodlo, open(tmp, "wb") as f:
                f.write(zrodlo.read())
            os.replace(tmp, cel)
            n += 1
    return n
