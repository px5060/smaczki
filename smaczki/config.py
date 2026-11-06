"""Stałe w jednym miejscu: ligi, adresy źródeł i progi smaczków (do strojenia)."""

# kod football-data.co.uk: (nazwa, poziom/tier, id ligi w API-Football)
LIGI = {
    "E0": ("Premier League", 1, 39),
    "E1": ("Championship", 2, 40),
    "E2": ("League One", 3, 41),
    "E3": ("League Two", 4, 42),
}
LIGA_PO_TIER = {tier: nazwa for nazwa, tier, _ in LIGI.values()}

# --- źródła danych ---
ARCHIWUM_URL = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/england.csv"
PIERWSZY_SEZON_PO_ARCHIWUM = 2025  # archiwum kończy się 25.05.2025, sezon 2025/26 dopisujemy ze źródła bieżącego
# Sezony, których brakuje w archiwum (engsoccerdata nie ma całego 2022/23), są wykrywane automatycznie od tego sezonu
# i dopisywane ze źródła bieżącego (football-data.co.uk ma 4 ligi od 1993/94). Wcześniejsze przerwy to lata wojen.
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
MIN_SERIA_GOLI = 8             # serie bramkowe (powyżej/poniżej 1.5, 2.5, 3.5, obie strzelą, drużyna strzelała)
                               #   – tylko długie serie, od 8 meczów
MIN_SERIA_BEZ_GOLA = 5         # "drużyna nie strzeliła gola" – rzadsze, od 5 meczów
STAWKI_DOMYSLNE = {"1": 0.45, "X": 0.26, "2": 0.29, "O": 0.49, "B": 0.50,  # gdy brak danych sezonu
                   "O15": 0.74, "O35": 0.26, "HS": 0.75, "AS": 0.66}
WYNIK_DOMYSLNY = 0.05

# Od tej wagi mecz jest "smaczkiem z długą historią": wyróżnienie na stronie i powiadomienie na telefon.
# Przykłady: "Bolton nie wygrał u Derby od 1981 r. (16 meczów)" ≈ 32, "6 remisów z rzędu" ≈ 37,
# "pierwszy mecz od 25 lat" = 25, "pierwszy mecz w historii" = 30.
PROG_DNIA = 25

# Ranking: pary, które grały ze sobą w ostatnich N latach, z co najmniej tyloma meczami u gospodarza
RANKING_LAT = 3
RANKING_MIN_MECZOW = 5
