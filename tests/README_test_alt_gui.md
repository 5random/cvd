# Tests für alt_gui.py

Diese Datei enthält umfassende Tests für die `SimpleGUIApplication` aus `alt_application.py` unter Verwendung des NiceGUI Testing Frameworks.

## Überblick

Die Tests sind in mehrere Kategorien unterteilt:

### 1. TestSimpleGUIApplicationBasics
- Tests für grundlegende Funktionalitäten
- Initialisierung der Anwendung
- Standard-Einstellungen

### 2. TestSimpleGUIApplicationUI  
- Tests für die Benutzeroberfläche
- Laden der Hauptseite
- Header-Elemente
- Dark Mode Toggle

### 3. TestSimpleGUIApplicationCameraFunctionality
- Tests für Kamera-Funktionalitäten
- Kamera-Status Updates
- Kamera-Einstellungen (Sensitivity, FPS, Resolution, Rotation)

### 4. TestSimpleGUIApplicationExperimentManagement
- Tests für Experiment-Management
- Experiment-Sektion Creation
- Standard-Experiment-Einstellungen

### 5. TestSimpleGUIApplicationAlertSystem
- Tests für das Alert-System
- Alert-Status Updates
- Alert-Konfiguration Loading

### 6. TestSimpleGUIApplicationNavigation
- Tests für Navigation und Seitenaktionen
- Fullscreen Toggle
- Page Reload

### 7. TestSimpleGUIApplicationIntegration
- Integrationstests für die gesamte Anwendung
- Vollständiges Layout Creation
- Zeit-Anzeige Updates

### 8. TestSimpleGUIApplicationErrorHandling
- Tests für Fehlerbehandlung
- Behandlung fehlender Controller
- Ungültige Einstellungen

### 9. TestSimpleGUIApplicationWithMockControllers
- Tests mit Mock-Controllern
- Erweiterte Kamera- und Motion Detection-Funktionalität

### 10. TestSimpleGUIApplicationPerformance
- Performance-Tests (markiert mit @pytest.mark.slow)
- Schnelle aufeinanderfolgende Updates

## Mock-Klassen

### MockEmailAlertService
Erbt von der echten `EmailAlertService` Klasse und überschreibt kritische Methoden für Test-Zwecke.

### MockControllerManager
Simuliert den Controller Manager mit der Möglichkeit, Mock-Controller hinzuzufügen.

### MockExperimentManager
Simuliert den Experiment Manager mit Test-Daten.

## Verwendung

### Einzelne Tests ausführen:
```bash
# Alle Tests für alt_gui
pytest tests/test_alt_gui.py -v

# Bestimmte Test-Klasse
pytest tests/test_alt_gui.py::TestSimpleGUIApplicationBasics -v

# Bestimmten Test
pytest tests/test_alt_gui.py::TestSimpleGUIApplicationBasics::test_application_initialization -v

# Performance-Tests überspringen
pytest tests/test_alt_gui.py -v -m "not slow"
```

### Debugging mit Ausgabe:
```bash
pytest tests/test_alt_gui.py -v -s
```

### Mit Coverage:
```bash
pytest tests/test_alt_gui.py --cov=program.src.gui.alt_application
```

## Fixtures

- `mock_config_service`: Erstellt einen Mock Configuration Service
- `mock_controller_manager`: Erstellt einen Mock Controller Manager
- `mock_experiment_manager`: Erstellt einen Mock Experiment Manager
- `simple_gui_app`: Erstellt eine vollständig konfigurierte SimpleGUIApplication für Tests

## Erweiterte Test-Szenarien

### Hinzufügen neuer Tests:

1. **UI-Tests**: Verwenden Sie das `user` Fixture für Interaktion mit der GUI
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

2. **Mock Controller Tests**: Erstellen Sie spezifische Mock-Controller
```python
def test_new_controller_feature(simple_gui_app):
    mock_controller = Mock()
    mock_controller.some_method = Mock(return_value="test_result")
    
    simple_gui_app.controller_manager.add_mock_controller("test_controller", mock_controller)
    
    # Test your functionality
    result = simple_gui_app.some_method_that_uses_controller()
    assert result == "expected_result"
```

3. **Async Tests**: Verwenden Sie AsyncMock für asynchrone Operationen
```python
async def test_async_functionality(simple_gui_app):
    mock_async_method = AsyncMock(return_value="async_result")
    simple_gui_app.some_async_component.method = mock_async_method
    
    result = await simple_gui_app.call_async_method()
    assert result == "async_result"
    mock_async_method.assert_called_once()
```

## Bekannte Limitationen

1. **JavaScript-basierte Funktionen**: Funktionen wie Fullscreen-Toggle führen JavaScript aus, das in Tests nicht vollständig simuliert werden kann.

2. **Timing-abhängige Tests**: Timer-basierte Updates können in Tests schwer zu prüfen sein.

3. **Externe Abhängigkeiten**: SMTP-Services und Hardware-Kameras werden durch Mocks ersetzt.

## Tipps für Entwickler

1. **Test-Isolation**: Jeder Test sollte unabhängig laufen können
2. **Mock richtig**: Mocken Sie nur das Nötige, um Tests fokussiert zu halten
3. **Aussagekräftige Assertions**: Verwenden Sie spezifische Assertions statt nur `assert True`
4. **Error-Handling testen**: Vergessen Sie nicht, Fehlerfälle zu testen
5. **Performance bewusst**: Markieren Sie langsame Tests entsprechend

## Zukünftige Erweiterungen

- Integration mit echten Hardware-Controllern in CI/CD
- Screenshot-Tests für UI-Regression
- Load-Tests für Multi-User-Szenarien
- Accessibility-Tests für die GUI-Elemente
