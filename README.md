# Smaczki meczowe

Codziennie rano strona na telefon (i opcjonalnie powiadomienie) z odpowiedzią na pytanie:
**czy dziś albo jutro w Premier League, Championship, League One lub League Two jest mecz ze smaczkiem z długą historią?**

Przykład z 7.11.2026:

```
[Championship] sob 07.11.2026 16:00  West Bromwich Albion – Millwall  ★
   (ostatni mecz u West Bromwich Albion: 10.04.2026, 0:0)
   • Ten sam wynik 0:0 w 4 meczach z rzędu u West Bromwich Albion z Millwall (od 2023 r.).  [wynik 0:0]
   • 6 remisów z rzędu w meczach u West Bromwich Albion z Millwall (od 2019 r.). …  [X]
   • West Bromwich Albion nie wygrał z Millwall od 2020 r. (10 meczów, u siebie i na wyjeździe) – …  [X2]
   • Millwall nie wygrał u West Bromwich Albion od 2001 r. (8 meczów) – ostatnio 11.10.2001, 0:2.  [1X]
   ⇒ Typ meczu – 1X2: X (remis) – część wspólna serii X, X2, 1X · kurs ok. 3.51 · w przeszłości …
   ★ OSTATECZNY TYP: X2 (gość nie przegra) · kurs ok. 1.76 · w przeszłości …
```

★ oznacza mecz, którego najmocniejsza seria ma wagę ≥ 25 (`PROG_DNIA` w `smaczki/config.py`), np. „nigdy nie wygrał”,
„nie wygrał od 1981 r. (16 meczów)”, „6 remisów z rzędu”, „poniżej 2.5 bramki w 11 meczach z rzędu”.

## Skąd dane

