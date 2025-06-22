from scripts import generate_uml


def test_collect_and_generate(tmp_path, monkeypatch):
    sample = tmp_path / "sample.py"
    sample.write_text(
        """
class Foo:
    pass

class Bar(Foo):
    def baz(self):
        pass
"""
    )

    monkeypatch.setattr(generate_uml, "SRC_DIR", tmp_path)

    classes = generate_uml.collect_classes()
    assert set(classes) == {"Bar", "Foo"}
    assert classes["Bar"]["bases"] == ["Foo"]
    methods = [m["name"] for m in classes["Bar"]["methods"]]
    assert "baz" in methods

    diagram = generate_uml.generate_mermaid(classes)
    assert "class Foo" in diagram
    assert "class Bar" in diagram
    assert "Foo <|-- Bar" in diagram
