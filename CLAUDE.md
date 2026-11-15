# smaczki

Aplikacja „Smaczki meczowe” (Python; 4 ligi angielskie + La Liga, Serie A, Bundesliga 1–2, Ligue 1, Eredivisie; włączane w `ligi.json`):
serie w pojedynkach par, typ meczu, ostateczna predykcja,
strona na GitHub Pages odświeżana przez GitHub Actions (`.github/workflows/smaczki.yml`). Opis i reguły: `README.md`.

- Rozmowa po polsku. Zmiany przez PR; PR scalany dopiero po słowie „scal” od użytkownika.
- Sesje w chmurze: środowisko „Smaczki meczowe” (dostęp do football-data.co.uk).
- Przed commitem: `python -m unittest discover -s tests -t .` (testy na archiwum potrzebują `dane/<kraj>.csv`:
  `python -m smaczki pobierz`).
- Progi i wagi tylko w `smaczki/config.py`. Po zmianie reguł serii przelicz `python -m smaczki skutecznosc`
  (zapisuje `smaczki/skutecznosc.json`, ok. 6 min) i zaktualizuj tabele w README.
- Użytkownik chce tylko serii z rzędu w pojedynkach tej pary (bez formy z innymi rywalami, bez rozkładów
  „X z ostatnich 10”, bez „pierwszy mecz od X lat”). Ostateczny typ = typ najdłuższej serii, potem najwyższy kurs.
- Kraje i ligi: `smaczki/config.py` (`KRAJE`: kody football-data, początek danych, pełna historia / wycinek),
  aliasy per kraj w `smaczki/aliasy/<kraj>.json`. Wycinek historii: bez „nigdy”, z „(dane od X)”, waga × 0,5.
  Kraje: Anglia, Hiszpania, Włochy, Niemcy, Francja, Holandia (innych nie dodawać bez prośby). Brakujący sezon
  w archiwum (Francja 1937/38, `Kraj.brak`): seria, która go obejmuje – zastrzeżenie zamiast „nigdy”.
- Strona: kalendarz dni, w dniu kafelki krajów (★ = liczba meczów ze smaczkami), po kliknięciu ligi kraju.
  Minione dni (7): smaczki sprzed meczu + wynik, ✔ seria utrzymała się / ✘ padła.
- Tylko mecze ligowe. Puchary/baraże/Tarcza Wspólnoty – na razie nie (archiwum tylko do 2019, brak darmowego
  bieżącego źródła; wróć do tematu tylko na prośbę użytkownika, np. z płatnym kluczem API-Football).
