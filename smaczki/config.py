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

# --- progi smaczków (brief, pkt 4) ---
MIN_MECZOW_GOSC_NIGDY = 5          # "V nigdy nie wygrał u H": co najmniej tyle meczów u H
MIN_LAT_BEZ_WYGRANEJ = 10          # "V nie wygrał u H od X lat"
MIN_MECZOW_OD_WYGRANEJ = 3         #   ... i co najmniej tyle meczów od ostatniej wygranej
MIN_SERIA_GOSC_BEZ_PORAZKI = 4
MIN_SERIA_GOSC_WYGRANE = 3
MIN_MECZOW_GOSP_NIGDY = 4          # "H nigdy nie wygrał u siebie z V"
MIN_MECZOW_GOSP_BEZ_WYGRANEJ = 4   # "H nie wygrał u siebie z V" (albo >= 10 lat i >= 3 mecze)
MIN_SERIA_GOSP_WYGRANE = 5
MIN_PRZERWA_LAT = 10               # "pierwszy mecz od X lat"
MIN_FORMA = 8                      # seria bez porażki / bez wygranej u siebie lub na wyjeździe
MAKS_FAKTOW = 4                    # ile faktów pokazać przy meczu

# Od tej wagi mecz jest "smaczkiem z długą historią": wyróżnienie na stronie i powiadomienie na telefon.
# Przykłady wag: "nigdy nie wygrał" 45+, "pierwszy mecz w historii" 30, "nie wygrał od 25 lat" 25,
# "wygrał 4 razy z rzędu" 24, "bez porażki w 5 meczach" 20, forma 14 meczów 21.
PROG_DNIA = 25

# Ranking: pary, które grały ze sobą w ostatnich N latach, z co najmniej tyloma meczami u gospodarza
RANKING_LAT = 3
RANKING_MIN_MECZOW = 5
