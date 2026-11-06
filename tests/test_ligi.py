"""Kryteria akceptacji briefu 2 (kolejne ligi) – na archiwum engsoccerdata (dane do sezonu 2024/25), bez uzupełnienia.

Wymaga plików dane/<kraj>.csv (python -m smaczki pobierz); bez nich testy na archiwum są pomijane.
"""
import datetime as dt
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from smaczki import config as C
from smaczki import data_loader as dl
from smaczki.names import Nazwy, bez_znakow, wczytaj_aliasy
from smaczki.rules import ANGLIA, karta_meczu, ranking, smaczki, zakres_kraju

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
    "portugal": "AVS|Academico Viseu|Alverca|Arouca|Benfica|Casa Pia|Estoril|Estrela|Famalicao|Gil Vicente|Guimaraes|"
                "Maritimo|Moreirense|Nacional|Porto|Rio Ave|Santa Clara|Sp Braga|Sp Lisbon|Tondela",
    "scotland": "Aberdeen|Airdrie Utd|Alloa|Annan Athletic|Arbroath|Ayr|Celtic|Clyde|Cove Rangers|Dumbarton|Dundee|"
                "Dundee United|Dunfermline|East Fife|East Kilbride|Edinburgh City|Elgin|Falkirk|Forfar|Hamilton|Hearts|"
                "Hibernian|Inverness C|Kelty Hearts|Kilmarnock|Livingston|Montrose|Morton|Motherwell|Partick|"
                "Peterhead|Queen of Sth|Queens Park|Raith Rvs|Rangers|Ross County|Spartans|St Johnstone|St Mirren|"
                "Stenhousemuir|Stirling|Stranraer",
    "belgium": "Anderlecht|Antwerp|Beveren|Cercle Brugge|Charleroi|Club Brugge|Dender|Genk|Gent|Kortrijk|Lommel SK|"
               "Mechelen|Oud-Heverlee Leuven|RAAL La Louviere|St Truiden|St. Gilloise|Standard|Waregem|Westerlo",
    "turkey": "Alanyaspor|Amedspor|Antalyaspor|Besiktas|Buyuksehyr|Corum|Erzurumspor|Eyupspor|Fenerbahce|Galatasaray|"
              "Gaziantep|Genclerbirligi|Goztep|Karagumruk|Kasimpasa|Kayserispor|Kocaelispor|Konyaspor|Rizespor|"
              "Samsunspor|Trabzonspor",
    "greece": "AEK|Aris|Asteras Tripolis|Atromitos|Iraklis|Kalamata|Kifisia|Larisa|Levadeiakos|OFI Crete|Olympiakos|PAOK|"
              "Panathinaikos|Panetolikos|Panserraikos|Volos NFC",
}


def teksty(fakty):
    return "\n".join(f.tekst for f in fakty)


