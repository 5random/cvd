"""
Base component system for modular UI components.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field
from nicegui import ui
from src.utils.log_utils.log_service import info, warning, error, debug

@dataclass
class ComponentConfig:
    """Configuration for a UI component"""
    component_id: str
    title: Optional[str] = None
    classes: str = ""
    styles: Dict[str, str] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)

class BaseComponent(ABC):
    """Base class for all UI components"""
    
    def __init__(self, config: ComponentConfig):
        self.config = config
        self._element: Optional[Any] = None
        self._rendered = False
        self._children: List['BaseComponent'] = []
    
    @property
    def component_id(self) -> str:
        """Get component ID"""
        return self.config.component_id
    
    @property
    def is_rendered(self) -> bool:
        """Check if component has been rendered"""
        return self._rendered
    
    @abstractmethod
    def render(self) -> Any:
        """Render the component and return NiceGUI element"""
        pass
    
    def update(self, data: Any) -> None:
        """Update component with new data"""
        if self._rendered and self._element:
            self._update_element(data)
    
    @abstractmethod
    def _update_element(self, data: Any) -> None:
        """Implementation-specific update logic"""
        pass
    
    def get_element(self) -> Any:
        """Get the rendered element, rendering if necessary"""
        if not self._rendered:
            self._element = self.render()
            self._rendered = True
        return self._element
    
    def add_child(self, child: 'BaseComponent') -> None:
        """Add a child component"""
        self._children.append(child)
    
    def remove_child(self, child: 'BaseComponent') -> None:
        """Remove a child component"""
        if child in self._children:
            self._children.remove(child)
    
    def get_children(self) -> List['BaseComponent']:
        """Get all child components"""
        return self._children.copy()
    
    def cleanup(self) -> None:
        """Cleanup component resources"""
        for child in self._children:
            child.cleanup()
        self._children.clear()
        self._element = None
        self._rendered = False

class ComponentRegistry:
    """Registry for managing UI components"""
    
    def __init__(self):
        self._components: Dict[str, BaseComponent] = {}
    
    def register(self, component: BaseComponent) -> None:
        """Register a component"""
        self._components[component.component_id] = component
        info(f"Registered component: {component.component_id}")
    
    def unregister(self, component_id: str) -> bool:
        """Unregister a component"""
        if component_id in self._components:
            component = self._components[component_id]
            component.cleanup()
            info(f"Unregistered component: {component_id}")
            return True
        return False
    
    def get_component(self, component_id: str) -> Optional[BaseComponent]:
        """Get component by ID"""
        return self._components.get(component_id)
    
    def get_all_components(self) -> List[BaseComponent]:
        """Get all registered components"""
        return list(self._components.values())
    
    def cleanup_all(self) -> None:
        """Clean up all components"""
        for component in list(self._components.values()):
            component.cleanup()
        self._components.clear()
        info("Cleaned up all components")

# Global component registry
_component_registry: Optional[ComponentRegistry] = None

def get_component_registry() -> ComponentRegistry:
    """Get the global component registry"""
    global _component_registry
    if _component_registry is None:
        _component_registry = ComponentRegistry()
    return _component_registry

class CardComponent(BaseComponent):
    """Reusable card component"""
    
    def __init__(self, config: ComponentConfig, content_factory: Optional[Callable] = None):
        super().__init__(config)
        self.content_factory = content_factory
        self._content_element = None
    
    def render(self) -> ui.card:
        """Render card component"""
        card = ui.card()
        
        if self.config.classes:
            card.classes(self.config.classes)
        
        for prop, value in self.config.properties.items():
            card.props(f'{prop}={value}')
        
        # Add title section if provided
        if self.config.title:
            with card:
                with ui.card_section():
                    ui.label(self.config.title).classes('text-h6')
        
        # Add content section
        with card:
            with ui.card_section() as content_section:
                if self.content_factory:
                    self._content_element = self.content_factory()
                else:
                    self._content_element = ui.label("No content provided")
        
        return card
    
    def _update_element(self, data: Any) -> None:
        """Update card content"""
        # Cards typically don't need dynamic updates
        # Content updates should be handled by child components
        pass
    
    def update_content(self, new_content_factory: Callable) -> None:
        """Update card content with new factory"""
        self.content_factory = new_content_factory
        if self._rendered and self._content_element:
            # Clear and recreate content
            self._content_element.clear()
            with self._content_element:
                self.content_factory()

class TabComponent(BaseComponent):
    """Tab component for organizing content"""
    
    def __init__(self, config: ComponentConfig, tabs_config: List[Dict[str, Any]]):
        """Initialize TabComponent with tabs configuration"""
        super().__init__(config)
        self.tabs_config = tabs_config
        self._tab_panels: Dict[str, Any] = {}
    
    def render(self) -> ui.tabs:
        """Render tab component"""
        tabs = ui.tabs()
        
        if self.config.classes:
            tabs.classes(self.config.classes)
        
        # Create tabs
        for tab_config in self.tabs_config:
            tab_id = tab_config['id']
            tab_label = tab_config.get('label', tab_id)
            tab_icon = tab_config.get('icon', None)
            
            ui.tab(tab_id, label=tab_label, icon=tab_icon)
        
        return tabs
    
    def _update_element(self, data: Any) -> None:
        """Update tab component"""
        # Tabs typically don't need dynamic updates
        pass
    
    def create_tab_panels(self, tabs_element: ui.tabs) -> ui.tab_panels:
        """Create tab panels for the tabs"""
        panels = ui.tab_panels(tabs_element)
        
        for tab_config in self.tabs_config:
            tab_id = tab_config['id']
            with ui.tab_panel(tab_id):
                panel_factory = tab_config.get('content_factory')
                if panel_factory:
                    self._tab_panels[tab_id] = panel_factory()
        
        return panels