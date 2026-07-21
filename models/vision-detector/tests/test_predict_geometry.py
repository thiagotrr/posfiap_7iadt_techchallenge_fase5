import numpy as np

import predict as P
from predict import Det


def _white_image(w=200, h=200):
    return np.full((h, w, 3), 255, dtype=np.uint8)


# --------------------------------------------------------------------------
# geometria pura
# --------------------------------------------------------------------------

class TestGeometryHelpers:
    def test_center(self):
        assert P._center((0, 0, 10, 20)) == (5, 10)

    def test_area(self):
        assert P._area((0, 0, 10, 20)) == 200

    def test_area_of_degenerate_box_is_zero(self):
        assert P._area((10, 10, 0, 0)) == 0

    def test_dist(self):
        assert P._dist((0, 0), (3, 4)) == 5.0

    def test_contains_true_for_nested_box(self):
        outer, inner = (0, 0, 100, 100), (10, 10, 50, 50)
        assert P._contains(outer, inner)

    def test_contains_false_for_partial_overlap(self):
        outer, inner = (0, 0, 50, 50), (10, 10, 100, 100)
        assert not P._contains(outer, inner)

    def test_contains_respects_tolerance(self):
        outer, inner = (0, 0, 100, 100), (-2, -2, 100, 100)
        assert P._contains(outer, inner, tol=4)
        assert not P._contains(outer, inner, tol=1)

    def test_box_point_dist_zero_when_point_inside(self):
        assert P._box_point_dist((0, 0, 10, 10), (5, 5)) == 0.0

    def test_box_point_dist_positive_when_point_outside(self):
        assert P._box_point_dist((0, 0, 10, 10), (20, 0)) == 10.0

    def test_nearest_component_picks_closest_by_edge_distance(self):
        components = [
            {"id": "far", "box": (0, 0, 10, 10)},
            {"id": "near", "box": (90, 90, 100, 100)},
        ]
        assert P._nearest_component((95, 95), components)["id"] == "near"

    def test_nearest_component_empty_list_returns_none(self):
        assert P._nearest_component((0, 0), []) is None

    def test_iou_identical_boxes_is_one(self):
        assert P._iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_iou_disjoint_boxes_is_zero(self):
        assert P._iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_iou_partial_overlap(self):
        # (0,0,10,10) e (5,5,15,15): intersecao 5x5=25, uniao 100+100-25=175
        assert P._iou((0, 0, 10, 10), (5, 5, 15, 15)) == 25 / 175


# --------------------------------------------------------------------------
# build_trust_boundaries
# --------------------------------------------------------------------------

