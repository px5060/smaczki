"""Kryteria akceptacji briefu 2 (kolejne ligi: Hiszpania, Włochy, Niemcy, Francja, Holandia) – na archiwum
engsoccerdata (dane do sezonu 2024/25), bez uzupełnienia. Zasady dla danych będących tylko wycinkiem historii
i dla sezonu brakującego w archiwum – także na danych sztucznych.

Wymaga plików dane/<kraj>.csv (python -m smaczki pobierz); bez nich testy na archiwum są pomijane.
"""
import contextlib
import datetime as dt
from dataclasses import replace
import io
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from smaczki import config as C
from smaczki import data_loader as dl
from smaczki.names import Nazwy, bez_znakow, wczytaj_aliasy
from smaczki.rules import ANGLIA, Zakres, karta_meczu, ranking, smaczki, zakres_kraju

DANE = os.path.join(os.path.dirname(__file__), "..", "dane")
KRAJE = [k for k in C.KRAJE if k != "england"]
JEST = all(os.path.exists(os.path.join(DANE, f"{k}.csv")) for k in KRAJE)

# Nazwy z football-data.co.uk z sezonów 2025/26 i 2026/27
NAZWY_FD = {
    "spain": "Alaves|Ath Bilbao|Ath Madrid|Barcelona|Betis|Celta|Elche|Espanol|Getafe|Girona|La Coruna|Levante|Malaga|"
             "Mallorca|Osasuna|Oviedo|Real Madrid|Santander|Sevilla|Sociedad|Valencia|Vallecano|Villarreal",
    "italy": "Atalanta|Bologna|Cagliari|Como|Cremonese|Fiorentina|Frosinone|Genoa|Inter|Juventus|Lazio|Lecce|Milan|"
             "Monza|Napoli|Parma|Pisa|Roma|Sassuolo|Torino|Udinese|Venezia|Verona",
    "germany": "Augsburg|Bayern Munich|Bielefeld|Bochum|Braunschweig|Cottbus|Darmstadt|Dortmund|Dresden|Ein Frankfurt|"
               "Elversberg|FC Koln|Fortuna Dusseldorf|Freiburg|Greuther Furth|Hamburg|Hannover|Heidenheim|Hertha|"
               "Hoffenheim|Holstein Kiel|Kaiserslautern|Karlsruhe|Leverkusen|M'gladbach|Magdeburg|Mainz|Nurnberg|"
               "Osnabruck|Paderborn|Preußen Münster|RB Leipzig|Schalke 04|St Pauli|Stuttgart|Union Berlin|"
               "Werder Bremen|Wolfsburg",
    "france": "Angers|Auxerre|Brest|Le Havre|Le Mans|Lens|Lille|Lorient|Lyon|Marseille|Metz|Monaco|Nantes|Nice|"
              "Paris FC|Paris SG|Rennes|Strasbourg|Toulouse|Troyes",
    "holland": "AZ Alkmaar|Ajax|Cambuur|Den Haag|Excelsior|Feyenoord|For Sittard|Go Ahead Eagles|Groningen|Heerenveen|"
               "Heracles|NAC Breda|Nijmegen|PSV Eindhoven|Sparta Rotterdam|Telstar|Twente|Utrecht|Volendam|"
               "Willem II|Zwolle",
}
TYPOWE = pd.DataFrame(columns=["1", "X", "2", "O", "B"], dtype=float)  # typowe odsetki wyników z config


def teksty(fakty):
    return "\n".join(f.tekst for f in fakty)


