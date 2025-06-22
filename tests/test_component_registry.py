
from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
    ComponentRegistry,
)


class DummyComponent(BaseComponent):
    def render(self):
        return None

    def _update_element(self, data):
        pass


def test_unregister_removes_from_registry():
    registry = ComponentRegistry()
    comp = DummyComponent(ComponentConfig(component_id="comp1"))
    registry.register(comp)

    assert comp in registry.get_all_components()

    removed = registry.unregister("comp1")
    assert removed
    assert comp not in registry.get_all_components()


def test_register_same_instance_no_extra_log(monkeypatch):
    registry = ComponentRegistry()
    comp = DummyComponent(ComponentConfig(component_id="comp1"))
    logs: list[str] = []

    monkeypatch.setattr(
        "src.gui.gui_tab_components.gui_tab_base_component.info",
        lambda msg, **k: logs.append(msg),
    )

    registry.register(comp)
    registry.register(comp)

    assert logs == ["Registered component: comp1"]


def test_register_new_instance_logs_replacement(monkeypatch):
    registry = ComponentRegistry()
    comp1 = DummyComponent(ComponentConfig(component_id="comp1"))
    comp2 = DummyComponent(ComponentConfig(component_id="comp1"))
    logs: list[str] = []

    monkeypatch.setattr(
        "src.gui.gui_tab_components.gui_tab_base_component.info",
        lambda msg, **k: logs.append(msg),
    )

    registry.register(comp1)
    registry.register(comp2)

    assert logs == ["Registered component: comp1", "Replaced component: comp1"]
    assert registry.get_component("comp1") is comp2


def test_cleanup_all_handles_missing_cleanup():
    registry = ComponentRegistry()

    class MissingCleanup:
        def __init__(self, cid: str = "missing"):
            self.component_id = cid

    registry.register(MissingCleanup())  # type: ignore[arg-type]

    registry.cleanup_all()  # should not raise
    assert registry.get_all_components() == []


def test_cleanup_all_handles_noncallable_cleanup_attribute(monkeypatch):
    registry = ComponentRegistry()

    class NonCallableCleanup:
        component_id = "bad"
        cleanup = True

    registry.register(NonCallableCleanup())  # type: ignore[arg-type]

    registry.cleanup_all()  # should not raise
    assert registry.get_all_components() == []
