# Smaczki meczowe

Codziennie rano strona na telefon (i opcjonalnie powiadomienie) z odpowiedzią na pytanie:
**czy dziś albo jutro w Premier League, Championship, League One lub League Two jest mecz ze smaczkiem z długą historią?**

Przykłady z 6–7.11.2026:

```
[Championship] pt 06.11.2026 21:00  Derby County – Bolton Wanderers  ★
   (ostatni mecz u Derby County: 16.03.2024, 1:0)
   • Bolton Wanderers nie wygrał u Derby County od 45 lat – ostatnio 23.09.1981 (0:2); od tego czasu 16 meczów bez wygranej.
   • Derby County wygrał u siebie z Bolton Wanderers 6 razy z rzędu.

[Championship] sob 07.11.2026 16:00  Queens Park Rangers – Lincoln City  ★
   • Pierwszy ligowy mecz tych drużyn od 64 lat (ostatni: 30.04.1962).
```

★ oznacza mecz, którego najciekawszy fakt ma wagę ≥ 25 (`PROG_DNIA` w `smaczki/config.py`), np. „nigdy nie wygrał”,
„nie wygrał od 25+ lat”, „pierwszy mecz od 25+ lat”, „pierwszy mecz w historii”.

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
| `python -m smaczki dzis` | mecze dziś i jutro (`--dni 2` = dziś + 2 dni), `raport_dzis.txt` + `site/index.html` (+ powiadomienie, jeśli ustawiony `NTFY_TOPIC`) |
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
z perspektywy gospodarza i gościa, a także serie bramkowe (under/over 2.5, obie strzelą, ten sam wynik),
w dwóch układach:

| Seria | Mecze u gospodarza z tym rywalem | Wszystkie mecze pary (u siebie i na wyjeździe) |
|---|---|---|
| 1 / wygrane gospodarza z rzędu | „Derby County wygrał u siebie z Bolton Wanderers 6 razy z rzędu (od 2015 r.).” | „X wygrał z Y 8 razy z rzędu, u siebie i na wyjeździe (od 2014 r.).” |
| X / remisy z rzędu | „6 remisów z rzędu w meczach u West Bromwich Albion z Millwall (od 2019 r.).” | „5 remisów z rzędu w meczach Blackburn Rovers z West Ham United, u siebie i na wyjeździe (od 2009 r.).” |
| 2 / wygrane gościa z rzędu | „Y wygrał u X 6 razy z rzędu (od 1991 r.).” | „Y wygrał z X 12 razy z rzędu, u siebie i na wyjeździe.” |
| gość nie wygrał (1X) | „Bolton Wanderers nie wygrał u Derby County od 1981 r. (16 meczów) – ostatnio 23.09.1981, 0:2.” | „Swansea City nie wygrał z Birmingham City od 2020 r. (10 meczów, u siebie i na wyjeździe) – ostatnio …” |
| gospodarz nie wygrał (X2) | „Blackburn Rovers nie wygrał u siebie z West Ham United od 2005 r. (5 meczów) – ostatnio 10.12.2005, 3:2.” | „Cardiff City nie wygrał z Burnley od 2012 r. (9 meczów, u siebie i na wyjeździe) – …” |
| bez remisu (12) | „Bez remisu w meczach u Fulham z Newcastle United od 1984 r. (19 meczów) – ostatni remis 03.03.1984, 2:2.” | „Bez remisu w meczach X z Y od … (… meczów, u siebie i na wyjeździe)” |
| under 2.5 | „Najwyżej 2 gole (under 2.5) w 7 meczach z rzędu u West Bromwich Albion z Millwall (od 2018 r.).” | „Najwyżej 2 gole (under 2.5) w 5 meczach z rzędu między Blackburn Rovers a West Ham United (u siebie i na wyjeździe, od 2009 r.).” |
| over 2.5 | „Co najmniej 3 gole (over 2.5) w 5 meczach z rzędu u Preston North End z Southampton (od 2007 r.).” | jak obok, dla wszystkich meczów pary |
| obie strzelą / co najmniej jedna bez gola | „Obie drużyny strzelały w 7 meczach z rzędu u Preston North End z Southampton (od 1966 r.).” | jak obok |
| ten sam dokładny wynik (od 3 meczów) | „Ten sam wynik 0:0 w 4 meczach z rzędu u West Bromwich Albion z Millwall (od 2023 r.).” | „Ten sam wynik 1:0 dla X w 3 meczach z rzędu między X a Y …” |

Gdy seria obejmuje całą historię: „Fulham NIGDY nie wygrał ligowo u Arsenal (31 meczów od 1914 r.)”,
„Mecze u X z Y nigdy nie skończyły się remisem”. Do tego „pierwszy ligowy mecz tych drużyn w historii” i
„pierwszy mecz od X lat”.

**Pokazywane są wszystkie serie pary**, które spełniają próg (bez limitu na mecz):
- co najmniej 4 mecze (ten sam dokładny wynik: 3) i seria rzadsza niż ok. 1 na 20, albo
- „nie wygrał” trwające co najmniej 10 lat i co najmniej 5 meczów.

Dwie serie złożone z dokładnie tych samych meczów są łączone w jedno zdanie, np. „Manchester United wygrał u siebie z Luton
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
| Under 2.5 | 2 619 | 51.2% | 51.3% | 1.80 | −8.3% |
| Over 2.5 | 2 527 | 51.6% | 48.7% | 1.88 | −4.4% |
| BTTS tak | 2 580 | 52.3% | 51.9% | – | brak kursów |
| BTTS nie | 2 041 | 48.0% | 48.1% | – | brak kursów |
| dokładny wynik | 531 | 10.2% | 9.7% | – | brak kursów |
| **1X2 razem** | 15 215 | 62.2% | 57.9% | 1.68 | −6.7% |
| **1X2 razem, mecze z ★** | 4 899 | 60.6% | 54.0% | 1.76 | −8.2% |
| **gole razem** | 5 146 | 51.4% | 50.0% | 1.84 | −6.4% |

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
