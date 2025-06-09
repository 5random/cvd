import pytest

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