class TestBuildTrustBoundaries:
    def test_confidence_propagated_and_notes_flagged_when_tracing_fails(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: None)
        # tesseract-ocr esta instalado na imagem Docker (ver Dockerfile) --
        # forca "OCR nao achou texto" explicitamente em vez de assumir que
        # o ambiente nao tem OCR (numa imagem em branco, o tesseract as
        # vezes alucina ruido tipo "SO" em vez de string vazia).
        monkeypatch.setattr(P, "_ocr_boundary_label", lambda *a, **k: ("boundary", "boundary", False))
        det = Det(cls_name="boundary", box=(10, 10, 190, 190), conf=0.42)

        boundaries = P.build_trust_boundaries([det], _white_image(), exclude_boxes=[])
        tb = next(b for b in boundaries if b["id"] == "tb1")

        assert tb["confidence"] == 0.42
        assert "rastreamento do retângulo falhou" in tb["note"]
        assert "rótulo não lido via OCR" in tb["note"]

    def test_traced_box_ignored_when_it_disagrees_with_raw_box(self, monkeypatch):
        # traced "funciona" (nao e None) mas aponta pra outro lugar (IoU<0.5
        # com a caixa bruta) -- provavelmente pegou a linha de uma boundary
        # VIZINHA por engano. Deve cair pra caixa bruta, nao usar o traced.
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: (500, 500, 600, 600))
        monkeypatch.setattr(P, "_ocr_boundary_label", lambda *a, **k: ("boundary", "boundary", False))
        det = Det(cls_name="boundary", box=(10, 10, 30, 30), conf=0.9)

        boundaries = P.build_trust_boundaries([det], _white_image(), exclude_boxes=[])
        tb = next(b for b in boundaries if b["id"] == "tb1")

        assert tb["box"] == det.box
        assert "rastreamento do retângulo falhou" in tb["note"]

    def test_no_notes_when_tracing_succeeds_and_ocr_finds_text(self, monkeypatch):
        # traced precisa CONCORDAR com a caixa bruta (IoU>=0.5) pra ser
        # aceito como refino -- ver build_trust_boundaries.
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: (10, 10, 190, 190))
        monkeypatch.setattr(P, "_ocr_boundary_label", lambda *a, **k: ("VPC principal", "vpc", True))
        det = Det(cls_name="boundary", box=(10, 10, 180, 180), conf=0.9)

        boundaries = P.build_trust_boundaries([det], _white_image(), exclude_boxes=[])
        tb = next(b for b in boundaries if b["id"] == "tb1")

        assert tb["note"] is None
        assert tb["name"] == "VPC principal"

    def test_nesting_assigns_parent_to_smallest_containing_box(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: None)
        outer = Det(cls_name="boundary", box=(0, 0, 190, 190), conf=0.9)
        inner = Det(cls_name="boundary", box=(20, 20, 100, 100), conf=0.9)

        boundaries = P.build_trust_boundaries([outer, inner], _white_image(), exclude_boxes=[])
        tb_outer = next(b for b in boundaries if b["box"] == outer.box)
        tb_inner = next(b for b in boundaries if b["box"] == inner.box)

        assert tb_inner["parent"] == tb_outer["id"]
        assert tb_outer["parent"] is None

    def test_implicit_external_boundary_always_appended(self):
        boundaries = P.build_trust_boundaries([], _white_image(), exclude_boxes=[])
        assert boundaries[-1] == {
            "id": "external", "box": None, "name": "Externo / Não Detectado",
            "type": "external", "parent": None, "confidence": None, "note": None,
        }

    def test_specific_subtype_detection_sets_type_directly(self, monkeypatch):
        # deteccao ja especifica (nao o "boundary" generico) -- type vem do
        # proprio YOLO, nao do keyword-match do OCR (ver class_to_
        # archetype.py::BOUNDARY_SUBTYPES).
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: None)
        monkeypatch.setattr(P, "_ocr_boundary_label", lambda *a, **k: ("boundary", "boundary", False))
        det = Det(cls_name="vpc", box=(10, 10, 190, 190), conf=0.8)

        boundaries = P.build_trust_boundaries([det], _white_image(), exclude_boxes=[])
        tb = next(b for b in boundaries if b["id"] == "tb1")

        assert tb["type"] == "vpc"

    def test_generic_boundary_detection_falls_back_to_ocr_type(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_boundary_box", lambda *a, **k: None)
        monkeypatch.setattr(P, "_ocr_boundary_label", lambda *a, **k: ("Private Subnet A", "subnet", True))
        det = Det(cls_name="boundary", box=(10, 10, 190, 190), conf=0.8)

        boundaries = P.build_trust_boundaries([det], _white_image(), exclude_boxes=[])
        tb = next(b for b in boundaries if b["id"] == "tb1")

        assert tb["type"] == "subnet"


# --------------------------------------------------------------------------
# build_components
# --------------------------------------------------------------------------

class TestBuildComponents:
    def test_component_gets_innermost_boundary_and_confidence(self, monkeypatch):
        # tesseract-ocr esta instalado na imagem Docker (ver Dockerfile) --
        # forca "OCR nao achou texto" explicitamente (ver comentario em
        # TestBuildTrustBoundaries.test_confidence_propagated...).
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "")
        boundaries = [
            {"id": "outer", "box": (0, 0, 200, 200), "parent": None},
            {"id": "inner", "box": (10, 10, 100, 100), "parent": "outer"},
            {"id": "external", "box": None, "parent": None},
        ]
        det = Det(cls_name="database", box=(20, 20, 40, 40), conf=0.77)

        components = P.build_components([det], boundaries, _white_image())

        assert len(components) == 1
        c = components[0]
        assert c["trust_boundary"] == "inner"
        assert c["confidence"] == 0.77
        assert c["element_type"] == "data_store"  # via ELEMENT_TYPE_OF["database"]
        # sem texto de OCR, cai no placeholder "{Arquétipo em PT-BR} {n}" e sinaliza via note.
        assert c["name"] == "Banco de Dados 1"
        assert c["aws_service"] is None
        assert c["note"] == "rótulo não lido via OCR"

    def test_component_outside_all_boundaries_falls_back_to_external(self):
        boundaries = [
            {"id": "inner", "box": (0, 0, 50, 50), "parent": None},
            {"id": "external", "box": None, "parent": None},
        ]
        det = Det(cls_name="compute", box=(100, 100, 120, 120), conf=0.5)

        components = P.build_components([det], boundaries, _white_image())
        assert components[0]["trust_boundary"] == "external"

    def test_unmapped_archetype_defaults_to_process(self):
        det = Det(cls_name="load_balancer", box=(0, 0, 10, 10), conf=0.6)
        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        assert components[0]["element_type"] == P.DEFAULT_ELEMENT_TYPE == "process"

    def test_fine_grained_service_detection_sets_aws_service_and_rolls_up_category(self, monkeypatch):
        # "RDS" e um servico especifico promovido (ver class_to_archetype.py
        # ::FINE_GRAINED_SERVICES), nao um arquetipo -- aws_service vem
        # DIRETO da deteccao (mais confiavel que OCR), category rola pro
        # arquetipo ("database") pra continuar batendo com ELEMENT_TYPE_OF/
        # STRIDE, que so conhecem arquetipo.
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "")
        det = Det(cls_name="RDS", box=(0, 0, 40, 40), conf=0.9)

        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        c = components[0]
        assert c["aws_service"] == "RDS"
        assert c["category"] == "database"
        assert c["element_type"] == "data_store"  # via ELEMENT_TYPE_OF["database"]

    def test_fine_grained_detection_takes_priority_over_ocr_match(self, monkeypatch):
        # deteccao diz "EC2", OCR le um texto que bateria com outro servico
        # (ex. rotulo errado/vizinho) -- a deteccao especifica vence.
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "Amazon Lambda")
        det = Det(cls_name="EC2", box=(0, 0, 40, 40), conf=0.9)

        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        assert components[0]["aws_service"] == "EC2"
        assert components[0]["category"] == "compute"

    def test_ocr_label_matched_to_known_service_sets_aws_service_and_name(self, monkeypatch):
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "Amazon RDS")
        det = Det(cls_name="database", box=(0, 0, 40, 40), conf=0.9)

        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        c = components[0]
        assert c["name"] == "Amazon RDS"
        assert c["aws_service"] == "RDS"
        assert c["note"] is None

    def test_ocr_label_with_no_service_match_falls_back_to_raw_text(self, monkeypatch):
        # nao bate com AWS_SERVICE_NAMES, mas o OCR leu algo plausivel --
        # aws_service cai pro texto bruto (best-effort) em vez de None,
        # sinalizado via note que nao foi validado contra a lista curada.
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "totally unrecognizable text")
        det = Det(cls_name="compute", box=(0, 0, 40, 40), conf=0.9)

        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        c = components[0]
        assert c["name"] == "totally unrecognizable text"
        assert c["aws_service"] == "totally unrecognizable text"
        assert "texto bruto do OCR" in c["note"]

    def test_ocr_label_too_short_stays_none(self, monkeypatch):
        # _ocr_component_label ja devolve texto LIMPO na producao (ver
        # _clean_ocr_text) -- simula esse contrato aqui (nao um texto cru
        # com ruido, que e testado direto em TestCleanOcrText).
        monkeypatch.setattr(P, "_ocr_component_label", lambda *a, **k: "ab")
        det = Det(cls_name="compute", box=(0, 0, 40, 40), conf=0.9)

        components = P.build_components(
            [det], [{"id": "external", "box": None, "parent": None}], _white_image()
        )
        assert components[0]["aws_service"] is None


