"""Ścieżki API-Football i football-data.co.uk na zamockowanych odpowiedziach + CLI z kluczem i bez."""
import contextlib
import datetime as dt
import io
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from smaczki import data_loader as dl
from smaczki.cli import main
from smaczki.report import powiadomienie, Pozycja
from smaczki.rules import Fakt, mecze

ARCHIWUM_CSV = """Date,Season,home,visitor,FT,hgoal,vgoal,division,tier
1995-09-10,1995,Wolverhampton Wanderers,Sheffield United,1-0,1,0,2,2
2002-10-05,2002,Wolverhampton Wanderers,Sheffield United,1-3,1,3,2,2
2020-10-10,2020,Wolverhampton Wanderers,Sheffield United,1-0,1,0,1,1
2021-03-03,2020,Sheffield United,Wolverhampton Wanderers,0-2,0,2,1,1
2024-02-02,2023,Luton Town,Manchester United,1-2,1,2,1,1
2025-05-25,2024,Manchester United,Luton Town,2-0,2,0,1,1
"""


def fx(data, status, home, away, gh=None, ga=None):
    return {"fixture": {"date": data, "status": {"short": status}},
            "teams": {"home": {"name": home}, "away": {"name": away}},
            "goals": {"home": gh, "away": ga}}


ODPOWIEDZI_API = {
    (39, 2025): [fx("2025-09-20T16:00:00+02:00", "FT", "Wolves", "Sheffield Utd", 1, 2)],
    (39, 2026): [
        fx("2026-08-30T16:00:00+02:00", "FT", "Man United", "Luton", 3, 0),
        fx("2026-11-07T16:00:00+01:00", "NS", "Sheffield Utd", "Wolves"),
        fx("2026-11-08T00:00:00+01:00", "TBD", "Luton", "Man United"),
        fx("2026-11-07T13:30:00+01:00", "PST", "Luton", "Wolves"),       # przełożony – pomijamy
        fx("2026-11-20T16:00:00+01:00", "NS", "Wolves", "Luton"),        # poza zakresem dat
        fx("2026-11-01T16:00:00+01:00", "AET", "Man City", "Wolves", 2, 2),
    ],
}


class Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        with open(os.path.join(self.tmp, "england.csv"), "w", encoding="utf-8") as f:
            f.write(ARCHIWUM_CSV)
        self.cache = os.path.join(self.tmp, "cache")

    def tearDown(self):
        self._tmp.cleanup()


