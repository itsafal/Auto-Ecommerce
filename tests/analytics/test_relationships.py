from backend.analytics.relationships import build_relationships


def _business(id_, category, supplier_id, margin):
    return {
        "id": id_,
        "category": category,
        "supplier_id": supplier_id,
        "margin_estimate": margin,
    }


def test_relationships_connect_businesses_with_same_supplier():
    businesses = [
        _business("a", "phone_accessories", "supp_4821", 0.60),
        _business("b", "computer_peripherals", "supp_4821", 0.30),
    ]
    edges = build_relationships(businesses)
    pairs = {(e.from_business_id, e.to_business_id, e.relationship_type) for e in edges}
    assert ("a", "b", "shared_supplier") in pairs
    assert ("b", "a", "shared_supplier") in pairs


def test_relationships_connect_shared_category():
    businesses = [
        _business("a", "phone_accessories", "supp_1", 0.60),
        _business("b", "phone_accessories", "supp_2", 0.30),
    ]
    edges = build_relationships(businesses)
    types = {(e.from_business_id, e.to_business_id, e.relationship_type) for e in edges}
    assert ("a", "b", "shared_category") in types
    assert ("b", "a", "shared_category") in types
    assert not any(e.relationship_type == "shared_supplier" for e in edges)


def test_relationships_emit_similar_margin_only_within_tolerance():
    close = [
        _business("a", "x", "supp_1", 0.60),
        _business("b", "y", "supp_2", 0.65),  # diff 0.05, within 0.10
    ]
    far = [
        _business("a", "x", "supp_1", 0.60),
        _business("b", "y", "supp_2", 0.85),  # diff 0.25, outside 0.10
    ]
    assert any(e.relationship_type == "similar_margin" for e in build_relationships(close))
    assert not any(e.relationship_type == "similar_margin" for e in build_relationships(far))


def test_no_self_edges_and_no_empty_id_edges():
    businesses = [
        _business("a", "x", "supp_1", 0.60),
        {"id": "", "category": "x", "supplier_id": "supp_1", "margin_estimate": 0.60},
    ]
    edges = build_relationships(businesses)
    for edge in edges:
        assert edge.from_business_id != edge.to_business_id
        assert edge.from_business_id and edge.to_business_id
