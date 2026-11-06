"""Ścieżki API-Football i football-data.co.uk na zamockowanych odpowiedziach + CLI z kluczem i bez."""
import contextlib
import datetime as dt
import io
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from smaczki import config as C
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
        # mini-archiwum ma tylko kilka sezonów – wykrywanie luk sprawdza osobny test
        luki = mock.patch.object(C, "LUKI_OD_SEZONU", 2024)
        luki.start()
        self.addCleanup(luki.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        with open(os.path.join(self.tmp, "england.csv"), "w", encoding="utf-8") as f:
            f.write(ARCHIWUM_CSV)
        self.cache = os.path.join(self.tmp, "cache")
        # testy CLI na samej Anglii (ligi.json z repo włącza też inne kraje)
        with open(os.path.join(self.tmp, "ligi.json"), "w", encoding="utf-8") as f:
            f.write('{"england": [1, 2, 3, 4]}')
        plik_lig = mock.patch.object(C, "PLIK_LIG", os.path.join(self.tmp, "ligi.json"))
        plik_lig.start()
        self.addCleanup(plik_lig.stop)

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


FIXTURES = ("\ufeffDiv,Date,Time,HomeTeam,AwayTeam,Referee,B365H,AvgH,AvgD,AvgA\n"
            "E0,07/11/2026,15:00,Arsenal,Hull,,1.2,1.25,6.0,11.0\n"
            "SP1,07/11/2026,15:00,Real Madrid,Getafe,,1.1,1.1,8,20\n"
            "E1,10/11/2026,19:45,Derby,Bolton,,2.0,2.6,3.5,2.5\n"
            "E3,06/11/2026,19:45,Walsall,Barrow,,2.1,,,\n")

WYNIKI_E0 = ("﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
             "E0,22/08/2026,15:00,Wolves,Man United,2,1,H\n"
             "E0,23/08/2026,15:00,Arsenal,Hull,,,\n").encode("utf-8")


class TestFootballData(Tmp):
    def test_terminarz(self):
        t = dl.fd_terminarz_z_tekstu(FIXTURES, dt.date(2026, 11, 6), dt.date(2026, 11, 7))
        self.assertEqual([(m.liga, m.home, m.away, m.data, m.kursy) for m in t],
                         [("Premier League", "Arsenal", "Hull", dt.datetime(2026, 11, 7, 16, 0),
                           {"1": 1.25, "X": 6.0, "2": 11.0}),
                          ("League Two", "Walsall", "Barrow", dt.datetime(2026, 11, 6, 20, 45), None)])

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


class TestLukiArchiwum(Tmp):
    def test_brakujacy_sezon_uzupelniany_ze_zrodla(self):
        # mini-archiwum: sezony 2020, 2023, 2024 -> brak 2021 i 2022 (od LUKI_OD_SEZONU = 2021)
        with open(os.path.join(self.tmp, "england.csv"), "w", encoding="utf-8") as f:
            f.write("Date,Season,home,visitor,hgoal,vgoal,tier\n"
                    "2020-10-10,2020,Derby County,Bolton Wanderers,1,0,2\n"
                    "2023-10-10,2023,Derby County,Bolton Wanderers,2,0,3\n"
                    "2024-10-10,2024,Bolton Wanderers,Derby County,2,2,3\n")
        sezony = []

        def fd(lista, s_biez, cache_dir, od, do, z_terminarzem=True):
            sezony.extend(lista)
            return pd.DataFrame([{"Date": pd.Timestamp("2022-09-10"), "Season": 2022, "home": "Derby",
                                  "visitor": "Bolton", "hgoal": 3, "vgoal": 1, "tier": 3}]), []

        with mock.patch.object(C, "LUKI_OD_SEZONU", 2021), mock.patch.object(dl, "fd_dane", side_effect=fd):
            d = dl.zbierz(self.tmp, self.cache, "fd", dt.date(2026, 11, 6), dt.date(2026, 11, 6),
                          dt.date(2026, 11, 7))
        self.assertEqual(sezony, [2021, 2022, 2025, 2026])
        self.assertEqual(d.uzupelnione, [2022])
        self.assertTrue(any("2021/22" in o for o in d.ostrzezenia))  # źródło nie zwróciło 2021/22
        r = d.hist[d.hist.Season == 2022].iloc[0]
        self.assertEqual((r.home, r.visitor, r.zrodlo), ("Derby County", "Bolton Wanderers", "football-data.co.uk"))


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
        wyniki = pd.DataFrame([{"Date": pd.Timestamp("2026-09-01"), "Season": 2026, "home": "Sheffield Utd",
                                "visitor": "Wolves", "hgoal": 1, "vgoal": 1, "tier": 2}] +
                              [{"Date": pd.Timestamp(f"{r}-10-01"), "Season": r, "home": "Luton",
                                "visitor": "Sheffield Utd", "hgoal": 3, "vgoal": 0, "tier": 2} for r in range(2015, 2023)])
        term = [dl.Mecz(dt.datetime(2026, 11, 6, 20, 45), "Championship", "Luton", "Sheffield Utd"),
                dl.Mecz(dt.datetime(2026, 11, 7, 16, 0), "Championship", "Wolves", "Sheffield Utd")]
        html = os.path.join(self.tmp, "site", "index.html")
        argv = ["dzis", "--dzis", "2026-11-06", "--zrodlo", "fd", "--dane", self.tmp, "--html", html,
                "--raport", os.path.join(self.tmp, "r.txt"), "--ntfy", "test-temat"]
        typowe = pd.DataFrame(columns=["1", "X", "2", "O", "B"], dtype=float)  # typowe odsetki z config
        with mock.patch.object(dl, "fd_dane", return_value=(wyniki, term)), \
                mock.patch("smaczki.rules.stawki_sezonow", return_value=typowe), \
                mock.patch("smaczki.cli.urllib.request.urlopen") as urlopen:
            self.uruchom(*argv)
            self.uruchom(*argv)  # drugie uruchomienie tego samego dnia – bez drugiego powiadomienia
        with open(html, encoding="utf-8") as f:
            strona = f.read()
        self.assertIn("Dziś · piątek 6 listopada", strona)
        self.assertIn("Jutro · sobota 7 listopada", strona)
        self.assertIn("Luton Town – Sheffield United", strona)
        self.assertIn("Pokaż wyniki", strona)                 # podgląd meczów po kliknięciu
        self.assertIn("01.10.2022<sup>°</sup>", strona)      # wynik spoza archiwum oznaczony
        self.assertNotIn("Wolverhampton Wanderers – Sheffield United", strona)  # mecz bez serii – niepokazywany
        self.assertIn("Skąd dane i czy są kompletne", strona)
        # kalendarz dni u góry, rozwijane zakładki lig, ostateczna predykcja każdego dnia
        self.assertIn('<nav class="kal">', strona)
        self.assertIn('<button type="button" data-d="2026-11-06">', strona)
        self.assertIn('<section class="dzien" data-d="2026-11-07">', strona)
        self.assertIn('<details class="liga"><summary><span>Championship</span>', strona)
        self.assertIn('<div class="liga pusta"><span>Premier League</span><span class="lic">brak meczów</span>', strona)
        self.assertIn('<div class="liga pusta"><span>Championship</span><span class="lic">brak smaczków</span>', strona)
        self.assertIn("Ostateczna predykcja dnia", strona)
        self.assertIn("Wszystkie typy dnia", strona)
        self.assertIn('<details class="seria">', strona)  # typ dnia rozwija listę meczów serii
        self.assertEqual(urlopen.call_count, 1)
        req = urlopen.call_args[0][0]
        self.assertIn("ntfy.sh/test-temat?title=Smaczki", req.full_url)
        self.assertIn("Luton Town – Sheffield United", req.data.decode("utf-8"))


def para(wyniki):
    """Historia pary A–B: lista (rok, gospodarz, gole gosp., gole gościa)."""
    return pd.DataFrame([{"Date": pd.Timestamp(f"{rok}-{'10' if g == 'A' else '03'}-01"), "Season": rok,
                          "home": g, "visitor": "B" if g == "A" else "A", "hgoal": hg, "vgoal": vg, "tier": 1,
                          "zrodlo": "archiwum"} for rok, g, hg, vg in wyniki]) \
        .sort_values("Date").reset_index(drop=True)


class TestSeriePary(unittest.TestCase):
    def setUp(self):
        # sztuczna historia ma same mecze A–B; do kolejności bierzemy typowe odsetki 1X2 z config
        typowe = mock.patch("smaczki.rules.stawki_sezonow",
                            return_value=pd.DataFrame(columns=["1", "X", "2", "O", "B"], dtype=float))
        typowe.start()
        self.addCleanup(typowe.stop)

    def test_wszystkie_serie_obu_druzyn_i_1x2(self):
        from smaczki.rules import smaczki
        w = [(2000, "A", 0, 1)]                                     # ostatnia wygrana B u A: 2000
        w += [(r, "A", 2, 0) for r in range(2001, 2006)]            # potem 5 wygranych A u siebie
        w += [(r, "A", 1, 1) for r in range(2006, 2012)]            # i 6 remisów z rzędu u A
        w += [(r, "B", 0, 3) for r in range(2001, 2006)]            # A wygrywa też u B
        w += [(r, "B", 2, 2) for r in range(2006, 2013)]            # 7 remisów u B
        t = "\n".join(f.tekst for f in smaczki(para(w), "A", "B", pd.Timestamp("2026-11-07")))
        self.assertIn("B nie wygrał u A od 2000 r. (11 meczów) – ostatnio 01.10.2000, 0:1.", t)
        self.assertIn("6 remisów z rzędu w meczach u A z B (od 2006 r.).", t)
        self.assertIn("13 remisów z rzędu w meczach A z B, u siebie i na wyjeździe (od 2006 r.).", t)
        self.assertIn("A nie wygrał u siebie z B od 2005 r. (ostatnio 01.10.2005, 2:0)", t)  # perspektywa gospodarza
        self.assertIn("B nie wygrał z A od 2000 r. (23 mecze, u siebie i na wyjeździe)", t)
        self.assertNotIn("na wyjeździe w", t)  # bez formy z wszystkimi rywalami

    def test_serie_bramkowe(self):
        from smaczki.rules import smaczki
        w = [(2000, "A", 3, 2)] + [(r, "A", 1, 0) for r in range(2001, 2009)] + \
            [(r, "B", 0, 0) for r in range(2001, 2009)]
        f = smaczki(para(w), "A", "B", pd.Timestamp("2026-11-07"))
        t = "\n".join(x.tekst for x in f)
        self.assertIn("Poniżej 2.5 bramki (under) w 8 meczach z rzędu u A z B (od 2001 r.).", t)
        self.assertIn("Poniżej 2.5 bramki (under) w 16 meczach z rzędu między A a B "
                      "(u siebie i na wyjeździe, od 2001 r.).", t)
        self.assertIn("Ten sam wynik 1:0 w 8 meczach z rzędu u A z B (od 2001 r.).", t)
        self.assertIn("Co najmniej jedna drużyna bez gola (BTTS nie) w 16 meczach z rzędu między A a B", t)
        typy = {x.tekst.split(" w ")[0]: x.typ for x in f}
        self.assertEqual(typy["Ten sam wynik 1:0"], "S1:0")
        self.assertEqual(typy["Poniżej 2.5 bramki (under)"], "U2.5")

    def test_serie_bramkowe_dopiero_od_8_meczow(self):
        from smaczki.rules import smaczki
        w = [(2000, "A", 3, 2)] + [(r, "A", 1, 0) for r in range(2001, 2008)]  # 7 meczów z rzędu poniżej 2.5
        t = "\n".join(f.tekst for f in smaczki(para(w), "A", "B", pd.Timestamp("2026-11-07")))
        self.assertNotIn("Poniżej 2.5 bramki", t)
        self.assertNotIn("bez gola (BTTS nie)", t)

    def test_przebieg_serii_obecna_i_wczesniejsze(self):
        from smaczki.rules import przebieg_serii
        # B nie wygrał u A (nieP): 5 meczów (seria), wygrana B, 2 mecze (za krótko), wygrana B, 4 mecze (obecna)
        w = ([(1990 + i, "A", 1, 0) for i in range(5)] + [(1995, "A", 0, 1)] + [(1996, "A", 2, 2), (1997, "A", 1, 0)]
             + [(1998, "A", 0, 2)] + [(1999 + i, "A", 3, 1) for i in range(4)])
        h = para(w)
        et, wcz = przebieg_serii(h, "A", "nieP")
        self.assertEqual(et, ["dawniej"] * 5 + ["", "", "", ""] + ["teraz"] * 4)
        self.assertEqual([(od.year, do.year, n) for od, do, n in wcz], [(1990, 1994, 5)])
        et, _ = przebieg_serii(h, "A", "S", (3, 1))  # ten sam wynik 3:1 – obecna seria 4 mecze
        self.assertEqual(et[-4:], ["teraz"] * 4)

    def test_rozwijana_seria_na_stronie(self):
        from smaczki.report import seria_html
        from smaczki.rules import typ_ostateczny, wyniki_pary
        w = ([(1990 + i, "A", 1, 0) for i in range(5)] + [(1995, "A", 0, 1)] + [(1996 + i, "A", 2, 1) for i in range(5)])
        h = para(w)
        f = Fakt(30, "B nie wygrał u A od 1995 r. (5 meczów)", typ="1X", regula="u:nieP", n=5)
        p = Pozycja(None, "", "A", "B", [f], wyniki=wyniki_pary(h, "A", "B"))
        html = seria_html(p, typ_ostateczny([f]))
        self.assertEqual(html.count('<tr class="teraz">'), 5)
        self.assertEqual(html.count('<tr class="dawniej">'), 5)
        self.assertIn("Wcześniejsze serie: 1990–1994: A wygrał u siebie 5 razy z rzędu; "
                      "1990–1994: ten sam wynik 1:0 5 razy z rzędu.", html)
        self.assertIn('<tr class="g">', html)  # mecz, który przerwał serię (wygrana B) – bez tła

    def test_wczesniejsze_serie_innego_rodzaju_na_niebiesko(self):
        """Niebieskie są wcześniejsze serie między drużynami każdego rodzaju, nie tylko takie jak obecny smaczek."""
        from smaczki.report import seria_html
        from smaczki.rules import typ_ostateczny, wyniki_pary
        w = ([(1990 + i, "A", 1, 1) for i in range(4)] + [(1994, "A", 0, 2)] + [(1995 + i, "A", 3, 0) for i in range(5)])
        h = para(w)
        f = Fakt(30, "A wygrał u siebie z B 5 razy z rzędu", typ="1", regula="u:W", n=5)
        p = Pozycja(None, "", "A", "B", [f], wyniki=wyniki_pary(h, "A", "B"))
        html = seria_html(p, typ_ostateczny([f]))
        self.assertEqual(html.count('<tr class="teraz">'), 5)
        self.assertEqual(html.count('<tr class="x dawniej">'), 4)  # 4 remisy z rzędu 1990–1993 – inny rodzaj serii
        self.assertIn("1990–1993: 4 remisy z rzędu", html)

    def test_smaczek_rozwija_mecze_serii_i_seria_w_wynikach(self):
        from smaczki.report import _karta
        from smaczki.rules import wyniki_pary
        # B nie wygrał z A od 2010 (u siebie i na wyjeździe): seria h2h, bez serii „u gospodarza”
        w = [(2009, "A", 0, 1)] + [(2010 + i, g, 1, 1) for i in range(3) for g in ("A", "B")]
        h = para(w)
        f = Fakt(30, "B nie wygrał z A od 2009 r. (6 meczów, u siebie i na wyjeździe)", typ="1X",
                 regula="h2h:nieP", n=6)
        p = Pozycja(None, "", "A", "B", [f], wyniki=wyniki_pary(h, "A", "B"))
        html = _karta(p)
        self.assertIn('<details class="seria fakt"><summary>B nie wygrał z A od 2009 r.', html)
        self.assertIn('<span class="pokaz">mecze serii</span>', html)
        # po 6 zielonych meczów: pod smaczkiem, pod ostatecznym typem i we „Wszystkich meczach pary” (Pokaż wyniki)
        self.assertEqual(html.count('class="teraz"') + html.count('class="x teraz"'), 18)
        self.assertIn("jest zaznaczona w tabeli „Wszystkie mecze pary” niżej", html)
        self.assertIn("<details open><summary>Wszystkie mecze pary: 7 meczów", html)

    def test_gosc_wygrywa_seria_2(self):
        from smaczki.rules import smaczki
        w = [(1990, "A", 3, 0)] + [(r, "A", 0, 1) for r in range(1991, 1997)] + \
            [(r, "B", 1, 0) for r in range(1991, 1997)]
        t = "\n".join(f.tekst for f in smaczki(para(w), "A", "B", pd.Timestamp("2026-11-07")))
        self.assertIn("B wygrał u A 6 razy z rzędu (od 1991 r.). A nie wygrał u siebie z B od 1990 r. "
                      "(ostatnio 01.10.1990, 3:0).", t)
        self.assertIn("B wygrał z A 12 razy z rzędu, u siebie i na wyjeździe", t)


class TestTypy(unittest.TestCase):
    def test_kursy_i_trafienia(self):
        from smaczki.report import kurs_typu
        from smaczki.skutecznosc import trafiony
        k = {"1": 2.0, "X": 4.0, "2": 4.0, "O2.5": 1.9, "U2.5": 1.95}
        self.assertAlmostEqual(kurs_typu(k, "1"), 2.0)
        # 1/2 + 1/4 + 1/4 = 1.0 (bez marży) -> kurs uczciwy 1 / 0.75
        self.assertAlmostEqual(kurs_typu(k, "1X"), 1 / 0.75)
        self.assertAlmostEqual(kurs_typu(k, "12"), 1 / 0.75)
        m = {"1": 1.1, "X": 9.0, "2": 25.0}   # wyraźny faworyt: kurs nie spada poniżej 1.01
        self.assertGreaterEqual(kurs_typu(m, "1X"), 1.01)
        self.assertEqual(kurs_typu(k, "U2.5"), 1.95)
        self.assertIsNone(kurs_typu(k, "BTTS"))
        self.assertIsNone(kurs_typu(k, "S1:0"))
        self.assertTrue(trafiony(1, 1, "X2") and trafiony(0, 2, "X2") and not trafiony(2, 0, "X2"))
        self.assertTrue(trafiony(3, 1, "12") and not trafiony(1, 1, "12"))
        self.assertTrue(trafiony(2, 1, "O2.5") and not trafiony(2, 0, "O2.5") and trafiony(1, 1, "U2.5"))
        self.assertTrue(trafiony(1, 1, "BTTS") and not trafiony(2, 0, "BTTS") and trafiony(0, 0, "noBTTS"))
        self.assertTrue(trafiony(1, 0, "S1:0") and not trafiony(0, 1, "S1:0"))

    def test_typ_meczu(self):
        from smaczki.report import typ_tekst
        from smaczki.rules import TypWspolny, typy_wspolne
        p = Pozycja(dt.datetime(2026, 11, 6, 21), "Championship", "Derby County", "Bolton", [],
                    kursy={"1": 2.0, "X": 4.0, "2": 4.0, "O2.5": 1.9, "U2.5": 1.95})
        skut = {"okres": "2005/06–2026/27", "wspolne": {
            "1X2:1X": {"typow": 6048, "trafione": 0.728, "przecietnie": 0.70, "kurs": 1.29, "zwrot": -0.084},
            "gole:U2.5": {"typow": 900, "trafione": 0.55, "przecietnie": 0.52, "kurs": 1.8, "zwrot": -0.05},
            "BTTS:BTTS": {"typow": 500, "trafione": 0.51, "przecietnie": 0.49, "kurs": None, "zwrot": None}}}
        self.assertEqual(typ_tekst(TypWspolny("1X2", "1X", ["1X"]), p, skut),
                         "1X2: 1X (gospodarz nie przegra) · kurs ok. 1.33 · "
                         "w przeszłości 73% trafień, zwrot −8% (6\u00a0048 typów od 2005/06)")
        self.assertEqual(typ_tekst(TypWspolny("1X2", "X", ["X", "X2", "1X"]), p, skut),
                         "1X2: X (remis) – część wspólna serii X, X2, 1X · kurs ok. 4.00")
        self.assertEqual(typ_tekst(TypWspolny("1X2", None, ["1", "X2"]), p, skut),
                         "1X2: serie się wykluczają (1, X2) – bez typu")
        self.assertEqual(typ_tekst(TypWspolny("gole", "U2.5", ["U2.5", "U2.5"]), p, skut),
                         "Gole: Under 2.5 (poniżej 2.5 bramki) – zgodny z 2 seriami · kurs ok. 1.95 · "
                         "w przeszłości 55% trafień, zwrot −5% (900 typów od 2005/06)")
        self.assertEqual(typ_tekst(TypWspolny("BTTS", "BTTS", ["BTTS"]), p, skut),
                         "Obie strzelą: BTTS tak (obie drużyny strzelą) · w przeszłości 51% trafień, "
                         "przeciętnie 49%, brak kursów w danych (500 typów od 2005/06)")
        self.assertEqual(typ_tekst(TypWspolny("wynik", "S1:1", ["S1:1"]), p, skut), "Wynik: dokładny wynik 1:1")
        # część wspólna: X ∩ X2 ∩ 1X = X; 1 ∩ 1X = 1; gole i BTTS osobno
        fakty = [Fakt(30, "a", typ="X"), Fakt(20, "b", typ="X2"), Fakt(10, "c", typ="1X"),
                 Fakt(15, "d", typ="U2.5"), Fakt(12, "e", typ="noBTTS"), Fakt(40, "f")]
        self.assertEqual([(t.rynek, t.typ) for t in typy_wspolne(fakty)],
                         [("1X2", "X"), ("gole", "U2.5"), ("BTTS", "noBTTS")])
        self.assertEqual(typy_wspolne([Fakt(1, "", typ="1X"), Fakt(1, "", typ="1")])[0].typ, "1")
        self.assertIsNone(typy_wspolne([Fakt(1, "", typ="O2.5"), Fakt(1, "", typ="U2.5")])[0].typ)

    def test_ostateczny_typ(self):
        from smaczki.report import ostateczny_tekst
        from smaczki.rules import typ_ostateczny
        from smaczki.rules import typy_wspolne as typy_wspolne_
        fakty = [Fakt(37, "6 remisów", typ="X", n=6), Fakt(22, "x2", typ="X2", n=10),
                 Fakt(30, "under 11", typ="U2.5", n=11), Fakt(45, "wynik", typ="S0:0", n=4)]
        t = typ_ostateczny(fakty)  # najdłuższa seria (bez dokładnego wyniku): under w 11 meczach
        self.assertEqual((t.rynek, t.typ, t.najdluzsza), ("gole", "U2.5", 11))
        # Derby – Bolton: część wspólna serii to 1, ale ostateczny typ to typ najdłuższej serii (16 meczów): 1X
        derby = [Fakt(32, "Bolton nie wygrał u Derby od 1981 r. (16 meczów)", typ="1X", regula="u:nieP", n=16),
                 Fakt(24, "Derby wygrał u siebie 6 razy z rzędu", typ="1", regula="u:W", n=6)]
        self.assertEqual(typy_wspolne_(derby)[0].typ, "1")
        t = typ_ostateczny(derby, {"1": 2.61, "X": 3.51, "2": 2.49})
        self.assertEqual((t.typ, t.najdluzsza, t.regula, t.fakt.n), ("1X", 16, "u:nieP", 16))
        rowne = [Fakt(30, "a", typ="1X", n=5), Fakt(20, "b", typ="O2.5", n=5)]
        self.assertEqual(typ_ostateczny(rowne).typ, "1X")  # bez kursów: kolejność rynków
        kursy = {"1": 2.0, "X": 4.0, "2": 4.0, "O2.5": 2.1, "U2.5": 1.75}
        self.assertEqual(typ_ostateczny(rowne, kursy).typ, "O2.5")  # równa długość -> najwyższy kurs (2.1 > 1.33)
        self.assertEqual(typ_ostateczny([Fakt(30, "s", typ="S1:1")]).typ, "S1:1")
        self.assertIsNone(typ_ostateczny([Fakt(0, "Pierwszy mecz")]))
        p = Pozycja(None, "", "A", "B", fakty, kursy={"1": 2.5, "X": 3.2, "2": 3.0, "O2.5": 2.1, "U2.5": 1.75})
        self.assertEqual(ostateczny_tekst(p, None), "OSTATECZNY TYP: Under 2.5 (poniżej 2.5 bramki) · kurs ok. 1.75")

    def test_predykcja_na_koniec(self):
        from smaczki.report import predykcja, predykcja_tekst
        d1, d2 = dt.datetime(2026, 11, 6, 21), dt.datetime(2026, 11, 7, 16)
        a = Pozycja(d1, "Championship", "Derby County", "Bolton",
                    [Fakt(32, "Bolton nie wygrał u Derby", typ="1X", n=16)], kursy={"1": 2.6, "X": 3.5, "2": 2.5})
        b = Pozycja(d2, "Championship", "WBA", "Millwall", [Fakt(37, "6 remisów", typ="X", n=6),
                                                             Fakt(30, "under 11", typ="U2.5", n=11)])
        c = Pozycja(d2, "Premier League", "Everton", "Coventry", [Fakt(0, "Pierwszy mecz w historii")])
        p, t, seria = predykcja([a, b, c])  # najdłuższa seria: 16 meczów
        self.assertEqual((p.h, t.typ, seria.tekst), ("Derby County", "1X", "Bolton nie wygrał u Derby"))
        p, t, seria = predykcja([a, b, c], d2.date())  # tylko mecze z danego dnia
        self.assertEqual((p.h, t.typ, seria.n), ("WBA", "U2.5", 11))
        self.assertIsNone(predykcja([c]))
        # równa długość serii -> wyższy kurs
        e = Pozycja(d2, "Premier League", "E", "F", [Fakt(20, "16 bez remisu", typ="12", n=16)],
                    kursy={"1": 2.0, "X": 3.4, "2": 3.6})
        self.assertEqual(predykcja([a, e])[0].h, "Derby County")  # 1X ok. 1.5 > 12 ok. 1.3
        # wszystkie typy dnia: każdy mecz z serią, od najdłuższej serii
        from smaczki.report import typ_linia, typy_dnia
        lista = [typ_linia(p, t) for p, t in typy_dnia([b, c, a, e])]
        self.assertEqual(lista[0], "21:00 Derby County – Bolton: 1X · kurs 1.51 · seria 16 meczów")
        self.assertEqual(lista[1], "16:00 E – F: 12 · kurs 1.31 · seria 16 meczów")
        self.assertEqual(lista[2], "16:00 WBA – Millwall: Under 2.5 · seria 11 meczów")
        self.assertEqual(len(lista), 3)  # Everton – Coventry bez serii -> bez typu
        nag, typ, why, hist = predykcja_tekst(predykcja([a]), None)
        self.assertEqual(nag, "[Championship] pt 06.11.2026 21:00 Derby County – Bolton")
        self.assertTrue(typ.startswith("1X (gospodarz nie przegra) · kurs ok."))
        self.assertEqual(why, "Najdłuższa seria (16 meczów): Bolton nie wygrał u Derby")

    def test_kazda_seria_ma_typ(self):
        from smaczki.rules import TYP_ZAKLADU, TYPY, TYPY_BRAMEK
        self.assertEqual(set(TYP_ZAKLADU), set(TYPY) | set(TYPY_BRAMEK))


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