class TestAPI(Tmp):
    def fake(self, params):
        self.wywolania.append((params["league"], params["season"]))
        return ODPOWIEDZI_API.get((params["league"], params["season"]), [])

    def zbierz(self):
        with mock.patch.dict(os.environ, {"API_FOOTBALL_KEY": "test"}), \
                mock.patch.object(dl, "api_zapytanie", side_effect=self.fake):
            return dl.zbierz(self.tmp, self.cache, "auto", dt.date(2026, 11, 6),
                             dt.date(2026, 11, 6), dt.date(2026, 11, 13))

    def test_dopisanie_wynikow_terminarz_i_nazwy(self):
        self.wywolania = []
        d = self.zbierz()
        self.assertIn("API-Football", d.zrodlo)
        nowe = d.hist[d.hist.Date >= "2025-06-01"]
        self.assertEqual(
            sorted(map(tuple, nowe[["home", "visitor", "hgoal", "vgoal"]].values.tolist())),
            [("Manchester City", "Wolverhampton Wanderers", 2, 2),
             ("Manchester United", "Luton Town", 3, 0),
             ("Wolverhampton Wanderers", "Sheffield United", 1, 2)])
        self.assertEqual([(m.home, m.away, m.data) for m in d.terminarz],
                         [("Sheffield Utd", "Wolves", dt.datetime(2026, 11, 7, 16, 0)),
                          ("Luton", "Man United", dt.datetime(2026, 11, 8, 0, 0))])
        self.assertEqual(d.nazwy("Sheffield Utd"), "Sheffield United")
        self.assertEqual(d.nazwy.niedopasowane, set())

    def test_budzet_zapytan_i_cache(self):
        self.wywolania = []
        self.zbierz()
        self.assertEqual(len(self.wywolania), 8)  # 4 ligi x sezony 2025 i 2026
        self.assertTrue(os.path.exists(os.path.join(self.cache, "api_39_2025.json")))
        self.assertFalse(os.path.exists(os.path.join(self.cache, "api_39_2026.json")))
        self.wywolania = []
        self.zbierz()
        self.assertEqual(sorted(self.wywolania), [(39, 2026), (40, 2026), (41, 2026), (42, 2026)])

    def test_blad_planu_przechodzi_na_football_data(self):
        blad = dl.BladDanych(dl._api_bledy({"plan": "Free plans do not have access to this season, "
                                                     "try from 2021 to 2023."}, {"league": 39, "season": 2026}))
        pusty = (pd.DataFrame(columns=dl.KOLUMNY), [])
        with mock.patch.dict(os.environ, {"API_FOOTBALL_KEY": "test"}), \
                mock.patch.object(dl, "api_zapytanie", side_effect=blad), \
                mock.patch.object(dl, "fd_dane", return_value=pusty):
            d = dl.zbierz(self.tmp, self.cache, "auto", dt.date(2026, 11, 6), dt.date(2026, 11, 6),
                          dt.date(2026, 11, 7))
        self.assertIn("football-data.co.uk", d.zrodlo)
        self.assertIn("Free plans do not have access", d.ostrzezenia[0])
        self.assertIn("--zrodlo fd", d.ostrzezenia[0])

    def test_rapidapi(self):
        with mock.patch.dict(os.environ, {"API_FOOTBALL_KEY": "k", "API_FOOTBALL_HOST": "api-football-v1.p.rapidapi.com"}):
            _, url, nagl = dl._api_konfig()
        self.assertEqual(url, "https://api-football-v1.p.rapidapi.com/v3/fixtures")
        self.assertEqual(nagl["x-rapidapi-host"], "api-football-v1.p.rapidapi.com")


FIXTURES = ("﻿Div,Date,Time,HomeTeam,AwayTeam,Referee,B365H\n"
            "E0,07/11/2026,15:00,Arsenal,Hull,,1.2\n"
            "SP1,07/11/2026,15:00,Real Madrid,Getafe,,1.1\n"
            "E1,10/11/2026,19:45,Derby,Bolton,,2.0\n"
            "E3,06/11/2026,19:45,Walsall,Barrow,,2.1\n")

WYNIKI_E0 = ("﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
             "E0,22/08/2026,15:00,Wolves,Man United,2,1,H\n"
             "E0,23/08/2026,15:00,Arsenal,Hull,,,\n").encode("utf-8")


class TestFootballData(Tmp):
    def test_terminarz(self):
        t = dl.fd_terminarz_z_tekstu(FIXTURES, dt.date(2026, 11, 6), dt.date(2026, 11, 7))
        self.assertEqual([(m.liga, m.home, m.away, m.data) for m in t],
                         [("Premier League", "Arsenal", "Hull", dt.datetime(2026, 11, 7, 16, 0)),
                          ("League Two", "Walsall", "Barrow", dt.datetime(2026, 11, 6, 20, 45))])

    def test_wyniki_i_cache(self):
        def get(url):
            wywolania.append(url)
            return WYNIKI_E0 if url.endswith("/2627/E0.csv") else None  # pozostałe ligi: 404

        wywolania = []
        with mock.patch.object(dl, "_fd_get", side_effect=get):
            w = dl.fd_wyniki(2026, self.cache, biezacy=True)
            self.assertEqual(w[["home", "visitor", "hgoal", "vgoal", "tier"]].values.tolist(),
                             [["Wolves", "Man United", 2, 1, 1]])
            self.assertFalse(os.path.exists(os.path.join(self.cache, "fd_2627_E0.csv")))
            dl.fd_wyniki(2026, self.cache, biezacy=False)  # sezon zakończony -> zapis do cache
            self.assertTrue(os.path.exists(os.path.join(self.cache, "fd_2627_E0.csv")))
            wywolania.clear()
            w = dl.fd_wyniki(2026, self.cache, biezacy=False)
            self.assertNotIn("https://www.football-data.co.uk/mmz4281/2627/E0.csv", wywolania)
            self.assertEqual(len(w), 1)