class TestCleanOcrText:
    def test_empty_text_returns_empty(self):
        assert P._clean_ocr_text("") == ""
        assert P._clean_ocr_text(None) == ""

    def test_drops_stray_single_letters_and_punctuation_only_tokens(self):
        # exemplo real: ver 1_architecture.json, c_database_1
        text = "S Amazon ElastiCache ,\n) (memcached) ee\nMulti-AZ 1 1"
        assert P._clean_ocr_text(text) == "Amazon ElastiCache (memcached) Multi-AZ 1 1"

    def test_drops_repeated_single_letter_tokens(self):
        # exemplo real: ver 1_architecture.json, c_database_2
        text = "I I Amazon RDS Amazoa\nI I\n(Secondary) ue\nI l"
        assert P._clean_ocr_text(text) == "Amazon RDS Amazoa (Secondary)"

    def test_preserves_parenthetical_qualifiers(self):
        # "(Secondary)"/"(memcached)" sao qualificador de verdade (estilo do
        # diagrama de referencia: "RDS (Standby Multi-AZ)"), nao ruido --
        # nao pode ser removido pela limpeza.
        assert P._clean_ocr_text("RDS (Secondary)") == "RDS (Secondary)"

    def test_clean_label_still_matches_service_after_cleaning(self):
        text = "S Amazon ElastiCache ,\n) (memcached) ee\nMulti-AZ 1 1"
        cleaned = P._clean_ocr_text(text)
        assert P._match_aws_service(cleaned) == "ElastiCache"


