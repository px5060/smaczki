"""Kryteria akceptacji z briefu – na prawdziwym archiwum engsoccerdata (dane do 25.05.2025).

Wymaga pliku dane/england.csv (python -m smaczki pobierz); bez niego testy są pomijane.
"""
import os
import unittest

from smaczki.data_loader import wczytaj_archiwum
from smaczki.names import ALIASY, Nazwy
from smaczki.rules import karta_meczu, smaczki

ARCHIWUM = os.environ.get("SMACZKI_ARCHIWUM",
                          os.path.join(os.path.dirname(__file__), "..", "dane", "england.csv"))

# Wszystkie nazwy z football-data.co.uk z sezonów 2025/26 i 2026/27 (+ "Dag and Red" z 2010/11)
NAZWY_FD = """AFC Wimbledon|Accrington|Arsenal|Aston Villa|Barnet|Barnsley|Barrow|Birmingham|Blackburn|Blackpool|Bolton|
Bournemouth|Bradford|Brentford|Brighton|Bristol City|Bristol Rvs|Bromley|Burnley|Burton|Cambridge|Cardiff|Charlton|Chelsea|
Cheltenham|Chesterfield|Colchester|Coventry|Crawley Town|Crewe|Crystal Palace|Derby|Doncaster|Everton|Exeter|Fleetwood Town|
Fulham|Gillingham|Grimsby|Harrogate|Huddersfield|Hull|Ipswich|Leeds|Leicester|Leyton Orient|Lincoln|Liverpool|Luton|
Man City|Man United|Mansfield|Middlesbrough|Millwall|Milton Keynes Dons|Newcastle|Newport County|Northampton|Norwich|
Nott'm Forest|Notts County|Oldham|Oxford|Peterboro|Plymouth|Port Vale|Portsmouth|Preston|QPR|Reading|Rochdale|Rotherham|
Salford|Sheffield United|Sheffield Weds|Shrewsbury|Southampton|Stevenage|Stockport|Stoke|Sunderland|Swansea|Swindon|
Tottenham|Tranmere|Walsall|Watford|West Brom|West Ham|Wigan|Wolves|Wrexham|Wycombe|York|Dag and Red"""


def teksty(fakty):
    return "\n".join(f.tekst for f in fakty)


@unittest.skipUnless(os.path.exists(ARCHIWUM), "brak dane/england.csv – uruchom: python -m smaczki pobierz")
class TestArchiwum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hist = wczytaj_archiwum(ARCHIWUM)
        cls.nazwy = Nazwy(cls.hist)

    def test_koniec_archiwum(self):
        self.assertEqual(self.hist.Date.max().strftime("%d.%m.%Y"), "25.05.2025")

    def test_luka_2022_23(self):
        from smaczki.data_loader import luki_archiwum
        self.assertEqual(luki_archiwum(self.hist), [2022])

    def test_arsenal_fulham(self):
        f = smaczki(self.hist, "Arsenal", "Fulham")
        self.assertIn("Fulham NIGDY nie wygrał ligowo u Arsenal (31 meczów od 1914 r.)", f[0].tekst)

    def test_man_utd_luton(self):
        t = teksty(smaczki(self.hist, "Manchester United", "Luton Town"))
        self.assertIn("Manchester United wygrał u siebie z Luton Town 19 razy z rzędu", t)
        self.assertIn("Luton Town nie wygrał u Manchester United od 1897 r. (ostatnio 18.09.1897, 1:2)", t)
        self.assertIn("Mecze u Manchester United z Luton Town nigdy nie skończyły się remisem (20 meczów", t)

    def test_derby_lincoln(self):
        t = teksty(smaczki(self.hist, "Derby County", "Lincoln City"))
        self.assertIn("Lincoln City NIGDY nie wygrał ligowo u Derby County (13 meczów od 1907 r.)", t)
        self.assertIn("Derby County wygrał u siebie z Lincoln City 13 razy z rzędu", t)

    def test_wolves_sheffield(self):
        h, v = self.nazwy("Wolves"), self.nazwy("Sheffield Utd")
        self.assertEqual((h, v), ("Wolverhampton Wanderers", "Sheffield United"))
        self.assertIn("Sheffield United nie wygrał u Wolverhampton Wanderers od 2002 r. (9 meczów) – ostatnio 05.10.2002",
                      teksty(smaczki(self.hist, h, v)))

    def test_luton_portsmouth(self):
        k = "\n".join(karta_meczu(self.hist, "Luton Town", "Portsmouth"))
        self.assertIn("Ostatnia wygrana Portsmouth u Luton Town: 22.11.2016 (1:3)", k)
        self.assertIn("16 wygranych gospodarzy, 5 remisów, 4 wygranych Portsmouth", k)

    def test_bradford_accrington(self):
        h, v = self.nazwy("Bradford"), self.nazwy("Accrington ST")
        self.assertEqual((h, v), ("Bradford City", "Accrington"))
        self.assertEqual(self.nazwy("Accrington Stanley"), "Accrington")  # nie dawny klub 1921–1962
        self.assertIn("Accrington nie wygrał u Bradford City od 2007 r. (8 meczów) – ostatnio 02.10.2007",
                      teksty(smaczki(self.hist, h, v)))

    def test_pierwszy_mecz(self):
        f = smaczki(self.hist, "Arsenal", "Bromley")
        self.assertEqual((f[0].waga, f[0].tekst), (30, "Pierwszy ligowy mecz tych drużyn w historii."))

    def test_aliasy_wskazuja_kluby_z_archiwum(self):
        brak = sorted(set(ALIASY.values()) - set(self.nazwy.ostatni_mecz))
        self.assertEqual(brak, [])

    def test_nazwy_football_data(self):
        nazwy = [n.strip() for n in NAZWY_FD.replace("\n", "").split("|")]
        mapa = {n: self.nazwy(n) for n in nazwy}
        self.assertEqual(self.nazwy.niedopasowane, set())
        self.assertTrue(all(m in self.nazwy.ostatni_mecz for m in mapa.values()))
        self.assertEqual(len(set(mapa.values())), len(nazwy))  # różne nazwy -> różne kluby
        for zrodlo, oczekiwane in [("Man United", "Manchester United"), ("Man City", "Manchester City"),
                                   ("Sheffield Weds", "Sheffield Wednesday"), ("Nott'm Forest", "Nottingham Forest"),
                                   ("Leeds", "Leeds United"), ("Brighton", "Brighton & Hove Albion"),
                                   ("Wigan", "Wigan Athletic"), ("Peterboro", "Peterborough United"),
                                   ("Bournemouth", "AFC Bournemouth"), ("AFC Wimbledon", "AFC Wimbledon")]:
            self.assertEqual(mapa[zrodlo], oczekiwane)


if __name__ == "__main__":
    unittest.main()