@unittest.skipUnless(JEST, "brak dane/spain.csv albo dane/italy.csv – uruchom: python -m smaczki pobierz")
class TestArchiwaLig(unittest.TestCase):
    hist = {}

    @classmethod
    def archiwum(cls, kraj):
        if kraj not in cls.hist:
            poziomy = tuple(sorted({t for _, t, _ in C.KRAJE[kraj].ligi.values()}))
            hist = dl.wczytaj_archiwum(DANE, kraj, poziomy)
            cls.hist[kraj] = (hist, zakres_kraju(kraj, poziomy, hist))
        return cls.hist[kraj]

    def smaczki(self, kraj, h, v):
        hist, z = self.archiwum(kraj)
        return teksty(smaczki(hist, h, v, zakres=z))

    # --- pełna historia 1. ligi: „nigdy” dozwolone, z dopiskiem „w 1. lidze” ---
    def test_hiszpania_granada_u_valencii(self):
        self.assertIn("Granada CF NIGDY nie wygrał w 1. lidze u Valencia CF (27 meczów od 1942 r.)",
                      self.smaczki("spain", "Valencia CF", "Granada CF"))

    def test_wlochy_cremonese_u_lazio(self):
        self.assertIn("US Cremonese NIGDY nie wygrał w 1. lidze u Lazio Roma (8 meczów od 1929 r.)",
                      self.smaczki("italy", "Lazio Roma", "US Cremonese"))

    def test_niemcy_braunschweig_u_kolna(self):
        # 24 mecze razem z 2. Bundesligą (w samej Bundeslidze 20)
        self.assertIn("Eintracht Braunschweig NIGDY nie wygrał w 1. i 2. Bundeslidze u 1. FC Koln (24 mecze od 1964 r.)",
                      self.smaczki("germany", "1. FC Koln", "Eintracht Braunschweig"))

    def test_francja_le_havre_u_marsylii(self):
        self.assertIn("Le Havre AC nie wygrał w 1. lidze u Olympique Marseille od 1938 r. (20 meczów) – "
                      "ostatnio 11.12.1938, 0:2.", self.smaczki("france", "Olympique Marseille", "Le Havre AC"))

    def test_holandia_go_ahead_u_ajaxu(self):
        # Eredivisie od 1956/57 to cała historia tej ligi -> „nigdy” z dopiskiem „w Eredivisie”
        self.assertIn("Go Ahead Eagles NIGDY nie wygrał w Eredivisie u AFC Ajax (35 meczów od 1964 r.)",
                      self.smaczki("holland", "AFC Ajax", "Go Ahead Eagles"))

    def test_francja_brakujacy_sezon_1937(self):
        hist, z = self.archiwum("france")
        self.assertEqual(z.brak, (1937,))
        self.assertIn("RC Lens", z.przy_luce)  # grał w 1936/37 albo 1938/39 – mógł grać w 1937/38
        self.assertNotIn("Paris Saint-Germain", z.przy_luce)
        k = "\n".join(karta_meczu(hist, "RC Lens", "FC Metz", zakres=z))
        self.assertIn("Zakres danych: mecze w 1. lidze, w danych brak sezonu 1937/38.", k)

    def test_karta_i_ranking_z_zakresem(self):
        hist, z = self.archiwum("spain")
        k = "\n".join(karta_meczu(hist, "Valencia CF", "Granada CF", zakres=z))
        self.assertIn("Zakres danych: mecze w 1. lidze.", k)
        self.assertIn("Granada CF NIGDY nie wygrał w 1. lidze u Valencia CF", k)
        r = "\n".join(ranking(hist, 500, zakres=z, lat_wstecz=30))
        self.assertIn("Granada CF NIGDY nie wygrał w 1. lidze u Valencia CF (27 meczów od 1942 r.)", r)

    def test_pierwszy_mecz_w_1_lidze(self):
        hist, z = self.archiwum("italy")
        self.assertEqual(teksty(smaczki(hist, "Juventus", "Nowy Klub", zakres=z)),
                         "Pierwszy mecz tych drużyn w 1. lidze w historii.")

    # --- nazwy ---
    def test_zmiany_nazw_w_archiwum_ujednolicone(self):
        hist, _ = self.archiwum("italy")
        self.assertNotIn("Parma AC", set(hist.home))
        self.assertEqual(hist[hist.home == "Parma FC"].Season.min(), 1990)
        hist, _ = self.archiwum("holland")
        self.assertNotIn("Feijenoord", set(hist.home))
        self.assertEqual(hist[hist.home == "Feyenoord"].Season.min(), 1956)
        self.assertNotIn("Heracles", set(hist.home))
        hist, _ = self.archiwum("germany")
        self.assertNotIn("TSV 1860 Munchen", set(hist.home))
        hist, _ = self.archiwum("france")
        self.assertEqual(sorted(hist[hist.home == "Gazelec Ajaccio"].Season.unique()), [2015])  # nie AC Ajaccio

    def test_aliasy_wskazuja_kluby_z_archiwum(self):
        for kraj in KRAJE:
            hist, _ = self.archiwum(kraj)
            druzyny = set(hist.home) | set(hist.visitor)
            a = wczytaj_aliasy(kraj)
            with self.subTest(kraj=kraj):
                self.assertEqual(sorted(set(a.get("aliasy", {}).values()) - druzyny), [])
                self.assertEqual(sorted(set(a.get("nowe_kluby", [])) & druzyny), [])

    def test_nazwy_football_data(self):
        for kraj, lista in NAZWY_FD.items():
            hist, _ = self.archiwum(kraj)
            n = Nazwy(hist, kraj)
            nazwy = lista.split("|")
            mapa = {x: n(x) for x in nazwy}
            with self.subTest(kraj=kraj):
                self.assertEqual(n.niedopasowane, set())
                self.assertTrue(all(m in n.ostatni_mecz for m in mapa.values()))
                self.assertEqual(len(set(mapa.values())), len(nazwy))  # różne nazwy -> różne kluby
        sprawdz = {("spain", "Ath Madrid"): "Atletico Madrid", ("spain", "Espanol"): "Espanyol Barcelona",
                   ("spain", "Real Madrid"): "Real Madrid", ("spain", "Sociedad"): "Real Sociedad",
                   ("spain", "Malaga"): "Malaga CF", ("italy", "Lazio"): "Lazio Roma", ("italy", "Roma"): "AS Roma",
                   ("italy", "Verona"): "Hellas Verona", ("italy", "Milan"): "AC Milan", ("italy", "Parma"): "Parma FC",
                   ("germany", "RB Leipzig"): "RasenBallsport Leipzig", ("germany", "FC Koln"): "1. FC Koln",
                   ("germany", "Preußen Münster"): "Preussen Munster", ("germany", "M'gladbach"): "Bor. Monchengladbach",
                   ("france", "Paris SG"): "Paris Saint-Germain", ("france", "Paris FC"): "Paris FC",
                   ("france", "St Etienne"): "AS Saint-Etienne", ("holland", "Den Haag"): "ADO Den Haag",
                   ("holland", "Zwolle"): "PEC Zwolle", ("holland", "Feyenoord"): "Feyenoord"}
        for (kraj, zrodlo), oczekiwane in sprawdz.items():
            hist, _ = self.archiwum(kraj)
            self.assertEqual(Nazwy(hist, kraj)(zrodlo), oczekiwane, (kraj, zrodlo))

    def test_nazwy_z_diakrytykami(self):
        hist, _ = self.archiwum("spain")
        n = Nazwy(hist, "spain")
        self.assertEqual([n(x) for x in ("Atlético Madrid", "Cádiz", "Leganés", "Deportivo Alavés", "Almería")],
                         ["Atletico Madrid", "Cadiz CF", "CD Leganes", "CD Alaves", "UD Almeria"])
        self.assertEqual(n.niedopasowane, set())
        hist, _ = self.archiwum("germany")
        n = Nazwy(hist, "germany")
        self.assertEqual([n(x) for x in ("1. FC Köln", "Bayern München", "Borussia Mönchengladbach")],
                         ["1. FC Koln", "Bayern Munchen", "Bor. Monchengladbach"])

    def test_raport_niedopasowanych_z_kandydatami(self):
        hist, _ = self.archiwum("spain")
        n = Nazwy(hist, "spain")
        self.assertEqual(n("Nieznany Klub CF"), "Nieznany Klub CF")
        self.assertIn("Nieznany Klub CF", n.niedopasowane)
        self.assertIn("Real Zaragoza", Nazwy(hist, "spain").kandydaci("Real Saragossa"))

    def test_luki_archiwum(self):
        for kraj in KRAJE:  # Francja 1994/95 – uzupełniane z football-data.co.uk
            self.assertEqual(dl.luki_archiwum(self.archiwum(kraj)[0]), [1994] if kraj == "france" else [], kraj)