@unittest.skipUnless(JEST, "brak dane/<kraj>.csv – uruchom: python -m smaczki pobierz")
class TestArchiwaLig(unittest.TestCase):
    hist = {}

    @classmethod
    def archiwum(cls, kraj):
        if kraj not in cls.hist:
            poziomy = tuple(sorted({t for _, t, _ in C.KRAJE[kraj].ligi.values()}))
            cls.hist[kraj] = (dl.wczytaj_archiwum(DANE, kraj, poziomy), zakres_kraju(kraj, poziomy))
        return cls.hist[kraj]

    def smaczki(self, kraj, h, v):
        hist, z = self.archiwum(kraj)
        return teksty(smaczki(hist, h, v, zakres=z))

    # --- pełna historia: „nigdy” dozwolone ---
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
        t = self.smaczki("france", "Olympique Marseille", "Le Havre AC")
        self.assertIn("Le Havre AC nie wygrał w 1. lidze u Olympique Marseille od 1938 r. (20 meczów) – "
                      "ostatnio 11.12.1938, 0:2.", t)

    # --- wycinek historii: bez „nigdy”, z zastrzeżeniem „dane od X”, niższa waga ---
    def test_holandia_go_ahead_u_ajaxu(self):
        t = self.smaczki("holland", "AFC Ajax", "Go Ahead Eagles")
        self.assertIn("Go Ahead Eagles nie wygrał w 1. lidze u AFC Ajax w żadnym z 35 meczów od 1964 r. (dane od 1956).", t)
        self.assertNotIn("NIGDY", t)

    def test_szkocja_dundee_united_u_celticu(self):
        t = self.smaczki("scotland", "Celtic", "Dundee United")
        self.assertNotIn("nigdy", t.lower())
        self.assertIn("Dundee United nie wygrał u Celtic w żadnym z 45 meczów ligowych od 1994 r. (dane od 1994).", t)

    def test_portugalia_boavista_u_sportingu(self):
        hist, z = self.archiwum("portugal")
        self.assertEqual(Nazwy(hist, "portugal")("Sp Lisbon"), "Sp Lisbon")
        t = self.smaczki("portugal", "Sp Lisbon", "Boavista")
        self.assertNotIn("nigdy", t.lower())
        self.assertIn("Boavista nie wygrał w 1. lidze u Sp Lisbon w żadnym z 25 meczów od 1994 r. (dane od 1994).", t)

    def test_waga_wycinka_obnizona(self):
        hist, z = self.archiwum("scotland")
        pelna = {f.tekst.split(" (")[0][:40]: f.waga for f in smaczki(hist, "Celtic", "Dundee United", zakres=ANGLIA)}
        wycinek = smaczki(hist, "Celtic", "Dundee United", zakres=z)
        f = next(f for f in wycinek if "w żadnym z 45" in f.tekst)
        g = next(w for t, w in pelna.items() if t.startswith("Dundee United NIGDY nie wygrał ligowo u"))
        self.assertAlmostEqual(f.waga, g * C.WAGA_WYCINKA, places=6)

    def test_karta_i_ranking_z_zakresem(self):
        hist, z = self.archiwum("scotland")
        k = "\n".join(karta_meczu(hist, "Celtic", "Dundee United", zakres=z))
        self.assertIn("tylko od 1994 (wcześniejszej historii nie ma w danych)", k)
        self.assertNotIn("NIGDY", k)
        r = "\n".join(ranking(hist, 50, 1, zakres=z))
        self.assertIn("Dundee United nie wygrał u Celtic w żadnym z 45 meczów od 1994 r. (dane od 1994)", r)

    def test_pierwszy_mecz_w_danych(self):
        hist, z = self.archiwum("portugal")
        self.assertEqual(teksty(smaczki(hist, "Benfica", "Nowy Klub", zakres=z)),
                         "Pierwszy mecz tych drużyn w 1. lidze w danych (dane od 1994).")

    # --- nazwy ---
    def test_zmiany_nazw_w_archiwum_ujednolicone(self):
        hist, _ = self.archiwum("holland")
        druzyny = set(hist.home)
        self.assertNotIn("Feijenoord", druzyny)
        self.assertEqual(hist[hist.home == "Feyenoord"].Season.min(), 1956)
        self.assertNotIn("Heracles", druzyny)
        hist, _ = self.archiwum("germany")
        self.assertNotIn("TSV 1860 Munchen", set(hist.home))
        hist, _ = self.archiwum("italy")
        self.assertNotIn("Parma AC", set(hist.home))
        hist, _ = self.archiwum("turkey")
        self.assertEqual(sorted(hist[hist.home == "Erzurum"].Season.unique()), [2018, 2020])  # 1998 to inny klub

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
                znane = [x for x in nazwy if x not in n.nowe]
                self.assertTrue(all(mapa[x] in n.ostatni_mecz for x in znane))
                self.assertEqual(len({mapa[x] for x in znane}), len(znane))  # różne nazwy -> różne kluby
        sprawdz = {("spain", "Ath Madrid"): "Atletico Madrid", ("spain", "Espanol"): "Espanyol Barcelona",
                   ("france", "Paris SG"): "Paris Saint-Germain", ("france", "Paris FC"): "Paris FC",
                   ("germany", "RB Leipzig"): "RasenBallsport Leipzig", ("germany", "Preußen Münster"): "Preussen Munster",
                   ("germany", "FC Koln"): "1. FC Koln", ("belgium", "Beveren"): "Waasland-Beveren",
                   ("belgium", "Lommel SK"): "Lommel SK", ("turkey", "Erzurumspor"): "Erzurum",
                   ("scotland", "Rangers"): "Rangers", ("greece", "OFI Crete"): "OFI"}
        for (kraj, zrodlo), oczekiwane in sprawdz.items():
            hist, _ = self.archiwum(kraj)
            self.assertEqual(Nazwy(hist, kraj)(zrodlo), oczekiwane, (kraj, zrodlo))

    def test_nazwy_z_diakrytykami(self):
        hist, _ = self.archiwum("germany")
        n = Nazwy(hist, "germany")
        self.assertEqual(n("1. FC Köln"), "1. FC Koln")
        self.assertEqual(n("Bayern München"), "Bayern Munchen")
        self.assertEqual(n("Borussia Mönchengladbach"), "Bor. Monchengladbach")
        hist, _ = self.archiwum("turkey")
        n = Nazwy(hist, "turkey")
        self.assertEqual((n("Beşiktaş"), n("Fenerbahçe")), ("Besiktas", "Fenerbahce"))
        hist, _ = self.archiwum("spain")
        self.assertEqual(Nazwy(hist, "spain")("Atlético Madrid"), "Atletico Madrid")

    def test_raport_niedopasowanych_z_kandydatami(self):
        hist, _ = self.archiwum("scotland")
        n = Nazwy(hist, "scotland")
        self.assertEqual(n("Nieznany Klub FC"), "Nieznany Klub FC")
        self.assertIn("Nieznany Klub FC", n.niedopasowane)
        self.assertIn("Dundee United", Nazwy(hist, "scotland").kandydaci("Dundee Utd"))

    def test_luki_i_poczatek_danych(self):
        hist, _ = self.archiwum("france")
        self.assertEqual(dl.luki_archiwum(hist), [1994])  # 1994/95 – uzupełniane z football-data.co.uk
        for kraj in ("portugal", "scotland", "belgium", "turkey", "greece"):  # przed początkiem danych to nie luka
            self.assertEqual(dl.luki_archiwum(self.archiwum(kraj)[0]), [], kraj)


