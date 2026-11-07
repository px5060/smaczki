# Smaczki meczowe

Codziennie rano strona na telefon (i opcjonalnie powiadomienie) z odpowiedzią na pytanie:
**czy dziś albo jutro w Premier League, Championship, League One, League Two, La Liga, Serie A, Bundeslidze,
2. Bundeslidze, Ligue 1 albo Eredivisie jest mecz ze smaczkiem z długą historią?** Które kraje i poziomy są włączone, ustala plik [`ligi.json`](ligi.json).

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
| Historia do maja 2025: Anglia od 08.09.1888 (208 028 meczów), Hiszpania od 1929, Włochy od 1929, Niemcy od 1963, Francja od 1933, Holandia od 1956 | [engsoccerdata](https://github.com/jalapic/engsoccerdata), pliki `data-raw/<kraj>.csv`, pobierane automatycznie przy pierwszym użyciu kraju (nie są w repo) | nie |
| Brakujące w archiwum sezony (Anglia 2022/23, Francja 1994/95), wyniki od sezonu 2025/26 i terminarz najbliższych dni | **football-data.co.uk**: pliki `mmz4281/<sezon>/<liga>.csv` (E0–E3, SP1, I1, D1, D2, F1, N1; wyniki aktualizowane ok. 2 razy w tygodniu) i `fixtures.csv` (mecze najbliższych dni) | nie |
| …albo zamiast tego | API-Football v3 (jedno zapytanie na ligę i sezon: ok. 12 przy pierwszym uruchomieniu, potem 4) | tak, `API_FOOTBALL_KEY` |

Domyślnie (`--zrodlo auto`): API-Football, jeśli ustawiony jest klucz, w przeciwnym razie football-data.co.uk.
Gdy API odrzuci zapytanie (np. darmowy plan nie obejmuje bieżącego sezonu), aplikacja wypisze komunikat z API i przejdzie na
football-data.co.uk. Gdy żadne źródło nie działa, liczy na samym archiwum i ostrzega na górze raportu, że dane kończą się 25.05.2025.

Zakończone sezony są zapisywane w `dane/cache/` i nie są pobierane ponownie; bieżący sezon pobierany jest przy każdym uruchomieniu.

## Ligi i kraje

Włączone kraje i poziomy są w pliku **`ligi.json`**; żeby wyłączyć kraj, usuń go albo zostaw pustą listę – bez zmian
w kodzie. Jednorazowo: `--ligi spain,italy` (kraje) albo `--ligi E0,SP1` (kody lig: tylko terminarz tych lig, historia
z poziomów z `ligi.json`). Opis krajów (kody lig, początek danych, czy to pełna historia) jest w `smaczki/config.py`
(`KRAJE`); tam można też dopisać inny kraj z engsoccerdata.

| Kraj | Ligi | Archiwum od | Historia |
|---|---|---|---|
| Anglia | Premier League, Championship, League One, League Two | 1888/89 | pełna (wszystkie 4 poziomy) |
| Hiszpania | La Liga | 1928/29 | pełna historia 1. ligi (przerwa 1936–1939 – wojna domowa) |
| Włochy | Serie A | 1929/30 | pełna historia 1. ligi (przerwa 1943–1945 – wojna) |
| Niemcy | Bundesliga, 2. Bundesliga | 1963/64 (2. BL od 1974/75) | pełna historia obu lig (od ich początku) |
| Francja | Ligue 1 | 1932/33 | pełna historia 1. ligi poza sezonem 1937/38, którego brakuje w archiwum (1994/95 jest uzupełniany z football-data.co.uk) |
| Holandia | Eredivisie | 1956/57 | pełna historia Eredivisie (od jej początku; wcześniejszych mistrzostw nie ma) |

Poza Anglią w danych są tylko niektóre poziomy ligowe, więc smaczki to zaznaczają: „Granada CF NIGDY nie wygrał
w 1. lidze u Valencia CF (27 meczów od 1942 r.)”, „Eintracht Braunschweig NIGDY nie wygrał w 1. i 2. Bundeslidze
u 1. FC Koln (24 mecze od 1964 r.)”, „Go Ahead Eagles NIGDY nie wygrał w Eredivisie u AFC Ajax (35 meczów od 1964 r.)” –
mecze w niższych ligach (i w Niemczech przed Bundesligą, w Holandii przed Eredivisie) nie są liczone. To samo
zastrzeżenie jest przy bilansach w „Pokaż wyniki”, w karcie pary (`mecz`) i w rankingu.

**Francja 1937/38:** tego sezonu nie ma w archiwum (ani w football-data.co.uk). Seria, w czasie której para mogła
zagrać w tym sezonie (obie drużyny grały w 1. lidze w 1936/37 albo 1938/39), nie dostaje słowa „nigdy”, tylko
zastrzeżenie „(w danych brak sezonu 1937/38)”, i ma o połowę niższą wagę. Wśród obecnych drużyn Ligue 1 nie dotyczy
to żadnej obecnej serii.

**Początek danych to nie zawsze początek historii.** Dla kraju, którego archiwum jest tylko wycinkiem historii
(`pelna=False` w `config.KRAJE`, np. gdyby dopisać Szkocję od 1994), słowa „nigdy” nie ma: „X nie wygrał u Y w żadnym
z 45 meczów ligowych od 1994 r. (dane od 1994)”, a waga takiej serii jest o połowę niższa (`WAGA_WYCINKA`).

Uzupełnienie od maja 2025 działa jak dla Anglii (football-data.co.uk ma wszystkie te ligi, sezony 2025/26 i 2026/27).
Raport podaje **dla każdej ligi** datę ostatniego meczu w historii, liczbę dopisanych meczów i ostrzeżenie, gdy luka nie
jest zamknięta (źródło nie zwróciło wyników któregoś sezonu). Ten sam mecz z archiwum i ze źródła bieżącego (ta sama
data i para) jest liczony raz, a sezon, który jest w archiwum, zostaje z archiwum.

### Kompletność historii (Anglia)

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
przy każdym dniu liczba meczów z ★. Po wybraniu dnia: **kafelki krajów** (Anglia, Hiszpania, Włochy, Niemcy, Francja, Holandia) – na kafelku
**★ i liczba meczów ze smaczkami**, liczba meczów tego dnia i ile z nich ma długą historię. Kliknięcie kafelka pokazuje
**ligi kraju** jako rozwijane zakładki z licznikami (Anglia: Premier League, Championship, League One, League Two; Niemcy: Bundesliga i 2. Bundesliga;
kraj z jedną ligą: od razu rozwinięta); po rozwinięciu mecze ze smaczkami, od najciekawszego. Ponowne
kliknięcie kafelka go zamyka. Wybrany dzień i kraj są zapamiętane w adresie (#RRRR-MM-DD/kraj).
**Mecze bez żadnej serii** (1X2, under/over, obie strzelą, dokładny wynik) **nie są pokazywane**; liga bez nich
ma dopisek „brak smaczków”. Na dole dnia **ostateczna predykcja dnia** i pod nią **wszystkie typy dnia**: każdy mecz z serią
w jednej linii (godzina, mecz, ostateczny typ, kurs, długość serii), od najdłuższej serii.

Kliknięcie w **smaczek** („mecze serii ▾”), w typ na liście typów dnia albo w „★ OSTATECZNY TYP” przy meczu rozwija
mecze pary, z których wynika seria: **obecna seria na zielono**, **wcześniejsze serie między drużynami na niebiesko** –
każdego rodzaju, nie tylko takie jak obecny smaczek (wygrane, remisy, „bez wygranej”, „bez remisu”, gole, ten sam wynik),
o ile w chwili przerwania spełniały próg smaczka (ta sama zasada co dla obecnych serii); pozostałe mecze – bez tła.
Pod legendą spis wcześniejszych serii z latami, np. „2008–2020: Birmingham City bez wygranej z Swansea City – 6 meczów;
1982–1995: poniżej 2.5 bramki 10 razy z rzędu; 1953–1980: Birmingham City wygrał 6 razy z rzędu”. To samo zaznaczenie
(zielone i niebieskie) jest w tabelach „Pokaż wyniki”.

### Podgląd wyników

Na stronie każdy mecz ma przycisk **„Pokaż wyniki”**: wszystkie mecze ligowe u gospodarza z tym rywalem (od najnowszego,
z bilansem; wygrane gości wyróżnione), a niżej rozwijane **rewanże** (mecze u gościa) i **wszystkie mecze pary**
(u siebie i na wyjeździe, W/R/P z perspektywy gospodarza). **Mecze obecnej serii są tam zaznaczone na zielono**: w tabeli
meczów u gospodarza – najdłuższa seria „u gospodarza”, we wszystkich meczach pary – najdłuższa seria „u siebie i na
wyjeździe” (gdy smaczek dotyczy tylko takiej serii, ta tabela jest od razu rozwinięta). Wyniki spoza archiwum
engsoccerdata są oznaczone „°”. Na dole strony sekcja
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
| `python -m smaczki kolejka` | najbliższe 7 dni (`--dni N` albo `--od 2026-11-07 --do 2026-11-09`), pogrupowane po kraju i lidze, w grupie od najciekawszego, `raport_kolejka.txt` |
| `python -m smaczki kolejka --plik-meczow mecze.csv` | własna lista meczów (kolumny `home,away,date,liga`; `date` i `liga` opcjonalne; `liga` = kod ligi z konfiguracji, np. `E1`, `SP1`, `I1`, albo nazwa ligi lub kraju; puste = Anglia) |
| `python -m smaczki mecz "Derby" "Bolton"` | pełna karta pary: bilans u gospodarza, ostatnie wygrane, serie, średnia goli, 0:0, najwyższe zwycięstwa, bilans wszystkich meczów, forma (`--wyniki`: lista wszystkich meczów u gospodarza). Kraj jest wykrywany po nazwach (`mecz "Atlético Madrid" Getafe`), można go podać: `--ligi spain` |
| `python -m smaczki ranking --top 25 [--tier 1] [--ligi italy]` | najdłuższe passy „gość nie wygrał u rywala od X lat” wśród par grających ze sobą w ostatnich 3 latach (domyślnie Anglia) |
| `python -m smaczki nazwy` | kontrola dopasowania nazw drużyn ze źródła do archiwum (każdy kraj osobno) |
| `python -m smaczki skutecznosc` | przelicza skuteczność typów na historii z kursami (od 2005/06) |

Opcje wspólne: `--zrodlo auto|fd|api|brak`, `--dane FOLDER` (domyślnie `dane`), `--archiwum ŚCIEŻKA` (folder z plikami
krajów, np. `engsoccerdata/data-raw`), `--ligi …` i `--plik-lig PLIK` (domyślnie `ligi.json`), w trybach terminarza
także `--wszystkie` (pokaż też mecze bez smaczków).

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
| ten sam dokładny wynik (od 3 meczów) | „Ten sam wynik 0:0 w 4 meczach z rzędu u West Bromwich Albion z Millwall (od 2023 r.).” | „Ten sam wynik 1:0 dla X w 3 meczach z rzędu między X a Y …” |

Gdy seria obejmuje całą historię: „Fulham NIGDY nie wygrał ligowo u Arsenal (31 meczów od 1914 r.)”,
„Mecze u X z Y nigdy nie skończyły się remisem”. „Pierwszy ligowy mecz tych drużyn w historii” jest tylko
informacją (bez ★ i bez typu); „pierwszy mecz od X lat” nie jest pokazywany.

W tabelach „Pokaż wyniki” jest kolumna 2.5 (pow./pon.).

**Pokazywane są wszystkie serie pary**, które spełniają próg (bez limitu na mecz):
- co najmniej 4 mecze (powyżej/poniżej 2.5 bramki i „obie strzelą”: co najmniej 8 meczów; ten sam dokładny
  wynik: 3) i seria rzadsza niż ok. 1 na 20, albo
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
| Under 2.5 | 373 | 52.0% | 51.3% | 1.80 | −7.1% |
| Over 2.5 | 307 | 50.8% | 48.7% | 1.85 | −7.7% |
| BTTS tak | 396 | 58.8% | 51.9% | – | brak kursów |
| BTTS nie | 187 | 53.5% | 48.0% | – | brak kursów |
| dokładny wynik | 531 | 10.2% | 9.7% | – | brak kursów |
| **1X2 razem** | 15 215 | 62.2% | 57.9% | 1.68 | −6.7% |
| **1X2 razem, mecze z ★** | 4 711 | 60.4% | 53.7% | 1.77 | −8.3% |
| **gole razem** | 680 | 51.5% | 50.1% | 1.82 | −7.4% |

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

Ostateczny typ (jeden na mecz):

| Ostateczny typ | Typów | Trafione | Przeciętnie | Śr. kurs | Zwrot |
|---|---|---|---|---|---|
| z rynku 1X2 | 14 923 | 67.8% | 64.0% | 1.48 | −5.9% |
| obie strzelą | 400 | 57.5% | 50.9% | – | brak kursów |
| z rynku goli | 544 | 49.8% | 50.1% | 1.84 | −9.3% |
| dokładny wynik | 150 | 7.3% | 9.5% | – | brak kursów |
| **razem, z kursem** | 15 467 | 67.1% | 63.5% | 1.49 | −6.0% |
| **razem, z kursem, mecze z ★** | 4 926 | 68.8% | 63.2% | 1.46 | −5.8% |
| **ostateczna predykcja dnia** (najdłuższa seria dnia; liczba = dni) | 2 858 | 71.9% | 66.6% | 1.37 | −5.3% |

Serie wykluczały się w 0 meczach (1X2) i w 0 meczach (gole).

**Wniosek:** typy z serii trafiają nieco częściej niż przeciętnie, ale kursy już to uwzględniają. W sumie zwrot
jest podobny jak przy obstawianiu na ślepo (marża bukmachera). Bukmacherzy znają te serie, więc **to nie są typy
z przewagą nad kursem**; aplikacja pokazuje je razem z wynikami, żeby było to widać.

Przeliczenie (np. po sezonie): `python -m smaczki skutecznosc` – pobiera ok. 100 plików z kursami (raz, potem cache)
i zapisuje `smaczki/skutecznosc.json`.

## Nazwy drużyn

Aliasy są **osobno dla każdego kraju**: `smaczki/aliasy/<kraj>.json` (ten sam skrót może znaczyć różne kluby w różnych
krajach). Sekcje pliku:
- `aliasy` – nazwa ze źródła → nazwa w archiwum (np. `"Ath Madrid": "Atletico Madrid"`, `"Espanol": "Espanyol Barcelona"`),
- `archiwum` – ten sam klub zapisany w archiwum pod kilkoma nazwami → jedna nazwa, żeby historia pary się nie rozpadała
  (np. Parma AC → Parma FC, Feijenoord → Feyenoord, TSV 1860 Munchen → 1860 Munchen, FC Den Haag → ADO Den Haag),
- `archiwum_sezony` – odwrotnie: dwa różne kluby pod jedną nazwą w archiwum, rozdzielone po sezonach (np. sezon 2015/16
  „AC Ajaccio” to w rzeczywistości Gazelec Ajaccio),
- `nowe_kluby` – nazwy, które nie są klubem z archiwum, choć brzmią podobnie (nowy klub bez historii),
- `uwagi` – wyjaśnienia decyzji.

Zasada: zmiana nazwy albo pisowni → jeden klub; fuzja albo klub o innej osobowości prawnej (np. obecny i dawny
Accrington, CD Malaga 1904–1992 i Malaga CF) → osobno; we Włoszech klub odbudowany po upadłości zachowuje historię
(tak liczy ją FIGC). Sprawdzone na danych: nazwy z football-data.co.uk z sezonów 1993/94–2024/25 zostały dopasowane do
archiwum po dacie i wyniku meczu.

Kolejność dopasowania: alias, dokładna nazwa (także bez znaków diakrytycznych: „Atlético Madrid” → „Atletico Madrid”,
„Cádiz” → „Cadiz CF”), nazwa zawarta w nazwie z archiwum („Luton” → „Luton Town”; przy kilku kandydatach wybierany jest klub, który
grał najpóźniej, np. obecny „Accrington”, a nie „Accrington Stanley” z lat 1921–1962), podobieństwo tekstu (difflib, próg
0,75). Nazwa bez dopasowania zostaje bez zmian (nowy klub bez historii), a aplikacja po każdym uruchomieniu wypisuje
listę takich nazw **z najbliższymi kandydatami z archiwum**, żeby łatwo dopisać alias (albo nazwę do `nowe_kluby`).
Wszystkie nazwy z football-data.co.uk z sezonów 2025/26 i 2026/27 (wszystkie włączone kraje) są sprawdzane w testach.

## Testy

```
python -m unittest discover -s tests -t .
```

Kryteria akceptacji z briefu na prawdziwym archiwum (plus wykrycie luki 2022/23) (Arsenal – Fulham, Manchester United – Luton, Derby – Lincoln,
Wolves – Sheffield United, Luton – Portsmouth, Bradford – Accrington), kryteria briefu lig (`tests/test_ligi.py`:
Granada – Valencia, Cremonese – Lazio, Braunschweig – Köln, Le Havre – Marsylia, Go Ahead Eagles – Ajax,
Francja 1937/38, „w 1. lidze”, wycinek historii bez „nigdy”, diakrytyki, brak duplikatów na styku
danych, aliasy, raport per liga, kafelki krajów na stronie) oraz ścieżki API-Football i football-data.co.uk na
zamockowanych odpowiedziach (dopisanie wyników, uzupełnienie brakującego sezonu, terminarz tylko z `NS/TBD` w zakresie
dat, cache, budżet zapytań, mapowanie nazw, błąd planu), tryb bez klucza, podgląd wyników na stronie i powiadomienia. Testy na archiwum są pomijane, jeśli nie ma `dane/<kraj>.csv` (`python -m smaczki pobierz`).

## Ograniczenia

- Tylko mecze ligowe (bez pucharów).
- Kluby, które grały poza ligami z danych (np. w National League, w 2. lidze Hiszpanii, Włoch, Francji czy Holandii,
  w 3. lidze Niemiec),
  nie mają w danych meczów z tego okresu.
- Skuteczność typów („w przeszłości …”) jest policzona na 4 ligach angielskich i pokazywana także przy meczach innych lig.
- Bez polskiej ligi (brak w archiwum).
- „U drużyny X” = mecze, w których X był gospodarzem (bez rozróżniania stadionów).
- football-data.co.uk dopisuje wyniki z opóźnieniem do kilku dni; na serie gospodarz–gość to nie wpływa
  (para gra u danego gospodarza raz w sezonie), najwyżej na serie formy.
- Licencja engsoccerdata: dane nie są redystrybuowane (pobiera je każdy użytkownik), przed ewentualnym udostępnianiem
  surowych danych sprawdź licencję repozytorium.
