"""The 11-sample-question mini-eval itself: pinned as a regression test so a
future retrieval/threshold change that regresses accuracy is caught, not
just observed manually."""
from src.module_b.eval.harness import run_eval


def test_all_eleven_sample_questions_score_correct(stw_conn):
    report = run_eval(stw_conn)
    wrong = [r for r in report["rows"] if r["verdict"] != "correct"]
    assert wrong == [], f"{report['n_correct']}/{report['n_total']} correct; failures: {wrong}"
