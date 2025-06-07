from pathlib import Path
import pytest
from nicegui import Client

pytest_plugins = ['nicegui.testing.user_plugin']

from src.utils.container import ApplicationContainer

@pytest.mark.asyncio
async def test_gui_pages(user):
    container = ApplicationContainer.create(Path('program/config'))
    # Disable problematic live plot updates
    from src.gui.gui_elements import gui_live_plot_element
    gui_live_plot_element.LivePlotComponent._refresh_plot = lambda self: None
    with Client.auto_index_client:
        container.web_application.register_components()
    await user.open('/')
    await user.should_see('Dashboard')
    await user.open('/sensors')
    await user.should_see('Sensor Management')
    container.shutdown_sync()
