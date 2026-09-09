from eval.qualitative import _review_rows, _write_markdown


def case(variant, repetition, achieved):
    return {"variant": variant, "repetition": repetition, "scenario": "same",
            "difficulty": "easy", "goal_achieved": achieved, "tool_calls": 1,
            "error": None, "error_categories": [],
            "agent_result": {"steps": [{"tool_name": "look", "tool_input": "{}",
                                         "tool_output": "Sin cambios.", "error": None}]}}


def test_reports_keep_variant_and_repetition_and_group_scores(tmp_path):
    review = _review_rows([case("a", 1, True), case("a", 2, False), case("b", 1, True)])
    assert review["by_variant"]["a"]["average_qualitative_score"] == 1.5
    assert review["by_variant"]["a"]["by_repetition"] == {"1": 3.0, "2": 0.0}
    assert review["by_variant"]["b"]["total"] == 1
    assert [(r["variant"], r["repetition"]) for r in review["reviews"]] == [("a", 1), ("a", 2), ("b", 1)]
    path = tmp_path / "review.md"
    _write_markdown(review, path)
    assert "| a | 2 | same |" in path.read_text(encoding="utf-8")


def test_empty_and_legacy_results_are_supported():
    assert _review_rows([])["by_variant"] == {}
    row = case("a", 1, True)
    del row["variant"], row["repetition"]
    assert _review_rows([row])["reviews"][0]["variant"] == "legacy"