| Co | Źródło | Klucz |
|---|---|---|
| Historia 08.09.1888 – 25.05.2025 (208 028 meczów) | [engsoccerdata](https://github.com/jalapic/engsoccerdata), pobierane automatycznie przy pierwszym uruchomieniu (nie jest w repo) | nie |
| Brakujący w archiwum sezon 2022/23, wyniki od sezonu 2025/26 i terminarz najbliższych dni | **football-data.co.uk**: pliki `mmz4281/<sezon>/E0..E3.csv` (wyniki, aktualizowane ok. 2 razy w tygodniu) i `fixtures.csv` (mecze najbliższych dni) | nie |
| …albo zamiast tego | API-Football v3 (jedno zapytanie na ligę i sezon: ok. 12 przy pierwszym uruchomieniu, potem 4) | tak, `API_FOOTBALL_KEY` |

Domyślnie (`--zrodlo auto`): API-Football, jeśli ustawiony jest klucz, w przeciwnym razie football-data.co.uk.
Gdy API odrzuci zapytanie (np. darmowy plan nie obejmuje bieżącego sezonu), aplikacja wypisze komunikat z API i przejdzie na
football-data.co.uk. Gdy żadne źródło nie działa, liczy na samym archiwum i ostrzega na górze raportu, że dane kończą się 25.05.2025.

Zakończone sezony są zapisywane w `dane/cache/` i nie są pobierane ponownie; bieżący sezon pobierany jest przy każdym uruchomieniu.

### Kompletność historii

- Archiwum ma wszystkie sezony ligowe od 1888/89: od 1888 jedna liga, od 1892 dwie, od 1920 trzy (1921–1958 jako
  Third Division North i South), od 1958 cztery. Przerwy 1915–1919 i 1939–1946 to lata wojen, kiedy ligi nie grano.
- **engsoccerdata nie ma całego sezonu 2022/23** (2036 meczów 4 lig). Aplikacja wykrywa takie luki sama (od sezonu
  1993/94, od którego football-data.co.uk ma 4 ligi) i dopisuje je ze źródła bieżącego. Jeśli autorzy archiwum dopiszą
  sezon, nic nie będzie uzupełniane.
- Sezony niepełne z przyczyn historycznych: 2019/20 League One i Two (przerwane przez COVID-19), 1961/62 (wycofanie
  Accrington Stanley), 1919/20 (wykluczenie Leeds City), 1931/32 (wycofanie Wigan Borough), 1973/74 (jeden nierozegrany mecz).
- Kontrola: w sezonach 1993/94, 2000/01, 2010/11 i 2020/21–2024/25 lista meczów, daty i wyniki z archiwum zgadzają się
  z football-data.co.uk. Na ok. 16 tys. meczów różni się jeden wynik: Bristol Rovers – Barnet 26.03.1994
  (archiwum 5:2, football-data 2:5).
- Baraże i puchary nie są uwzględnione.

### Strona

U góry **kalendarz**: kolejne dni z meczami (terminarz football-data.co.uk obejmuje zwykle kilka najbliższych dni),
przy każdym dniu liczba meczów z ★. Po wybraniu dnia: **cztery rozwijane zakładki lig** (Premier League,
Championship, League One, League Two) z licznikami; po rozwinięciu mecze ze smaczkami, od najciekawszego.
**Mecze bez żadnej serii** (1X2, under/over, obie strzelą, dokładny wynik) **nie są pokazywane**; liga bez nich
ma dopisek „brak smaczków”. Na dole dnia **ostateczna predykcja dnia** i pod nią **wszystkie typy dnia**: każdy mecz z serią
w jednej linii (godzina, mecz, ostateczny typ, kurs, długość serii), od najdłuższej serii.

Kliknięcie w typ (na liście typów dnia albo w „★ OSTATECZNY TYP” przy meczu) rozwija mecze pary, z których wynika
seria: **obecna seria na zielono**, **wcześniejsze, przerwane serie tego samego rodzaju na niebiesko** (od progu
długości, np. 4 mecze dla 1X2, 8 dla goli), mecze, które przerywały serie – bez tła. Pod legendą spis wcześniejszych
serii z latami, np. „1965–1980 (7 meczów), 1947–1952 (6 meczów)”. Wybrany dzień jest zapamiętany w adresie (#RRRR-MM-DD).

### Podgląd wyników

Na stronie każdy mecz ma przycisk **„Pokaż wyniki”**: wszystkie mecze ligowe u gospodarza z tym rywalem (od najnowszego,
z bilansem; wygrane gości wyróżnione), a niżej rozwijane **rewanże** (mecze u gościa) i **wszystkie mecze pary**
(u siebie i na wyjeździe, W/R/P z perspektywy gospodarza). Wyniki spoza archiwum engsoccerdata są oznaczone „°”. Na dole strony sekcja
**„Skąd dane i czy są kompletne”** pokazuje, ile meczów pochodzi z którego źródła. W konsoli to samo daje
`python -m smaczki mecz "Derby" "Bolton" --wyniki`.

## A. Automat w chmurze: codziennie, bez włączonego komputera

GitHub Actions uruchamia aplikację dwa razy dziennie (ok. 6:20 i 12:20 czasu polskiego zimą, latem godzinę później) i publikuje stronę na GitHub Pages.

1. Załóż na GitHubie **publiczne** repozytorium (np. `smaczki`) i wrzuć do niego te pliki (kod nie zawiera kluczy ani danych).
   Na prywatnym repo GitHub Pages wymaga płatnego planu.
2. W repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions → Smaczki dnia → Run workflow**: pierwsze uruchomienie ręcznie (trwa ok. 1 minuty).
4. Strona: `https://<twój-login>.github.io/<nazwa-repo>/`. Na telefonie otwórz ją i wybierz „Dodaj do ekranu głównego”.
5. *(opcjonalnie)* **Powiadomienie na telefon**, tylko w dni, gdy jest mecz z ★:
   - zainstaluj aplikację **ntfy** (Android / iOS) i zasubskrybuj temat o trudnej do zgadnięcia nazwie, np. `smaczki-k7f3x9`;
   - w repo: **Settings → Secrets and variables → Actions → New repository secret**: `NTFY_TOPIC` = ta nazwa.
   Powiadomienie przychodzi najwyżej raz dziennie; kliknięcie otwiera stronę.
6. *(opcjonalnie)* Klucz API-Football jako secret `API_FOOTBALL_KEY` (dla klucza z RapidAPI dodatkowo zmienna
   `API_FOOTBALL_HOST` = `api-football-v1.p.rapidapi.com` w zakładce *Variables*).

GitHub wyłącza harmonogram w repo bez zmian przez 60 dni. Ostatni krok workflow co dzień go ponownie włącza.
Gdyby mimo to został wyłączony, GitHub przyśle e-mail: wystarczy kliknąć **Enable workflow** w zakładce Actions.

## B. Na komputerze z Windows

1. Zainstaluj Pythona 3.10+ z [python.org](https://www.python.org/downloads/) (zaznacz **Add python.exe to PATH**).
2. Pobierz repo (**Code → Download ZIP**, rozpakuj) albo `git clone`.
3. W folderze aplikacji otwórz wiersz poleceń (w pasku adresu Eksploratora wpisz `cmd` i Enter) i wpisz:
   ```
   pip install -r requirements.txt
   python -m smaczki pobierz
   ```
   (drugie polecenie jednorazowo pobiera archiwum, ok. 15 MB, do `dane\england.csv`).
4. Na co dzień wystarczy dwuklik **`dzis.bat`**: raport w oknie i strona `site\index.html` w przeglądarce.
5. Klucz API (opcjonalnie): skopiuj `.env.example` jako `.env` i wpisz klucz. Plik `.env` nie trafia do repo.

### Polecenia

| Polecenie | Co robi |
|---|---|
| `python -m smaczki dzis` | mecze od dziś na tydzień (`--dni N` = dziś + N dni, domyślnie 6), `raport_dzis.txt` + `site/index.html` (+ powiadomienie o dzisiejszych meczach, jeśli ustawiony `NTFY_TOPIC`) |
| `python -m smaczki kolejka` | najbliższe 7 dni (`--dni N` albo `--od 2026-11-07 --do 2026-11-09`), sortowane od najciekawszego, `raport_kolejka.txt` |
| `python -m smaczki kolejka --plik-meczow mecze.csv` | własna lista meczów (kolumny `home,away,date,liga`; `date` i `liga` opcjonalne) |
| `python -m smaczki mecz "Derby" "Bolton"` | pełna karta pary: bilans u gospodarza, ostatnie wygrane, serie, średnia goli, 0:0, najwyższe zwycięstwa, bilans wszystkich meczów, forma (`--wyniki`: lista wszystkich meczów u gospodarza) |
| `python -m smaczki ranking --top 25 [--tier 1]` | najdłuższe passy „gość nie wygrał u rywala od X lat” wśród par grających ze sobą w ostatnich 3 latach |
| `python -m smaczki nazwy` | kontrola dopasowania nazw drużyn ze źródła do archiwum |
| `python -m smaczki skutecznosc` | przelicza skuteczność typów na historii z kursami (od 2005/06) |

Opcje wspólne: `--zrodlo auto|fd|api|brak`, `--dane FOLDER` (domyślnie `dane`), `--archiwum ŚCIEŻKA` (własna kopia
`england.csv` albo folder `engsoccerdata/data-raw`), w trybach terminarza także `--wszystkie` (pokaż też mecze bez smaczków).

## Reguły smaczków

Liczone są **tylko pojedynki tych dwóch drużyn** (mecze ligowe sprzed dnia meczu), bez formy z innymi rywalami.
Dla każdej pary aplikacja sprawdza bieżące serie (od ostatniego meczu wstecz) wszystkich wyników 1X2,
z perspektywy gospodarza i gościa, a także serie bramkowe (powyżej/poniżej 2.5 bramki, obie strzelą, ten sam wynik),
w dwóch układach. Nie ma rozkładów typu „7 z 10 ostatnich meczów” – tylko serie z rzędu.

| Seria | Mecze u gospodarza z tym rywalem | Wszystkie mecze pary (u siebie i na wyjeździe) |
|---|---|---|
| 1 / wygrane gospodarza z rzędu | „Derby County wygrał u siebie z Bolton Wanderers 6 razy z rzędu (od 2015 r.).” | „X wygrał z Y 8 razy z rzędu, u siebie i na wyjeździe (od 2014 r.).” |
| X / remisy z rzędu | „6 remisów z rzędu w meczach u West Bromwich Albion z Millwall (od 2019 r.).” | „5 remisów z rzędu w meczach Blackburn Rovers z West Ham United, u siebie i na wyjeździe (od 2009 r.).” |
| 2 / wygrane gościa z rzędu | „Y wygrał u X 6 razy z rzędu (od 1991 r.).” | „Y wygrał z X 12 razy z rzędu, u siebie i na wyjeździe.” |
| gość nie wygrał (1X) | „Bolton Wanderers nie wygrał u Derby County od 1981 r. (16 meczów) – ostatnio 23.09.1981, 0:2.” | „Swansea City nie wygrał z Birmingham City od 2020 r. (10 meczów, u siebie i na wyjeździe) – ostatnio …” |
| gospodarz nie wygrał (X2) | „Blackburn Rovers nie wygrał u siebie z West Ham United od 2005 r. (5 meczów) – ostatnio 10.12.2005, 3:2.” | „Cardiff City nie wygrał z Burnley od 2012 r. (9 meczów, u siebie i na wyjeździe) – …” |
| bez remisu (12) | „Bez remisu w meczach u Fulham z Newcastle United od 1984 r. (19 meczów) – ostatni remis 03.03.1984, 2:2.” | „Bez remisu w meczach X z Y od … (… meczów, u siebie i na wyjeździe)” |
| poniżej 2.5 bramki (under), od 8 meczów | „Poniżej 2.5 bramki (under) w 9 meczach z rzędu u X z Y (od 2008 r.).” | „Poniżej 2.5 bramki (under) w 11 meczach z rzędu między X a Y (u siebie i na wyjeździe, od 2004 r.).” |
| powyżej 2.5 bramki (over), od 8 meczów | „Powyżej 2.5 bramki (over) w 8 meczach z rzędu u X z Y (od 2010 r.).” | jak obok, dla wszystkich meczów pary |
| obie strzelą / co najmniej jedna bez gola, od 8 meczów | „Obie drużyny strzelały w 8 meczach z rzędu u X z Y (od 2012 r.).” | jak obok |
| powyżej/poniżej 1.5 i 3.5 bramki, od 8 meczów | „Poniżej 3.5 bramki (najwyżej 3 gole) w 13 meczach z rzędu u West Bromwich Albion z Millwall (od 1991 r.).” | „Powyżej 1.5 bramki (co najmniej 2 gole) w 10 meczach z rzędu między Arsenal a Hull City (u siebie i na wyjeździe, od 2008 r.).” |
| gospodarz / gość strzelał gola, od 8 meczów | „Ipswich Town strzelał gola u siebie z AFC Bournemouth w 16 meczach z rzędu (od 1947 r.).” | „Tottenham Hotspur strzelał gola w 16 meczach z rzędu z Leeds United (u siebie i na wyjeździe, od 2000 r.).” |
| gospodarz / gość nie strzelił gola, od 5 meczów | „Bolton nie strzelił gola u Derby w 6 meczach z rzędu (od …).” | „X nie strzelił gola w 6 meczach z rzędu z Y (u siebie i na wyjeździe, …).” |
| ten sam dokładny wynik (od 3 meczów) | „Ten sam wynik 0:0 w 4 meczach z rzędu u West Bromwich Albion z Millwall (od 2023 r.).” | „Ten sam wynik 1:0 dla X w 3 meczach z rzędu między X a Y …” |

Gdy seria obejmuje całą historię: „Fulham NIGDY nie wygrał ligowo u Arsenal (31 meczów od 1914 r.)”,
„Mecze u X z Y nigdy nie skończyły się remisem”. „Pierwszy ligowy mecz tych drużyn w historii” jest tylko
informacją (bez ★ i bez typu); „pierwszy mecz od X lat” nie jest pokazywany.

W tabelach „Pokaż wyniki” jest kolumna 2.5 (pow./pon.).

**Pokazywane są wszystkie serie pary**, które spełniają próg (bez limitu na mecz):
- co najmniej 4 mecze (serie bramkowe – powyżej/poniżej 1.5, 2.5, 3.5, obie strzelą, drużyna strzelała: co najmniej
  8 meczów; drużyna nie strzeliła: 5; ten sam dokładny wynik: 3) i seria rzadsza niż ok. 1 na 20, albo
- „nie wygrał” trwające co najmniej 10 lat i co najmniej 5 meczów.

Gdy kilka serii bramkowych obejmuje dokładnie te same mecze (np. „poniżej 1.5”, „poniżej 2.5” i „poniżej 3.5”), pokazywana
jest tylko najwęższa (tu „poniżej 1.5”). Dwie serie 1X2 złożone z dokładnie tych samych meczów są łączone w jedno zdanie, np. „Manchester United wygrał u siebie z Luton
Town 19 razy z rzędu (od 1899 r.). Luton Town nie wygrał u Manchester United od 1897 r. (ostatnio 18.09.1897, 1:2).”

**Kolejność** (nie jest nigdzie wyświetlana): im mniej prawdopodobna seria przy typowych wynikach z sezonów, w których
grano te mecze, i im dłużej trwa, tym wyżej. Dzięki temu 16 meczów bez wygranej stoi wyżej niż 4, a seria remisów
porównuje się uczciwie z serią wygranych. ★ = waga ≥ 25 (`PROG_DNIA`). Wszystkie progi są w `smaczki/config.py`.

## Typ meczu (zakład)

Przy każdym smaczku jest krótka etykieta: jaki wynik zakłada ta seria, jeśli potrwa (np. [X2], [Under 2.5]).
Pod smaczkami jest **jeden typ meczu na każdy rynek**:
- **1X2:** część wspólna wszystkich serii. Przykład: seria „6 remisów z rzędu” (X), „WBA nie wygrał z Millwall” (X2)
  i „Millwall nie wygrał u WBA” (1X) nie przeczą sobie, bo wszystkie dopuszczają remis, więc typ meczu to **X**.
  Gdy serie naprawdę się wykluczają (np. 1 i X2), aplikacja pisze „serie się wykluczają – bez typu”.
- **Gole:** Under albo Over 2.5, gdy serie wskazują to samo.
- **Obie strzelą:** tak albo nie.
- **Dokładny wynik:** gdy ten sam wynik padł co najmniej 3 razy z rzędu.

Na końcu jest **jeden ostateczny typ** na mecz: typ **najdłuższej serii** (najwięcej meczów z rzędu), a przy
równej długości – ten z **najwyższym kursem**. Przykład Derby – Bolton: część wspólna serii to 1 (Derby wygrał
u siebie 6 razy z rzędu), ale najdłuższa seria to „Bolton nie wygrał u Derby od 1981 r. (16 meczów)”, więc
ostateczny typ to **1X**. Dokładny wynik jest ostatecznym typem tylko wtedy, gdy nie ma innych serii.

Na samym końcu strony (i raportu) jest **jedna ostateczna predykcja**: spośród wszystkich meczów na stronie
ten z najdłuższą serią, a przy równej długości – z najwyższym kursem; obok seria, na której się opiera. Powiadomienie na telefon podaje
ostateczną predykcję z meczów danego dnia.

Obok jest **aktualny kurs** (średnia rynkowa z football-data.co.uk; podwójna szansa wyliczona z kursów 1X2)
i **jak taki typ meczu wypadał w przeszłości**. Kursów na „obie strzelą” i dokładny wynik w danych nie ma,
więc tam jest tylko skuteczność w porównaniu z przeciętną.

**Jak liczona jest skuteczność.** Na 43 063 meczach z sezonów 2005/06–2026/27 serie były liczone tylko
z meczów sprzed danego meczu (tak, jak w dniu meczu). Potem sprawdzane było, czy typ meczu wszedł i ile dał przy
ówczesnym średnim kursie (stawka 1 zł). „Przeciętnie” to częstość takiego wyniku we wszystkich meczach tamtych sezonów.

| Typ meczu | Typów | Trafione | Przeciętnie | Śr. kurs | Zwrot |
|---|---|---|---|---|---|
| 1 (wygra gospodarz) | 2 551 | 52.9% | 43.4% | 1.97 | −5.2% |
| X (remis) | 536 | 24.2% | 26.5% | 3.43 | −17.9% |
| 2 (wygra gość) | 1 432 | 41.5% | 30.2% | 2.66 | −4.9% |
| 1X | 5 799 | 72.2% | 70.0% | 1.32 | −6.7% |
| X2 | 3 114 | 61.1% | 56.6% | 1.57 | −7.7% |
| 12 | 1 783 | 73.0% | 73.6% | 1.30 | −4.8% |
| Under 2.5 | 368 | 51.9% | 51.3% | 1.79 | −7.4% |
| Over 2.5 | 302 | 51.0% | 48.7% | 1.85 | −7.2% |
| BTTS tak | 396 | 58.8% | 51.9% | – | brak kursów |
| BTTS nie | 169 | 52.1% | 48.1% | – | brak kursów |
| dokładny wynik | 531 | 10.2% | 9.7% | – | brak kursów |
| Over 1.5 | 2 684 | 74.8% | 73.6% | – | brak kursów |
| Under 3.5 | 2 730 | 75.3% | 73.6% | – | brak kursów |
| gol gospodarza – tak | 3 129 | 79.9% | 76.2% | – | brak kursów |
| gol gospodarza – nie | 139 | 32.4% | 23.6% | – | brak kursów |
| gol gościa – tak | 2 640 | 72.1% | 68.2% | – | brak kursów |
| gol gościa – nie | 264 | 37.5% | 31.8% | – | brak kursów |
| **1X2 razem** | 15 215 | 62.2% | 57.9% | 1.68 | −6.7% |
| **1X2 razem, mecze z ★** | 5 788 | 61.1% | 54.6% | 1.75 | −7.3% |
| **gole razem** | 670 | 51.5% | 50.1% | 1.82 | −7.3% |

| Na ślepo, każdy mecz | Typów | Trafione | Przeciętnie | Śr. kurs | Zwrot |
|---|---|---|---|---|---|
| 1 | 43 063 | 43.4% | 43.4% | 2.42 | −6.0% |
| X | 43 063 | 26.5% | 26.5% | 3.53 | −8.5% |
| 2 | 43 063 | 30.1% | 30.1% | 3.69 | −8.1% |
| 1X | 43 063 | 69.9% | 69.9% | 1.40 | −5.2% |
| X2 | 43 063 | 56.6% | 56.6% | 1.75 | −7.4% |
| 12 | 43 063 | 73.5% | 73.5% | 1.31 | −4.0% |
| O2.5 | 43 063 | 48.7% | 48.7% | 1.94 | −6.5% |
| U2.5 | 43 063 | 51.3% | 51.3% | 1.86 | −5.8% |
| BTTS | 43 063 | 51.9% | 51.9% | – | brak kursów |
| noBTTS | 43 063 | 48.1% | 48.1% | – | brak kursów |
| O1.5 | 43 063 | 73.7% | 73.7% | – | brak kursów |
| U1.5 | 43 063 | 26.4% | 26.4% | – | brak kursów |
| O3.5 | 43 063 | 26.4% | 26.4% | – | brak kursów |
| U3.5 | 43 063 | 73.6% | 73.6% | – | brak kursów |
| GH | 43 063 | 76.1% | 76.1% | – | brak kursów |
| nGH | 43 063 | 23.8% | 23.8% | – | brak kursów |
| GA | 43 063 | 68.1% | 68.1% | – | brak kursów |
| nGA | 43 063 | 31.9% | 31.9% | – | brak kursów |

Ostateczny typ (jeden na mecz):

| Ostateczny typ | Typów | Trafione | Przeciętnie | Śr. kurs | Zwrot |
|---|---|---|---|---|---|
| z rynku 1X2 | 11 774 | 68.0% | 64.4% | 1.47 | −6.2% |
| obie strzelą | 149 | 54.4% | 50.0% | – | brak kursów |
| gole 2.5 | 264 | 45.1% | 50.4% | 1.85 | −17.2% |
| gole 1.5 | 1 946 | 73.8% | 73.5% | – | brak kursów |
| gole 3.5 | 2 426 | 76.0% | 73.6% | – | brak kursów |
| gol gościa | 1 742 | 71.8% | 67.9% | – | brak kursów |
| gol gospodarza | 2 182 | 78.9% | 75.8% | – | brak kursów |
| dokładny wynik | 105 | 7.6% | 9.3% | – | brak kursów |
| **razem, z kursem** | 12 038 | 67.5% | 64.1% | 1.48 | −6.4% |
| **razem, z kursem, mecze z ★** | 3 977 | 70.0% | 64.3% | 1.43 | −5.8% |
| **ostateczna predykcja dnia** (najdłuższa seria dnia; liczba = dni) | 1 456 | 73.4% | 66.7% | 1.36 | −4.5% |

Serie wykluczały się w 0 meczach (1X2) i w 0 meczach (gole).

**Wniosek:** typy z serii trafiają nieco częściej niż przeciętnie, ale kursy już to uwzględniają. W sumie zwrot
jest podobny jak przy obstawianiu na ślepo (marża bukmachera). Bukmacherzy znają te serie, więc **to nie są typy
z przewagą nad kursem**; aplikacja pokazuje je razem z wynikami, żeby było to widać.

Przeliczenie (np. po sezonie): `python -m smaczki skutecznosc` – pobiera ok. 100 plików z kursami (raz, potem cache)
i zapisuje `smaczki/skutecznosc.json`.

## Nazwy drużyn

Kolejność dopasowania: alias (`smaczki/names.py`), dokładna nazwa, nazwa zawarta w nazwie z archiwum („Luton” → „Luton Town”;
przy kilku kandydatach wybierany jest klub, który grał najpóźniej, np. obecny „Accrington”, a nie „Accrington Stanley” z lat
1921–1962), podobieństwo tekstu (difflib, próg 0,75). Nazwa bez dopasowania zostaje bez zmian (nowy klub bez historii),
a aplikacja wypisuje ostrzeżenie z listą takich nazw, żeby łatwo dopisać alias. Wszystkie nazwy z football-data.co.uk
z sezonów 2025/26 i 2026/27 są sprawdzane w testach.

## Testy

```
python -m unittest discover -s tests -t .
```

Kryteria akceptacji z briefu na prawdziwym archiwum (plus wykrycie luki 2022/23) (Arsenal – Fulham, Manchester United – Luton, Derby – Lincoln,
Wolves – Sheffield United, Luton – Portsmouth, Bradford – Accrington) oraz ścieżki API-Football i football-data.co.uk na
zamockowanych odpowiedziach (dopisanie wyników, uzupełnienie brakującego sezonu, terminarz tylko z `NS/TBD` w zakresie
dat, cache, budżet zapytań, mapowanie nazw, błąd planu), tryb bez klucza, podgląd wyników na stronie i powiadomienia. Testy na archiwum są pomijane, jeśli nie ma `dane/england.csv`.

## Ograniczenia

- Tylko mecze ligowe (bez pucharów).
- Kluby, które grały poza 4 ligami (np. w National League), nie mają w danych meczów z tego okresu.
- „U drużyny X” = mecze, w których X był gospodarzem (bez rozróżniania stadionów).
- football-data.co.uk dopisuje wyniki z opóźnieniem do kilku dni; na serie gospodarz–gość to nie wpływa
  (para gra u danego gospodarza raz w sezonie), najwyżej na serie formy.
- Licencja engsoccerdata: dane nie są redystrybuowane (pobiera je każdy użytkownik), przed ewentualnym udostępnianiem
  surowych danych sprawdź licencję repozytorium.
