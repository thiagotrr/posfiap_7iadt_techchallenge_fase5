from extraction.eval import _multiset_f1, compare_diagrams
from extraction.schemas import ArchitectureDiagram

from collections import Counter


def _diagram(components, data_flows=(), trust_boundaries=()):
    return ArchitectureDiagram.model_validate({
        "diagram_metadata": {"cloud_provider": "aws", "extraction_confidence": "média"},
        "trust_boundaries": [
            {"id": "tb1", "name": "tb1", "type": "vpc"}, *trust_boundaries,
        ],
        "components": components,
        "data_flows": data_flows,
    })


def _component(id_, element_type="process", category=None, confidence=None, note=None):
    return {
        "id": id_, "name": id_, "element_type": element_type, "category": category,
        "trust_boundary": "tb1", "confidence": confidence, "note": note,
    }


class TestMultisetF1:
    def test_identical_counters_score_one(self):
        c = Counter(a=2, b=1)
        assert _multiset_f1(c, c) == 1.0

    def test_disjoint_counters_score_zero(self):
        assert _multiset_f1(Counter(a=2), Counter(b=2)) == 0.0

    def test_both_empty_scores_one(self):
        assert _multiset_f1(Counter(), Counter()) == 1.0

    def test_partial_overlap(self):
        # predicted: 3 "a"; expected: 2 "a" + 1 "b" -> overlap = 2
        # precision = 2/3, recall = 2/3 -> f1 = 2/3
        predicted, expected = Counter(a=3), Counter(a=2, b=1)
        assert abs(_multiset_f1(predicted, expected) - 2 / 3) < 1e-9


class TestCompareDiagrams:
    def test_identical_diagrams_score_perfectly(self):
        diagram = _diagram([_component("c1", category="database")])
        metrics = compare_diagrams(diagram, diagram)

        assert metrics["component_count"] == {"predicted": 1, "expected": 1}
        assert metrics["element_type_distribution_f1"] == 1.0
        assert metrics["category_distribution_f1"] == 1.0
        assert metrics["components_flagged_for_review"] == 0
        assert metrics["components_low_confidence"] == 0

    def test_missing_component_lowers_counts_and_f1(self):
        expected = _diagram([
            _component("c1", element_type="data_store", category="database"),
            _component("c2", element_type="process", category="compute"),
        ])
        predicted = _diagram([_component("c1", element_type="data_store", category="database")])

        metrics = compare_diagrams(predicted, expected)

        assert metrics["component_count"] == {"predicted": 1, "expected": 2}
        assert 0.0 < metrics["element_type_distribution_f1"] < 1.0

    def test_low_confidence_and_notes_are_counted(self):
        predicted = _diagram([
            _component("c1", confidence=0.2, note="rótulo não lido via OCR"),
            _component("c2", confidence=0.9),
        ])
        metrics = compare_diagrams(predicted, predicted)

        assert metrics["components_low_confidence"] == 1
        assert metrics["components_flagged_for_review"] == 1
