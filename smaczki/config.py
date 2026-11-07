"""Stałe w jednym miejscu: kraje i ligi, adresy źródeł i progi smaczków (do strojenia)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Kraj:
    """Kraj z archiwum engsoccerdata (plik data-raw/<id>.csv)."""
    nazwa: str
    ligi: dict           # kod football-data.co.uk -> (nazwa ligi, poziom, id ligi w API-Football)
    od: int              # pierwszy sezon w archiwum (rok rozpoczęcia: 1994 = 1994/95)
    pelna: bool          # True: archiwum ma całą historię tych rozgrywek (wolno pisać „nigdy”);
                         # False: wycinek historii – zamiast „nigdy” piszemy „w żadnym z N meczów … (dane od X)”
    w: dict = field(default_factory=dict)  # poziomy -> dopisek zakresu w smaczkach, np. (1,): "w 1. lidze";
                                           # () = wszystkie poziomy ligowe kraju są w danych (bez dopisku)
    od_poziomu: dict = field(default_factory=dict)  # poziom -> pierwszy sezon, gdy inny niż `od`
    brak: tuple = ()     # sezony rozegrane, ale brakujące w archiwum i nie do uzupełnienia (np. Francja 1937/38):
                         # serie, które je obejmują, dostają zastrzeżenie zamiast „nigdy” i niższą wagę
    uwagi: str = ""      # opis kompletności danych (na stronę)


# Kolejność krajów = kolejność na stronie i w raporcie. Które ligi są włączone: plik ligi.json (PLIK_LIG).
# Inny kraj z engsoccerdata (data-raw/<kraj>.csv) można dodać tu, z kodami lig football-data.co.uk.
KRAJE = {
    "england": Kraj("Anglia", {"E0": ("Premier League", 1, 39), "E1": ("Championship", 2, 40),
                               "E2": ("League One", 3, 41), "E3": ("League Two", 4, 42)},
                    od=1888, pelna=True, w={(1, 2, 3, 4): "", (1,): "w Premier League"},
                    uwagi="wszystkie sezony ligowe od 1888/89 (od 1892 dwie ligi, od 1920 trzy, od 1958 cztery); "
                          "przerwy to lata wojen"),
    "spain": Kraj("Hiszpania", {"SP1": ("La Liga", 1, 140)}, od=1928, pelna=True, w={(1,): "w 1. lidze"},
                  uwagi="La Liga od 1928/29 (przerwa 1936–1939 – wojna domowa)"),
    "italy": Kraj("Włochy", {"I1": ("Serie A", 1, 135)}, od=1929, pelna=True, w={(1,): "w 1. lidze"},
                  uwagi="Serie A od 1929/30 (przerwa 1943–1945 – wojna)"),
    "germany": Kraj("Niemcy", {"D1": ("Bundesliga", 1, 78), "D2": ("2. Bundesliga", 2, 79)}, od=1963, pelna=True,
                    w={(1,): "w Bundeslidze", (2,): "w 2. Bundeslidze", (1, 2): "w 1. i 2. Bundeslidze"},
                    od_poziomu={2: 1974},
                    uwagi="Bundesliga od 1963/64 i 2. Bundesliga od 1974/75 (od początku tych lig); bez niższych lig "
                          "i bez dawnych Oberlig"),
    "france": Kraj("Francja", {"F1": ("Ligue 1", 1, 61)}, od=1932, pelna=True, w={(1,): "w 1. lidze"}, brak=(1937,),
                   uwagi="1. liga od 1932/33 (od początku ligi zawodowej; przerwa 1939–1945 – wojna). Archiwum nie ma "
                         "sezonu 1937/38 – serie obejmujące ten sezon mają zastrzeżenie; 1994/95 jest uzupełniany "
                         "z football-data.co.uk"),
    "holland": Kraj("Holandia", {"N1": ("Eredivisie", 1, 88)}, od=1956, pelna=True, w={(1,): "w Eredivisie"},
                    uwagi="Eredivisie od 1956/57 (od początku tej ligi); wcześniejsze mistrzostwa Holandii nie są "
                          "w danych, dlatego smaczki mówią „w Eredivisie”"),
}
KRAJ_DOMYSLNY = "england"
PLIK_LIG = "ligi.json"  # włączone kraje i poziomy, np. {"england": [1, 2, 3, 4], "spain": [1]}
WAGA_WYCINKA = 0.5      # seria od pierwszego meczu w danych, gdy dane są tylko wycinkiem historii: waga × 0,5

# Anglia (zgodność wstecz)
LIGI = KRAJE["england"].ligi
LIGA_PO_TIER = {tier: nazwa for nazwa, tier, _ in LIGI.values()}
LIGA_KRAJ = {kod: k for k, kraj in KRAJE.items() for kod in kraj.ligi}  # kod ligi -> kraj

# --- źródła danych ---
ARCHIWUM_BAZA = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw"
ARCHIWUM_URL = f"{ARCHIWUM_BAZA}/england.csv"
PIERWSZY_SEZON_PO_ARCHIWUM = 2025  # archiwa kończą się w maju–czerwcu 2025, sezon 2025/26 dopisujemy ze źródła bieżącego
# Sezony, których brakuje w archiwum (np. Anglia 2022/23), są wykrywane automatycznie od tego sezonu
# i dopisywane ze źródła bieżącego (football-data.co.uk ma te ligi od 1993/94–1997/98). Wcześniejsze przerwy to lata wojen.
LUKI_OD_SEZONU = 1993

FD_URL = "https://www.football-data.co.uk"  # darmowe CSV, bez klucza

API_HOST_DOMYSLNY = "v3.football.api-sports.io"  # albo api-football-v1.p.rapidapi.com (klucz z RapidAPI)
API_ZAKONCZONE = {"FT", "AET", "PEN"}
API_DO_ROZEGRANIA = {"NS", "TBD"}
API_STREFA = "Europe/Warsaw"  # godziny meczów z API od razu w czasie polskim

# football-data.co.uk podaje godziny brytyjskie; Polska jest zawsze +1 h (zmiana czasu w tych samych dniach)
FD_PRZESUNIECIE_GODZIN = 1

# --- smaczki: serie 1X2 w pojedynkach pary ---
# Liczone są tylko mecze tych dwóch drużyn, w dwóch układach: mecze u gospodarza z tym rywalem oraz wszystkie
# mecze ligowe pary (u siebie i na wyjeździe). Serie: wygrane gospodarza (1), remisy (X), wygrane gościa (2),
# "nie wygrał" (każda ze stron), "bez remisu", over/under 2.5, obie strzelą tak/nie i ten sam dokładny wynik.
# Kolejność (niewyświetlana): rzadkość serii = -log10(szansy na nią przy typowych wynikach z sezonów, w których
# grano), żeby 15 meczów bez wygranej stało wyżej niż 4, a seria remisów dała się porównać z serią wygranych.
MIN_SERIA = 4                  # co najmniej tyle meczów w serii
MIN_RZADKOSC = 1.3             # i seria rzadsza niż ok. 1 na 20
WAGA_RZADKOSCI = 10            # waga faktu = 10 × rzadkość + premia za lata trwania serii
BONUS_ZA_ROK = 0.2             # +1 za każde 5 lat trwania serii
MAKS_LAT_BONUSU = 100
MIN_LAT_BEZ_WYGRANEJ = 10      # "nie wygrał od X r." / "nigdy nie wygrał" pokazujemy też przy mniejszej rzadkości,
MIN_MECZOW_OD_LAT = 5          #   jeśli trwa co najmniej 10 lat i obejmuje co najmniej 5 meczów
WAGA_PIERWSZEGO_MECZU = 0      # "pierwszy mecz w historii" – tylko informacja (bez serii, bez ★)
MAKS_FAKTOW = None             # ile faktów pokazać przy meczu (None = wszystkie serie pary)
MIN_SERIA_WYNIKU = 3           # "ten sam dokładny wynik" – od 3 meczów z rzędu
MIN_SERIA_GOLI = 8             # powyżej/poniżej 2.5 bramki i "obie strzelą" – tylko długie serie, od 8 meczów
STAWKI_DOMYSLNE = {"1": 0.45, "X": 0.26, "2": 0.29, "O": 0.49, "B": 0.50}  # gdy brak danych sezonu
WYNIK_DOMYSLNY = 0.05

# Od tej wagi mecz jest "smaczkiem z długą historią": wyróżnienie na stronie i powiadomienie na telefon.
# Przykłady: "Bolton nie wygrał u Derby od 1981 r. (16 meczów)" ≈ 32, "6 remisów z rzędu" ≈ 37,
# "pierwszy mecz od 25 lat" = 25, "pierwszy mecz w historii" = 30.
PROG_DNIA = 25

# Ranking: pary, które grały ze sobą w ostatnich N latach, z co najmniej tyloma meczami u gospodarza
RANKING_LAT = 3
RANKING_MIN_MECZOW = 5
