# Tests for ``alt_gui.py``

This file contains comprehensive tests for the ``SimpleGUIApplication`` from
``alt_application.py`` using the NiceGUI testing framework.

## Overview

The tests are divided into several categories:

### 1. TestSimpleGUIApplicationBasics
- Tests for basic functionality
- Application initialization
- Default settings

### 2. TestSimpleGUIApplicationUI
- Tests for the user interface
- Loading the main page
- Header elements
- Dark mode toggle

### 3. TestSimpleGUIApplicationCameraFunctionality
- Tests for camera functionality
- Camera status updates
- Camera settings (Sensitivity, FPS, Resolution, Rotation)

### 4. TestSimpleGUIApplicationExperimentManagement
- Tests for experiment management
- Experiment section creation
- Default experiment settings

### 5. TestSimpleGUIApplicationAlertSystem
- Tests for the alert system
- Alert status updates
- Alert configuration loading

### 6. TestSimpleGUIApplicationNavigation
- Tests for navigation and page actions
- Fullscreen toggle
- Page reload

- Integration tests for the entire application
- Full layout creation
- Time display updates

### 8. TestSimpleGUIApplicationErrorHandling
- Tests for error handling
- Handling missing controllers
- Invalid settings

### 9. TestSimpleGUIApplicationWithMockControllers
- Tests with mock controllers
- Extended camera and motion detection functionality

### 10. TestSimpleGUIApplicationPerformance
- Performance tests (marked with @pytest.mark.slow)
- Rapid consecutive updates

## Mock classes

### MockEmailAlertService
Inherits from the real ``EmailAlertService`` class and overrides critical methods for testing.

### MockControllerManager
Simulates the controller manager with the ability to add mock controllers.

### MockExperimentManager
Simulates the experiment manager with test data.

## Usage

### Running individual tests:
```bash
# Run all tests for alt_gui
pytest tests/test_alt_gui.py -v

# Specific test class
pytest tests/test_alt_gui.py::TestSimpleGUIApplicationBasics -v

# Specific test
pytest tests/test_alt_gui.py::TestSimpleGUIApplicationBasics::test_application_initialization -v

# Skip performance tests
pytest tests/test_alt_gui.py -v -m "not slow"
```

### Debugging with output:
```bash
pytest tests/test_alt_gui.py -v -s
```

### With coverage:
```bash
pytest tests/test_alt_gui.py --cov=src.gui.alt_application
```

## Fixtures

- `mock_config_service`: creates a mock configuration service
- `mock_controller_manager`: creates a mock controller manager
- `mock_experiment_manager`: creates a mock experiment manager
- `simple_gui_app`: creates a fully configured ``SimpleGUIApplication`` for tests

## Advanced test scenarios

### Adding new tests:

1. **UI tests**: use the `user` fixture for interaction with the GUI
```python
async def test_new_ui_feature(user: User, simple_gui_app):
    @ui.page('/')
    def main_page():
        simple_gui_app.create_main_layout()
    
    await user.open('/')
    await user.should_see('Expected Text')
    user.find('Button Text').click()
    await user.should_see('Result Text')
```

2. **Mock controller tests**: create specific mock controllers
```python
def test_new_controller_feature(simple_gui_app):
    mock_controller = Mock()
    mock_controller.some_method = Mock(return_value="test_result")
    
    simple_gui_app.controller_manager.add_mock_controller("test_controller", mock_controller)
    
    # Test your functionality
    result = simple_gui_app.some_method_that_uses_controller()
    assert result == "expected_result"
```

3. **Async tests**: use ``AsyncMock`` for asynchronous operations
```python
async def test_async_functionality(simple_gui_app):
    mock_async_method = AsyncMock(return_value="async_result")
    simple_gui_app.some_async_component.method = mock_async_method
    
    result = await simple_gui_app.call_async_method()
    assert result == "async_result"
    mock_async_method.assert_called_once()
```

## Known limitations

1. **JavaScript-based functions**: functions such as the fullscreen toggle run JavaScript which cannot be fully simulated in tests.

2. **Timing-dependent tests**: timer-based updates can be difficult to verify in tests.

3. **External dependencies**: SMTP services and hardware cameras are replaced with mocks.

## Tips for developers

1. **Test isolation**: each test should be able to run independently
2. **Mock appropriately**: mock only what is necessary to keep tests focused
3. **Meaningful assertions**: use specific assertions instead of just `assert True`
4. **Test error handling**: don't forget to test failure cases
5. **Performance awareness**: mark slow tests accordingly

## Future extensions

- Integration with real hardware controllers in CI/CD
- Screenshot tests for UI regression
- Load tests for multi-user scenarios
- Accessibility tests for the GUI elements
