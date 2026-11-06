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
z bilansem; wygrane gości wyróżnione), a niżej rozwijane **rewanże** i **forma** (ostatnie 10 meczów gospodarza u siebie
i gościa na wyjeździe). Wyniki spoza archiwum engsoccerdata są oznaczone „°”. Na dole strony sekcja
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

Opcje wspólne: `--zrodlo auto|fd|api|brak`, `--dane FOLDER` (domyślnie `dane`), `--archiwum ŚCIEŻKA` (własna kopia
`england.csv` albo folder `engsoccerdata/data-raw`), w trybach terminarza także `--wszystkie` (pokaż też mecze bez smaczków).

## Reguły smaczków

Liczone na historii ligowej sprzed dnia meczu. Każdy fakt ma wagę; przy meczu widać maks. 4 fakty, od najciekawszego.

| Fakt | Warunek | Waga |
|---|---|---|
| Pierwszy ligowy mecz drużyn w historii | brak meczów H2H | 30 |
| Pierwszy mecz od wielu lat | ostatni H2H ≥ 10 lat temu | liczba lat |
| Gość nigdy nie wygrał u gospodarza | 0 wygranych, ≥ 5 meczów | 40 + liczba meczów |
| Gość nie wygrał u gospodarza od X lat | ≥ 10 lat i ≥ 3 mecze od ostatniej wygranej | liczba lat |
| Gość bez porażki u gospodarza | seria ≥ 4 | 4 × seria |
| Gość wygrał u gospodarza z rzędu | seria ≥ 3 | 6 × seria |
| Gospodarz nigdy nie wygrał u siebie z gościem | 0 wygranych, ≥ 4 mecze | 35 + liczba meczów |
| Gospodarz nie wygrał u siebie z gościem | ≥ 4 mecze bez wygranej albo ≥ 10 lat i ≥ 3 mecze | max(lata, 4 × mecze) |
| Gospodarz wygrał u siebie z rzędu | seria ≥ 5 | 3 × seria |
| Forma gospodarza u siebie / gościa na wyjeździe | seria bez porażki albo bez wygranej ≥ 8 | 1,5 × seria |

Wszystkie progi są w `smaczki/config.py`.

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