class TestCLI(Tmp):
    def uruchom(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            main(list(argv))
        return out.getvalue()

    def test_bez_klucza_z_plikiem_meczow(self):
        mecze_csv = os.path.join(self.tmp, "mecze.csv")
        with open(mecze_csv, "w", encoding="utf-8") as f:
            f.write("home,away,date,liga\nWolves,Sheffield Utd,2026-11-07 16:00,Championship\nLuton,Arsenal,,\n")
        raport = os.path.join(self.tmp, "r.txt")
        tekst = self.uruchom("kolejka", "--zrodlo", "brak", "--dane", self.tmp, "--plik-meczow", mecze_csv,
                             "--raport", raport, "--wszystkie")
        self.assertIn("UWAGA: brak danych bieżących – historia kończy się 25.05.2025", tekst)
        self.assertIn("Wolverhampton Wanderers – Sheffield United", tekst)
        self.assertIn("Pierwszy ligowy mecz tych drużyn w historii.", tekst)  # Luton – Arsenal w mini-archiwum
        self.assertTrue(os.path.exists(raport))

    def test_dzis_strona_i_powiadomienie(self):
        wyniki = pd.DataFrame([{"Date": pd.Timestamp("2026-09-01"), "home": "Wolves", "visitor": "Luton",
                                "hgoal": 1, "vgoal": 0, "tier": 2}])
        term = [dl.Mecz(dt.datetime(2026, 11, 6, 20, 45), "Championship", "Luton", "Sheffield Utd"),
                dl.Mecz(dt.datetime(2026, 11, 7, 16, 0), "Championship", "Wolves", "Sheffield Utd")]
        html = os.path.join(self.tmp, "site", "index.html")
        argv = ["dzis", "--dzis", "2026-11-06", "--zrodlo", "fd", "--dane", self.tmp, "--html", html,
                "--raport", os.path.join(self.tmp, "r.txt"), "--ntfy", "test-temat"]
        with mock.patch.object(dl, "fd_dane", return_value=(wyniki, term)), \
                mock.patch("smaczki.cli.urllib.request.urlopen") as urlopen:
            self.uruchom(*argv)
            self.uruchom(*argv)  # drugie uruchomienie tego samego dnia – bez drugiego powiadomienia
        with open(html, encoding="utf-8") as f:
            strona = f.read()
        self.assertIn("Dziś · piątek 6 listopada", strona)
        self.assertIn("Jutro · sobota 7 listopada", strona)
        self.assertIn("Luton Town – Sheffield United", strona)
        self.assertEqual(urlopen.call_count, 1)
        req = urlopen.call_args[0][0]
        self.assertIn("ntfy.sh/test-temat?title=Smaczki", req.full_url)
        self.assertIn("Luton Town – Sheffield United", req.data.decode("utf-8"))


class TestRaport(unittest.TestCase):
    def test_odmiana(self):
        self.assertEqual([mecze(n) for n in (1, 2, 5, 12, 22, 25, 112, 104)],
                         ["1 mecz", "2 mecze", "5 meczów", "12 meczów", "22 mecze", "25 meczów",
                          "112 meczów", "104 mecze"])

    def test_powiadomienie_tylko_dluga_historia_z_dzisiaj(self):
        dzis = dt.datetime(2026, 11, 6, 21, 0)
        p = [Pozycja(dzis, "PL", "A", "B", [Fakt(45, "B NIGDY nie wygrał u A.")]),
             Pozycja(dzis, "PL", "C", "D", [Fakt(12, "seria")]),
             Pozycja(dzis + dt.timedelta(days=1), "PL", "E", "F", [Fakt(60, "jutro")])]
        tytul, tresc = powiadomienie(p, dzis.date())
        self.assertEqual(tytul, "Smaczki pt 06.11: 1 mecz z długą historią")
        self.assertEqual(tresc, "21:00 A – B: B NIGDY nie wygrał u A.")
        self.assertIsNone(powiadomienie(p[1:2], dzis.date()))


if __name__ == "__main__":
    unittest.main()
