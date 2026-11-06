# smaczki

Aplikacja „Smaczki meczowe” (Python, 4 ligi angielskie): serie w pojedynkach par, typ meczu, ostateczna predykcja,
strona na GitHub Pages odświeżana przez GitHub Actions (`.github/workflows/smaczki.yml`). Opis i reguły: `README.md`.

- Rozmowa po polsku. Zmiany przez PR; PR scalany dopiero po słowie „scal” od użytkownika.
- Sesje w chmurze: środowisko „Smaczki meczowe” (dostęp do football-data.co.uk).
- Przed commitem: `python -m unittest discover -s tests -t .` (testy na archiwum potrzebują `dane/england.csv`:
  `python -m smaczki pobierz`).
- Progi i wagi tylko w `smaczki/config.py`. Po zmianie reguł serii przelicz `python -m smaczki skutecznosc`
  (zapisuje `smaczki/skutecznosc.json`, ok. 6 min) i zaktualizuj tabele w README.
- Użytkownik chce tylko serii z rzędu w pojedynkach tej pary (bez formy z innymi rywalami, bez rozkładów
  „X z ostatnich 10”, bez „pierwszy mecz od X lat”). Ostateczny typ = typ najdłuższej serii, potem najwyższy kurs.