class TestMatchAwsService:
    def test_no_text_returns_none(self):
        assert P._match_aws_service("") is None
        assert P._match_aws_service(None) is None

    def test_exact_match(self):
        assert P._match_aws_service("Lambda") == "Lambda"

    def test_strips_amazon_aws_prefix(self):
        assert P._match_aws_service("Amazon RDS") == "RDS"
        assert P._match_aws_service("AWS Lambda") == "Lambda"

    def test_fuzzy_typo_still_matches(self):
        assert P._match_aws_service("DynamoBD") == "Dynamo DB"

    def test_unrelated_text_returns_none(self):
        assert P._match_aws_service("qwzxjk 12345") is None

    def test_extra_words_around_service_name_still_match(self):
        # rotulos reais tem palavras extras em volta do nome do servico --
        # ver predict.py: falso-positivo historico foi "EBS" "achando"
        # dentro de "webSite" com substring livre; window-match exige
        # igualdade exata de uma janela de palavra, nao substring solto.
        assert P._match_aws_service("DynamoDB Tables") == "Dynamo DB"
        assert P._match_aws_service("SNS Notifications") == "SNS"
        assert P._match_aws_service("S3 Static Website") == "S3"
        assert P._match_aws_service("CloudFront Distribution") == "Cloudfront"


# --------------------------------------------------------------------------
# build_data_flows
# --------------------------------------------------------------------------

class TestBuildDataFlows:
    def _components(self):
        return [
            {"id": "src", "box": (0, 0, 20, 20), "trust_boundary": "tb1"},
            {"id": "dst", "box": (150, 150, 170, 170), "trust_boundary": "tb2"},
        ]

    def test_matches_source_and_destination_by_endpoint_distance(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_far_endpoint", lambda *a, **k: (10, 10))
        arrowhead = Det(cls_name="arrowhead", box=(155, 155, 165, 165), conf=0.65)

        flows = P.build_data_flows([arrowhead], self._components(), boundary_boxes=[], image=_white_image())

        assert len(flows) == 1
        flow = flows[0]
        assert flow["source"] == "src"
        assert flow["destination"] == "dst"
        assert flow["crosses_boundary"] is True
        assert flow["confidence"] == 0.65

    def test_protocol_falls_back_to_unknown_with_note_when_ocr_finds_nothing(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_far_endpoint", lambda *a, **k: (10, 10))
        # tesseract-ocr esta instalado na imagem Docker (ver Dockerfile) --
        # forca "OCR nao achou texto" explicitamente (ver comentario em
        # TestBuildTrustBoundaries.test_confidence_propagated...).
        monkeypatch.setattr(P, "_ocr_flow_protocol", lambda *a, **k: None)
        arrowhead = Det(cls_name="arrowhead", box=(155, 155, 165, 165), conf=0.65)

        flows = P.build_data_flows([arrowhead], self._components(), boundary_boxes=[], image=_white_image())

        assert flows[0]["protocol"] == "desconhecido"
        assert flows[0]["note"] == "protocolo não lido via OCR"

    def test_skips_when_source_and_destination_are_the_same_component(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_far_endpoint", lambda *a, **k: (5, 5))
        arrowhead = Det(cls_name="arrowhead", box=(1, 1, 5, 5), conf=0.9)

        flows = P.build_data_flows([arrowhead], self._components(), boundary_boxes=[], image=_white_image())
        assert flows == []

    def test_skips_when_far_endpoint_not_found(self, monkeypatch):
        monkeypatch.setattr(P, "_trace_far_endpoint", lambda *a, **k: None)
        arrowhead = Det(cls_name="arrowhead", box=(155, 155, 165, 165), conf=0.9)

        flows = P.build_data_flows([arrowhead], self._components(), boundary_boxes=[], image=_white_image())
        assert flows == []

    def test_no_arrowheads_or_no_components_returns_empty(self):
        assert P.build_data_flows([], self._components(), [], _white_image()) == []
        assert P.build_data_flows([Det("arrowhead", (0, 0, 1, 1), 0.9)], [], [], _white_image()) == []
