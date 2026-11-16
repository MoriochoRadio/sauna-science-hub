"""collect.py 회귀 테스트 — 네트워크 없이 돈다.  실행: python -m unittest discover -s tests"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import collect as c  # noqa: E402


class RelevanceTest(unittest.TestCase):
    def keep(self, title, abstract="", keywords=(), mesh=()):
        return c.relevance(title, abstract, keywords, mesh)[0]

    def test_sauna_in_title_is_kept(self):
        self.assertTrue(self.keep("Effects of Sauna Bathing on NMR-Based Metabolomic Profiles."))
        self.assertTrue(self.keep("Effect of Cardiac Rehabilitation Combined with Waon Therapy"))

    def test_acronym_sauna_model_and_trial_are_dropped(self):
        # HFpEF 생쥐 'SAUNA 모델' · 신경내분비종양 'SAUNA trial' 은 사우나가 아니다
        self.assertFalse(self.keep("Assessing left atrial function in murine HFpEF.",
                                   "HFpEF was induced using the SAUNA model. Obese-SAUNA HFpEF mice ..."))
        self.assertFalse(self.keep("Somatostatin analogue continuation (SAUNA trial): a protocol.",
                                   "The SAUNA trial is an international, multicentre, randomised trial."))

    def test_sauna_hfpef_trial_is_real_sauna(self):
        self.assertTrue(self.keep('Response to: "Feasibility ... pilot findings in SAUNA-HFpEF".'))

    def test_venue_mentions_are_dropped(self):
        self.assertFalse(self.keep(
            "Factors associated with one-night stands among men who have sex with men",
            "Meeting partners in offline venues (such as bars and saunas) was associated with ..."))
        self.assertFalse(self.keep(
            "Outreach mpox vaccination at sex-on-premises venues",
            'Two sex-on-premises venues, also known as "saunas". Sauna attendees ...'))

    def test_weight_cut_surveys_dropped_unless_sauna_is_the_subject(self):
        self.assertFalse(self.keep(
            "Rapid weight loss practices among judo athletes.",
            "Methods included fluid restriction and sauna. Sauna use was common."))
        self.assertTrue(self.keep(
            "Reliability of a portable infrared sauna protocol for rapid weight loss.", "..."))

    def test_single_incidental_mention_is_dropped(self):
        self.assertFalse(self.keep(
            "Wireless microsensors for sweat electrolyte monitoring.",
            "Tested across temperatures including outdoor exercise and dry saunas."))
        self.assertFalse(self.keep(
            "Heat thresholds for maternal health: a meta-analysis.",
            "We included ambient heat exposure; heat from medical devices, saunas or pools was excluded."))

    def test_single_mention_with_heat_therapy_context_is_kept(self):
        self.assertTrue(self.keep(
            "Feasibility of home-based leg heat therapy in older adults.",
            "Heat therapy using sauna or hot water immersion can improve health."))

    def test_repeated_abstract_mentions_are_kept(self):
        self.assertTrue(self.keep(
            "Optimizing chronic pain treatment.",
            "Interventions include sauna therapy and cryotherapy. Sauna reduced pain."))

    def test_keyword_or_mesh_is_kept(self):
        self.assertTrue(self.keep("Passive heat interventions in women.", "", keywords=["sauna"]))
        self.assertTrue(self.keep("Hydration testing in combat athletes.", "", mesh=["Steam Bath"]))

    def test_no_sauna_word_is_dropped(self):
        self.assertFalse(self.keep("Unrelated paper.", "Nothing about it."))


def _http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("https://x", code, "err", headers, io.BytesIO(b""))


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class RetryTest(unittest.TestCase):
    def setUp(self):
        self.sleep = mock.patch.object(c.time, "sleep").start()
        self.urlopen = mock.patch.object(c.urllib.request, "urlopen").start()
        self.addCleanup(mock.patch.stopall)
        self._err = redirect_stderr(io.StringIO())
        self._err.__enter__()
        self.addCleanup(self._err.__exit__, None, None, None)

    def backoff_sleeps(self):
        # 스로틀(≈0.34초) 대기는 빼고 백오프 대기만 본다
        return [call.args[0] for call in self.sleep.call_args_list if call.args[0] >= 1]

    def test_5xx_then_success(self):
        self.urlopen.side_effect = [_http_error(500), _http_error(503), _Resp(b"ok")]
        self.assertEqual(c.http_get("https://x"), "ok")
        self.assertEqual(self.urlopen.call_count, 3)
        self.assertEqual(self.backoff_sleeps(), [2.0, 4.0])

    def test_429_honours_retry_after_with_cap(self):
        self.urlopen.side_effect = [_http_error(429, "5"), _http_error(429, "999"), _Resp(b"ok")]
        self.assertEqual(c.http_get("https://x"), "ok")
        self.assertEqual(self.backoff_sleeps(), [5.0, float(c.RETRY_AFTER_CAP)])

    def test_timeout_and_connection_errors_are_retried(self):
        self.urlopen.side_effect = [TimeoutError("timed out"), urllib.error.URLError("reset"), _Resp(b"ok")]
        self.assertEqual(c.http_get("https://x"), "ok")

    def test_4xx_is_not_retried(self):
        self.urlopen.side_effect = [_http_error(400)]
        with self.assertRaises(urllib.error.HTTPError):
            c.http_get("https://x")
        self.assertEqual(self.urlopen.call_count, 1)

    def test_gives_up_after_max_tries(self):
        self.urlopen.side_effect = [_http_error(502)] * 10
        with self.assertRaises(urllib.error.HTTPError):
            c.http_get("https://x")
        self.assertEqual(self.urlopen.call_count, c.MAX_TRIES)

    def test_requests_are_spaced_for_ncbi_rate_limit(self):
        clock = iter([0.0, 0.0, 0.1, 0.34])   # monotonic(): 1차 대기 계산·기록, 2차 대기 계산·기록
        with mock.patch.object(c.time, "monotonic", side_effect=lambda: next(clock)):
            c._last_request[0] = -10.0
            self.urlopen.side_effect = [_Resp(b"a"), _Resp(b"b")]
            c.http_get("https://x")
            c.http_get("https://x")
        waits = [call.args[0] for call in self.sleep.call_args_list]
        self.assertEqual(len(waits), 1)
        self.assertAlmostEqual(waits[0], c.EUTILS_MIN_INTERVAL - 0.1)

    def test_esearch_error_body_is_a_failure_not_empty(self):
        with mock.patch.object(c, "fetch_json", return_value={"esearchresult": {"ERROR": "backend down"}}):
            with self.assertRaises(RuntimeError):
                c.search_pmids()


class KeepOnEmptyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = os.path.join(self.tmp.name, "research.json")
        for name, val in (("OUT", self.out), ("CACHE", os.path.join(self.tmp.name, "tr.json"))):
            p = mock.patch.object(c, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(c, "translate_articles").start()

    def write_existing(self, days_ago):
        data = {"updated": str(date.today() - timedelta(days=days_ago)), "count": 1,
                "articles": [{"pmid": "1", "title": "Sauna", "abstract": ""}]}
        with open(self.out, "w", encoding="utf-8") as f:
            json.dump(data, f)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def run_main(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = c.main()
        return code, out.getvalue()

    def read(self):
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_zero_results_keep_existing_file(self):
        before = self.write_existing(days_ago=1)
        mock.patch.object(c, "search_pmids", return_value=[]).start()
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.read(), before)
        self.assertIn("::warning", out)

    def test_all_filtered_out_keeps_existing_file(self):
        before = self.write_existing(days_ago=0)
        mock.patch.object(c, "search_pmids", return_value=["1", "2"]).start()
        mock.patch.object(c, "fetch_details", return_value=[]).start()
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.read(), before)

    def test_fetch_failure_keeps_existing_file(self):
        before = self.write_existing(days_ago=1)
        mock.patch.object(c, "search_pmids", side_effect=_http_error(500)).start()
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.read(), before)
        self.assertIn("HTTPError", out)

    def test_persistent_failure_fails_the_run(self):
        before = self.write_existing(days_ago=c.STALE_DAYS)
        mock.patch.object(c, "search_pmids", side_effect=_http_error(503)).start()
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("::error", out)
        self.assertEqual(self.read(), before)

    def test_no_existing_data_fails_without_writing(self):
        mock.patch.object(c, "search_pmids", return_value=[]).start()
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.out))

    def test_success_overwrites(self):
        self.write_existing(days_ago=5)
        art = {"pmid": "9", "title": "Sauna", "abstract": "", "year": "2026", "is_clinical": False}
        mock.patch.object(c, "search_pmids", return_value=["9"]).start()
        mock.patch.object(c, "fetch_details", return_value=[art]).start()
        code, _ = self.run_main()
        self.assertEqual(code, 0)
        data = json.loads(self.read())
        self.assertEqual(data["updated"], str(date.today()))
        self.assertEqual([a["pmid"] for a in data["articles"]], ["9"])


class FetchDetailsTest(unittest.TestCase):
    XML = """<PubmedArticleSet>
      <PubmedArticle><MedlineCitation><PMID>2</PMID><Article>
        <ArticleTitle>Sauna bathing and blood pressure</ArticleTitle></Article></MedlineCitation></PubmedArticle>
      <PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
        <ArticleTitle>Biosensor fibres</ArticleTitle>
        <Abstract><AbstractText>Tested during exercise and sauna conditions.</AbstractText></Abstract>
      </Article></MedlineCitation></PubmedArticle>
      <PubmedArticle><MedlineCitation><PMID>3</PMID><Article>
        <ArticleTitle>Far-infrared sauna and core temperature</ArticleTitle></Article></MedlineCitation></PubmedArticle>
    </PubmedArticleSet>"""

    def test_filters_and_keeps_search_order(self):
        with mock.patch.object(c, "fetch_xml", return_value=self.XML), redirect_stderr(io.StringIO()):
            out = c.fetch_details(["3", "1", "2"])
        self.assertEqual([a["pmid"] for a in out], ["3", "2"])


if __name__ == "__main__":
    unittest.main()