def para(wyniki):
    """Historia pary A–B: lista (rok, gospodarz, gole gosp., gole gościa)."""
    return pd.DataFrame([{"Date": pd.Timestamp(f"{rok}-{'10' if g == 'A' else '03'}-01"), "Season": rok,
                          "home": g, "visitor": "B" if g == "A" else "A", "hgoal": hg, "vgoal": vg, "tier": 1,
                          "zrodlo": "archiwum"} for rok, g, hg, vg in wyniki]).sort_values("Date").reset_index(drop=True)


class TestBezArchiwum(unittest.TestCase):
    def test_bez_znakow(self):
        self.assertEqual(bez_znakow("1. FC Köln"), "1. FC Koln")
        self.assertEqual(bez_znakow("Málaga · Atlético · Göztepe · Beşiktaş · Preußen"),
                         "Malaga · Atletico · Goztepe · Besiktas · Preussen")

    def test_zakres_kraju(self):
        self.assertEqual(zakres_kraju("england").w, "")
        self.assertTrue(zakres_kraju("england").pelna)
        z = zakres_kraju("spain")
        self.assertEqual((z.w, z.pelna, z.dane_od(1), z.opis), ("w 1. lidze", True, 1928, "w 1. lidze"))
        self.assertEqual(zakres_kraju("italy").dane_od(), 1929)

    def test_wycinek_historii_bez_nigdy_i_z_nizsza_waga(self):
        """Gdyby dane były tylko wycinkiem historii (np. od 1994): bez „nigdy”, z „dane od X”, waga × 0,5."""
        hist = para([(r, "A", 2, 0) for r in range(1994, 2010)])
        wycinek = Zakres("w 1. lidze", False, ((1, 1994),))
        with mock.patch("smaczki.rules.stawki_sezonow", return_value=TYPOWE):
            pelna = smaczki(hist, "A", "B", zakres=ANGLIA)
            f = smaczki(hist, "A", "B", zakres=wycinek)
        t = teksty(f)
        self.assertNotIn("nigdy", t.lower())
        self.assertIn("B nie wygrał w 1. lidze u A w żadnym z 16 meczów od 1994 r. (dane od 1994).", t)
        self.assertIn("A wygrał u siebie z B 16 razy z rzędu w 1. lidze – wszystkie mecze od 1994 r. (dane od 1994).", t)
        self.assertAlmostEqual(f[0].waga, pelna[0].waga * C.WAGA_WYCINKA, places=6)
        self.assertIn("NIGDY nie wygrał ligowo u A", teksty(pelna))

    def test_seria_przez_brakujacy_sezon(self):
        """Seria obejmująca sezon brakujący w archiwum (np. Francja 1937/38): bez „nigdy”, z zastrzeżeniem."""
        hist = para([(r, "A", 2, 0) for r in list(range(1934, 1937)) + list(range(1938, 1945))])
        z = Zakres("w 1. lidze", True, ((1, 1932),), brak=(1937,), przy_luce=frozenset({"A", "B"}))
        with mock.patch("smaczki.rules.stawki_sezonow", return_value=TYPOWE):
            pelna = smaczki(hist, "A", "B", zakres=Zakres("w 1. lidze", True, ((1, 1932),)))
            t = teksty(smaczki(hist, "A", "B", zakres=z))
            inna = teksty(smaczki(hist, "A", "B", zakres=replace(z, przy_luce=frozenset({"A"}))))
        self.assertNotIn("nigdy", t.lower())
        self.assertIn("B nie wygrał w 1. lidze u A w żadnym z 10 meczów od 1934 r. (w danych brak sezonu 1937/38).", t)
        self.assertIn("NIGDY nie wygrał w 1. lidze u A", teksty(pelna))
        self.assertIn("NIGDY nie wygrał w 1. lidze u A", inna)  # B nie grał w lidze obok brakującego sezonu

    def test_wybor_lig(self):
        with tempfile.TemporaryDirectory() as tmp:
            plik = os.path.join(tmp, "ligi.json")
            with open(plik, "w", encoding="utf-8") as f:
                f.write('{"_opis": "x", "spain": [1], "england": [1, 2, 3, 4], "italy": []}')
            w = dl.wlaczone_ligi(plik)
            self.assertEqual(list(w.items()), [("england", (1, 2, 3, 4)), ("spain", (1,))])  # kolejność z config
            self.assertEqual(dl.wybierz_ligi(w, "spain"), ({"spain": (1,)}, None))
            self.assertEqual(dl.wybierz_ligi(w, "E0,I1"), ({"england": (1, 2, 3, 4), "italy": (1,)}, {"E0", "I1"}))
            with self.assertRaises(dl.BladDanych):
                dl.wybierz_ligi(w, "polska")
            with open(plik, "w", encoding="utf-8") as f:
                f.write('{"spain": [2]}')
            with self.assertRaises(dl.BladDanych):
                dl.wlaczone_ligi(plik)
            self.assertEqual(dl.wlaczone_ligi(os.path.join(tmp, "brak.json")), {"england": (1, 2, 3, 4)})

    def test_terminarz_innej_ligi(self):
        tekst = ("Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA\n"
                 "E0,07/11/2026,15:00,Arsenal,Hull,1.25,6.0,11.0\n"
                 "SP1,07/11/2026,20:00,Real Madrid,Getafe,1.1,8,20\n"
                 "I1,07/11/2026,19:45,Inter,Lecce,1.2,7,15\n")
        t = dl.fd_terminarz_z_tekstu(tekst, dt.date(2026, 11, 7), dt.date(2026, 11, 7), dl.ligi_kraju("spain"))
        self.assertEqual([(m.liga, m.home, m.away, m.data) for m in t],
                         [("La Liga", "Real Madrid", "Getafe", dt.datetime(2026, 11, 7, 21, 0))])

    def test_bez_duplikatow_na_styku(self):
        """Ten sam mecz z archiwum i ze źródła bieżącego = jeden mecz; sezon z archiwum zostaje z archiwum."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "spain.csv"), "w", encoding="utf-8") as f:
                f.write("Date,Season,home,visitor,hgoal,vgoal,tier\n"
                        "2024-08-10,2024,Real Madrid,FC Barcelona,1,0,1\n"
                        "2025-05-25,2024,FC Barcelona,Real Madrid,2,2,1\n")
            wyniki = pd.DataFrame([
                # ostatnia kolejka 2024/25 także w źródle bieżącym (np. inny zapis sezonu) – nie może się zdublować
                {"Date": pd.Timestamp("2025-05-25"), "Season": 2024, "home": "Barcelona", "visitor": "Real Madrid",
                 "hgoal": 2, "vgoal": 2, "tier": 1},
                {"Date": pd.Timestamp("2025-05-25"), "Season": 2025, "home": "Barcelona", "visitor": "Real Madrid",
                 "hgoal": 2, "vgoal": 2, "tier": 1},
                {"Date": pd.Timestamp("2025-08-16"), "Season": 2025, "home": "Real Madrid", "visitor": "Barcelona",
                 "hgoal": 3, "vgoal": 1, "tier": 1}])
            with mock.patch.object(dl, "fd_dane", return_value=(wyniki, [])):
                d = dl.zbierz(tmp, os.path.join(tmp, "cache"), "fd", dt.date(2026, 11, 6), dt.date(2026, 11, 6),
                              dt.date(2026, 11, 7), kraj="spain", poziomy=(1,))
        self.assertEqual(int(d.hist.duplicated(["Date", "home", "visitor"]).sum()), 0)
        self.assertEqual(len(d.hist), 3)
        self.assertEqual(d.hist.zrodlo.tolist(), ["archiwum", "archiwum", "football-data.co.uk"])
        st = d.ligi[0]
        self.assertEqual((st.kod, st.dopisane, st.koniec), ("SP1", 1, pd.Timestamp("2025-08-16")))
        self.assertIn("2026/27", st.ostrzezenie)  # brak wyników bieżącego sezonu -> luka niezamknięta

    def test_kolejka_z_pliku_kilka_krajow(self):
        """Plik meczów z kolumną liga (kod ligi z config); raport grupowany po kraju i lidze."""
        from smaczki.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "england.csv"), "w", encoding="utf-8") as f:
                f.write("Date,Season,home,visitor,hgoal,vgoal,tier\n2024-10-10,2024,Arsenal,Fulham,2,0,1\n")
            with open(os.path.join(tmp, "spain.csv"), "w", encoding="utf-8") as f:
                f.write("Date,Season,home,visitor,hgoal,vgoal,tier\n" + "".join(
                    f"{r}-10-10,{r},Valencia CF,Granada CF,2,0,1\n" for r in range(2015, 2021)))
            with open(os.path.join(tmp, "ligi.json"), "w", encoding="utf-8") as f:
                f.write('{"england": [1, 2, 3, 4], "spain": [1]}')
            with open(os.path.join(tmp, "mecze.csv"), "w", encoding="utf-8") as f:
                f.write("home,away,date,liga\nValencia,Granada,2026-11-07 21:00,SP1\nArsenal,Fulham,2026-11-07,E0\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), \
                    mock.patch.object(C, "LUKI_OD_SEZONU", 2024), \
                    mock.patch("smaczki.rules.stawki_sezonow", return_value=TYPOWE):
                main(["kolejka", "--zrodlo", "brak", "--dane", tmp, "--plik-lig", os.path.join(tmp, "ligi.json"),
                      "--plik-meczow", os.path.join(tmp, "mecze.csv"), "--raport", os.path.join(tmp, "r.txt"),
                      "--wszystkie", "--html", os.path.join(tmp, "s.html")])
            tekst = out.getvalue()
            with open(os.path.join(tmp, "s.html"), encoding="utf-8") as f:
                strona = f.read()
        self.assertIn("== Anglia ==", tekst)
        self.assertIn("== Hiszpania ==", tekst)
        self.assertIn("· La Liga ·", tekst)
        self.assertIn("Valencia CF wygrał u siebie z Granada CF 6 razy z rzędu w 1. lidze – wszystkie mecze od 2015 r.",
                      tekst)
        self.assertIn("Hiszpania – La Liga: historia do 10.10.2020", tekst)  # stan danych per liga
        self.assertLess(tekst.index("== Anglia =="), tekst.index("== Hiszpania =="))
        # strona: kafelki krajów z gwiazdką i liczbą smaczków, w środku ligi
        self.assertIn('<button type="button" class="kafel" data-k="spain"', strona)
        self.assertIn('<span class="ile">★ 1</span>', strona)
        self.assertIn('<div class="kraj" data-k="spain" hidden>', strona)
        self.assertIn('<details class="liga" open><summary><span>La Liga</span>', strona)


if __name__ == "__main__":
    unittest.main()