class TestBezArchiwum(unittest.TestCase):
    def test_bez_znakow(self):
        self.assertEqual(bez_znakow("1. FC Köln"), "1. FC Koln")
        self.assertEqual(bez_znakow("Málaga · Çaykur Rizespor · Göztepe · Beşiktaş · Preußen"),
                         "Malaga · Caykur Rizespor · Goztepe · Besiktas · Preussen")

    def test_zakres_kraju(self):
        self.assertEqual(zakres_kraju("england", (1, 2, 3, 4)), ANGLIA.__class__("", True, ((1, 1888), (2, 1888),
                                                                                           (3, 1888), (4, 1888))))
        self.assertEqual(zakres_kraju("england").w, "")
        self.assertEqual(zakres_kraju("germany", (1, 2)).w, "w 1. i 2. Bundeslidze")
        self.assertEqual(zakres_kraju("germany", (1,)).w, "w Bundeslidze")
        z = zakres_kraju("scotland", (1, 2, 3, 4))
        self.assertEqual((z.w, z.pelna, z.dane_od(1), z.dane_od(3), z.opis), ("", False, 1994, 1997, "dane od 1994"))
        self.assertEqual(zakres_kraju("spain").opis, "w 1. lidze")

    def test_wybor_lig(self):
        with tempfile.TemporaryDirectory() as tmp:
            plik = os.path.join(tmp, "ligi.json")
            with open(plik, "w", encoding="utf-8") as f:
                f.write('{"_opis": "x", "spain": [1], "england": [1, 2, 3, 4], "italy": []}')
            w = dl.wlaczone_ligi(plik)
            self.assertEqual(list(w.items()), [("england", (1, 2, 3, 4)), ("spain", (1,))])  # kolejność z config
            self.assertEqual(dl.wybierz_ligi(w, "spain"), ({"spain": (1,)}, None))
            self.assertEqual(dl.wybierz_ligi(w, "E0,D2"), ({"england": (1, 2, 3, 4), "germany": (2,)}, {"E0", "D2"}))
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
                 "SP1,07/11/2026,20:00,Real Madrid,Getafe,1.1,8,20\n")
        t = dl.fd_terminarz_z_tekstu(tekst, dt.date(2026, 11, 7), dt.date(2026, 11, 7), dl.ligi_kraju("spain"))
        self.assertEqual([(m.liga, m.home, m.away, m.data) for m in t],
                         [("La Liga", "Real Madrid", "Getafe", dt.datetime(2026, 11, 7, 21, 0))])

    def test_bez_duplikatow_na_styku(self):
        """Turcja kończy 2024/25 1.06.2025: ten sam mecz z obu źródeł = jeden mecz, sezon z archiwum zostaje."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "turkey.csv"), "w", encoding="utf-8") as f:
                f.write("Date,Season,home,visitor,hgoal,vgoal,tier\n"
                        "2024-08-10,2024,Galatasaray,Fenerbahce,1,0,1\n"
                        "2025-06-01,2024,Fenerbahce,Galatasaray,2,2,1\n")
            wyniki = pd.DataFrame([
                # ostatnia kolejka 2024/25 także w źródle bieżącym (np. inny zapis sezonu) – nie może się zdublować
                {"Date": pd.Timestamp("2025-06-01"), "Season": 2024, "home": "Fenerbahce", "visitor": "Galatasaray",
                 "hgoal": 2, "vgoal": 2, "tier": 1},
                {"Date": pd.Timestamp("2025-06-01"), "Season": 2025, "home": "Fenerbahce", "visitor": "Galatasaray",
                 "hgoal": 2, "vgoal": 2, "tier": 1},
                {"Date": pd.Timestamp("2025-08-09"), "Season": 2025, "home": "Galatasaray", "visitor": "Fenerbahce",
                 "hgoal": 3, "vgoal": 1, "tier": 1}])
            with mock.patch.object(dl, "fd_dane", return_value=(wyniki, [])):
                d = dl.zbierz(tmp, os.path.join(tmp, "cache"), "fd", dt.date(2026, 11, 6), dt.date(2026, 11, 6),
                              dt.date(2026, 11, 7), kraj="turkey", poziomy=(1,))
        self.assertEqual(int(d.hist.duplicated(["Date", "home", "visitor"]).sum()), 0)
        self.assertEqual(len(d.hist), 3)
        self.assertEqual(d.hist.zrodlo.tolist(), ["archiwum", "archiwum", "football-data.co.uk"])
        st = d.ligi[0]
        self.assertEqual((st.kod, st.dopisane, st.koniec), ("T1", 1, pd.Timestamp("2025-08-09")))
        self.assertIn("2026/27", st.ostrzezenie)  # brak wyników bieżącego sezonu -> luka niezamknięta

    def test_kolejka_z_pliku_kilka_krajow(self):
        """Plik meczów z kolumną liga (kod ligi z config); raport grupowany po kraju i lidze."""
        import contextlib
        import io
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
            typowe = pd.DataFrame(columns=["1", "X", "2", "O", "B"], dtype=float)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), \
                    mock.patch.object(C, "LUKI_OD_SEZONU", 2024), \
                    mock.patch("smaczki.rules.stawki_sezonow", return_value=typowe):
                main(["kolejka", "--zrodlo", "brak", "--dane", tmp, "--plik-lig", os.path.join(tmp, "ligi.json"),
                      "--plik-meczow", os.path.join(tmp, "mecze.csv"), "--raport", os.path.join(tmp, "r.txt"),
                      "--wszystkie"])
            tekst = out.getvalue()
        self.assertIn("== Anglia ==", tekst)
        self.assertIn("== Hiszpania ==", tekst)
        self.assertIn("· La Liga ·", tekst)
        self.assertIn("Valencia CF wygrał u siebie z Granada CF 6 razy z rzędu w 1. lidze – wszystkie mecze od 2015 r.",
                      tekst)
        self.assertIn("Hiszpania – La Liga: historia do 10.10.2020", tekst)  # stan danych per liga
        self.assertLess(tekst.index("== Anglia =="), tekst.index("== Hiszpania =="))


if __name__ == "__main__":
    unittest.main()
