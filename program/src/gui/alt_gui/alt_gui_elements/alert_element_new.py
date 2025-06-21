"""
Email Alert Service Setup Wizard
Implementiert einen 4-stufigen Wizard für die Konfiguration des Email-Alert-Service mit NiceGUI Stepper
"""

from nicegui import ui
from typing import Dict, List, Optional, Any, Callable
from src.utils.email_alert_service import get_email_alert_service
from datetime import datetime
import re


class EmailAlertWizard:
    """4-Step Email Alert Service Setup Wizard using NiceGUI Stepper"""

    def __init__(self, on_save: Optional[Callable[[Dict[str, Any]], None]] = None):
        """Initialize the Email Alert Wizard

        Args:
            on_save: optional callback invoked with the configuration when saved
        """
        self.on_save = on_save
        self.alert_data = {
            'name': '',
            'emails': [],
            'settings': {
                'no_motion_detected': {
                    'enabled': False,
                    'delay_minutes': 5
                },
                'camera_offline': {
                    'enabled': False
                },
                'system_error': {
                    'enabled': False                },
                'experiment_completes': {
                    'enabled': False
                }
            }
        }
        
    def create_wizard(self) -> ui.card:
        """Create the Email Alert Setup Wizard"""
        with ui.card().classes('w-full max-w-4xl mx-auto') as wizard_card:
            ui.label('Email Alert Service Setup').classes('text-xl font-bold mb-4')
            
            with ui.stepper().props('vertical').classes('w-full') as stepper:
                self.stepper = stepper
                self._create_step1_alert_name()
                self._create_step2_email_addresses()
                self._create_step3_alert_settings()
                self._create_step4_review()
                
        return wizard_card
    
    def _create_step1_alert_name(self):
        """Step 1: Alert Configuration Name"""
        with ui.step('alert_name', title='Alert Configuration Name', icon='label'):
            ui.label('Step 1: Choose a Name for Your Alert Configuration').classes('text-lg font-semibold mb-4')
            ui.label('Give your alert configuration a descriptive name to identify it later.').classes('text-sm text-gray-600 mb-4')
            
            with ui.column().classes('gap-4 w-full'):
                # Alert Name Input
                name_input = ui.input(
                    'Configuration Name',
                    placeholder='e.g., "Lab Monitor Alerts", "Experiment Notifications"'
                ).classes('w-full').props('outlined')
                
                # Suggestions
                ui.label('Suggestions:').classes('text-sm font-medium mt-2')
                suggestions = [
                    'Lab Monitor Alerts',
                    'Experiment Notifications', 
                    'Security Alerts',
                    'System Monitoring',
                    f'CVD Alerts {datetime.now().strftime("%Y-%m-%d")}'
                ]
                
                with ui.row().classes('gap-2 flex-wrap'):
                    for suggestion in suggestions:
                        ui.button(
                            suggestion, 
                            on_click=lambda _, s=suggestion: self._set_alert_name(s, name_input, step1_feedback, step1_next_btn)
                        ).props('size=sm outline color=primary')
                
                # Validation feedback
                step1_feedback = ui.label('').classes('text-sm mt-2')
                
                # Set up validation
                name_input.on('input', lambda: self._validate_step1(name_input, step1_feedback, step1_next_btn))
                
            with ui.stepper_navigation():
                step1_next_btn = ui.button('Next', on_click=lambda: self._next_to_step2(name_input), icon='arrow_forward').props('color=primary')
                step1_next_btn.disable()
    
    def _create_step2_email_addresses(self):
        """Step 2: Email Addresses Configuration"""
        with ui.step('email_config', title='Email Addresses', icon='email'):
            ui.label('Step 2: Configure Email Addresses').classes('text-lg font-semibold mb-4')
            ui.label('Add email addresses that should receive alerts. You can add multiple recipients.').classes('text-sm text-gray-600 mb-4')
            
            with ui.column().classes('gap-4 w-full'):
                # Email Input
                with ui.row().classes('gap-2 w-full items-end'):
                    email_input = ui.input(
                        'Email Address',
                        placeholder='user@example.com'
                    ).classes('flex-1').props('outlined')
                    
                    add_email_btn = ui.button(
                        'Add Email', 
                        icon='add',
                        on_click=lambda: self._add_email(email_input, email_list, step2_feedback, step2_next_btn, email_feedback)
                    ).props('color=primary')
                    add_email_btn.disable()
                
                # Email validation feedback
                email_feedback = ui.label('').classes('text-sm')
                
                # Set up email validation
                email_input.on('input', lambda: self._validate_email_input(email_input, email_feedback, add_email_btn))
                
                # Current Email List
                ui.label('Recipients:').classes('text-sm font-medium mt-4')
                with ui.card().classes('w-full min-h-24'):
                    email_list = ui.column().classes('gap-2 p-2')
                    self._update_email_list(email_list)
                
                # Step validation feedback
                step2_feedback = ui.label('Add at least one valid email address to continue.').classes('text-sm text-orange-600 mt-2')
                
            with ui.stepper_navigation():
                ui.button('Back', on_click=self.stepper.previous, icon='arrow_back').props('flat')
                step2_next_btn = ui.button('Next', on_click=self._next_to_step3, icon='arrow_forward').props('color=primary')
                step2_next_btn.disable()
    
    def _create_step3_alert_settings(self):
        """Step 3: Alert Settings Configuration"""
        with ui.step('alert_settings', title='Alert Settings', icon='settings'):
            ui.label('Step 3: Configure Alert Conditions').classes('text-lg font-semibold mb-4')
            ui.label('Choose which events should trigger email alerts and configure their settings.').classes('text-sm text-gray-600 mb-4')
            
            with ui.column().classes('gap-6 w-full'):
                # Configuration Summary
                ui.separator().classes('my-4')
                ui.label('Configuration Summary:').classes('text-sm font-semibold')
                summary_container = ui.column().classes('gap-2 p-3 bg-gray-50 rounded')
                
                # No Motion Detected Alert
                with ui.expansion('No Motion Detected Alert', icon='motion_photos_off').classes('w-full'):
                    with ui.column().classes('gap-3 p-4'):
                        no_motion_checkbox = ui.checkbox(
                            'Send alert when no motion is detected for extended period',
                            value=False,
                            on_change=lambda e: self._update_no_motion_setting(e.value, summary_container)
                        )
                        
                        with ui.row().classes('gap-4 items-center ml-6'):
                            ui.label('Alert delay:').classes('text-sm')
                            no_motion_delay = ui.number(
                                'Minutes',
                                value=5,
                                min=1,
                                max=1440,
                                on_change=lambda e: self._update_no_motion_delay(e.value, summary_container)
                            ).classes('w-24').props('dense outlined')
                            ui.label('minutes without motion before sending alert').classes('text-sm text-gray-600')
                
                # Camera Offline Alert
                with ui.expansion('Camera Offline Alert', icon='videocam_off').classes('w-full'):
                    with ui.column().classes('gap-3 p-4'):
                        camera_offline_checkbox = ui.checkbox(
                            'Send alert when camera goes offline or becomes unavailable',
                            value=False,
                            on_change=lambda e: self._update_camera_offline_setting(e.value, summary_container)
                        )
                        ui.label('Alert will be sent immediately when camera connection is lost.').classes('text-sm text-gray-600 ml-6')
                
                # System Error Alert
                with ui.expansion('System Error Alert', icon='error').classes('w-full'):
                    with ui.column().classes('gap-3 p-4'):
                        system_error_checkbox = ui.checkbox(
                            'Send alert when system errors occur',
                            value=False,
                            on_change=lambda e: self._update_system_error_setting(e.value, summary_container)
                        )
                        ui.label('Alert will be sent when critical system errors are detected.').classes('text-sm text-gray-600 ml-6')
                  # Experiment Complete Alert
                with ui.expansion('Experiment Complete Alert', icon='science').classes('w-full'):
                    with ui.column().classes('gap-3 p-4'):
                        experiment_complete_checkbox = ui.checkbox(
                            'Send alert when experiments complete',
                            value=False,
                            on_change=lambda e: self._update_experiment_complete_setting(e.value, summary_container)
                        )
                        ui.label('Alert will be sent when a running experiment finishes.').classes('text-sm text-gray-600 ml-6')
                
                self._update_summary(summary_container)
                
            with ui.stepper_navigation():
                ui.button('Back', on_click=self.stepper.previous, icon='arrow_back').props('flat')
                step3_next_btn = ui.button('Review', on_click=self._next_to_step4, icon='arrow_forward').props('color=primary')
                step3_next_btn.enable()  # Always enabled, user can proceed even with no alerts selected
    
    def _create_step4_review(self):
        """Step 4: Review Configuration Before Saving"""
        with ui.step('review', title='Review & Save', icon='preview'):
            ui.label('Step 4: Review Your Configuration').classes('text-lg font-semibold mb-4')
            ui.label('Please review all settings before saving your email alert configuration.').classes('text-sm text-gray-600 mb-6')
            
            with ui.column().classes('gap-6 w-full'):
                # Configuration Overview Card
                with ui.card().classes('w-full p-4 bg-blue-50 border-l-4 border-blue-500'):
                    ui.label('Configuration Overview').classes('text-lg font-semibold text-blue-800 mb-3')
                    
                    # Alert Name
                    with ui.row().classes('gap-3 items-center mb-2'):
                        ui.icon('label').classes('text-blue-600')
                        ui.label('Configuration Name:').classes('font-medium')
                        ui.label(self.alert_data['name'] or 'Not set').classes('font-mono bg-white p-1 rounded')
                    
                    # Email Recipients
                    with ui.row().classes('gap-3 items-start mb-2'):
                        ui.icon('email').classes('text-blue-600')
                        ui.label('Email Recipients:').classes('font-medium')
                        with ui.column().classes('gap-1'):
                            if self.alert_data['emails']:
                                for email in self.alert_data['emails']:
                                    ui.label(f'• {email}').classes('font-mono text-sm bg-white p-1 rounded')
                            else:
                                ui.label('No recipients added').classes('text-orange-600')
                
                # Alert Types Card
                with ui.card().classes('w-full p-4 bg-green-50 border-l-4 border-green-500'):
                    ui.label('Alert Types Configuration').classes('text-lg font-semibold text-green-800 mb-3')
                    
                    alert_types = [
                        ('no_motion_detected', 'No Motion Detected', 'motion_photos_off'),
                        ('camera_offline', 'Camera Offline', 'videocam_off'),
                        ('system_error', 'System Error', 'error'),
                        ('experiment_completes', 'Experiment Complete', 'check_circle')
                    ]
                    
                    active_alerts_count = 0
                    for alert_key, alert_name, icon in alert_types:
                        settings = self.alert_data['settings'][alert_key]
                        is_enabled = settings['enabled']
                        
                        if is_enabled:
                            active_alerts_count += 1
                            
                        with ui.row().classes('gap-3 items-center mb-2'):
                            ui.icon(icon).classes('text-green-600' if is_enabled else 'text-gray-400')
                            ui.label(alert_name).classes('font-medium')
                            if is_enabled:
                                ui.chip('Enabled', color='positive').props('dense')
                                if alert_key == 'no_motion_detected':
                                    ui.label(f'({settings["delay_minutes"]} min delay)').classes('text-sm text-gray-600')
                            else:
                                ui.chip('Disabled', color='grey').props('dense outline')
                    
                    if active_alerts_count == 0:
                        ui.label('⚠️ No alert types are currently enabled').classes('text-orange-600 font-medium mt-2')
                
                # Validation Summary
                with ui.card().classes('w-full p-4 bg-gray-50 border-l-4 border-gray-400'):
                    ui.label('Configuration Status').classes('text-lg font-semibold text-gray-800 mb-3')
                    
                    validation_issues = []
                    
                    if not self.alert_data['name']:
                        validation_issues.append('Configuration name is required')
                    
                    if not self.alert_data['emails']:
                        validation_issues.append('At least one email recipient is required')
                    
                    if active_alerts_count == 0:
                        validation_issues.append('At least one alert type should be enabled')
                    
                    if validation_issues:
                        ui.label('Issues found:').classes('font-medium text-red-600 mb-2')
                        for issue in validation_issues:
                            with ui.row().classes('gap-2 items-center'):
                                ui.icon('error').classes('text-red-500')
                                ui.label(issue).classes('text-red-600')
                    else:
                        with ui.row().classes('gap-2 items-center'):
                            ui.icon('check_circle').classes('text-green-600')
                            ui.label('Configuration is valid and ready to save').classes('text-green-600 font-medium')
            
            # Navigation
            with ui.stepper_navigation():
                ui.button('Back', on_click=self.stepper.previous, icon='arrow_back').props('flat')
                ui.button('Save Configuration', on_click=self._save_configuration, icon='save').props('color=positive')
                ui.button('Test Alerts', on_click=self._test_alerts, icon='send').props('color=warning ')

    def _validate_step1(self, name_input, step1_feedback, step1_next_btn):
        """Validate Step 1: Alert Name"""
        name = name_input.value.strip() if name_input.value else ''
        
        if len(name) < 3:
            step1_feedback.text = 'Name must be at least 3 characters long'
            step1_feedback.classes = 'text-sm mt-2 text-red-600'
            step1_next_btn.disable()
        elif len(name) > 50:
            step1_feedback.text = 'Name must be 50 characters or less'
            step1_feedback.classes = 'text-sm mt-2 text-red-600'
            step1_next_btn.disable()
        else:
            step1_feedback.text = '✓ Valid configuration name'
            step1_feedback.classes = 'text-sm mt-2 text-green-600'
            step1_next_btn.enable()
            self.alert_data['name'] = name
    
    def _set_alert_name(self, name: str, name_input, step1_feedback, step1_next_btn):
        """Set alert name from suggestion"""
        name_input.value = name
        self._validate_step1(name_input, step1_feedback, step1_next_btn)
    
    def _validate_email_input(self, email_input, email_feedback, add_email_btn):
        """Validate email input in real-time"""
        email = email_input.value.strip() if email_input.value else ''
        
        if not email:
            email_feedback.text = ''
            add_email_btn.disable()
            return
            
        if self._is_valid_email(email):
            if email in self.alert_data['emails']:
                email_feedback.text = 'Email already added'
                email_feedback.classes = 'text-sm text-orange-600'
                add_email_btn.disable()
            else:
                email_feedback.text = '✓ Valid email address'
                email_feedback.classes = 'text-sm text-green-600'
                add_email_btn.enable()
        else:
            email_feedback.text = 'Please enter a valid email address'
            email_feedback.classes = 'text-sm text-red-600'
            add_email_btn.disable()
    
    def _is_valid_email(self, email: str) -> bool:
        """Check if email format is valid"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _add_email(self, email_input, email_list, step2_feedback, step2_next_btn, email_feedback):
        """Add email to the list"""
        email = email_input.value.strip()
        if email and self._is_valid_email(email) and email not in self.alert_data['emails']:
            self.alert_data['emails'].append(email)
            email_input.value = ''
            self._update_email_list(email_list)
            self._validate_step2(step2_feedback, step2_next_btn)
            email_feedback.text = ''
    
    def _remove_email(self, email: str, email_list, step2_feedback=None, step2_next_btn=None):
        """Remove email from the list"""
        if email in self.alert_data['emails']:
            self.alert_data['emails'].remove(email)
            self._update_email_list(email_list)
            if step2_feedback and step2_next_btn:
                self._validate_step2(step2_feedback, step2_next_btn)
    
    def _update_email_list(self, email_list):
        """Update the email list display"""
        email_list.clear()
        
        if not self.alert_data['emails']:
            with email_list:
                ui.label('No email addresses added yet').classes('text-gray-500 text-sm italic')
        else:
            with email_list:
                for email in self.alert_data['emails']:
                    with ui.row().classes('gap-2 items-center justify-between w-full p-2 bg-blue-50 rounded'):
                        ui.icon('email').classes('text-blue-600')
                        ui.label(email).classes('flex-1')
                        ui.button(
                            icon='delete',
                            on_click=lambda _, e=email: self._remove_email(e, email_list)
                        ).props('size=sm flat round color=negative')
    
    def _validate_step2(self, step2_feedback, step2_next_btn):
        """Validate Step 2: Email Addresses"""
        if len(self.alert_data['emails']) > 0:
            step2_feedback.text = f'✓ {len(self.alert_data["emails"])} email address(es) configured'
            step2_feedback.classes = 'text-sm mt-2 text-green-600'
            step2_next_btn.enable()
        else:
            step2_feedback.text = 'Add at least one valid email address to continue.'
            step2_feedback.classes = 'text-sm text-orange-600 mt-2'
            step2_next_btn.disable()
    
    def _next_to_step2(self, name_input):
        """Navigate to step 2"""
        if name_input.value and len(name_input.value.strip()) >= 3:
            self.alert_data['name'] = name_input.value.strip()
            self.stepper.next()
    
    def _next_to_step3(self):
        """Navigate to step 3"""
        if len(self.alert_data['emails']) > 0:
            self.stepper.next()
    
    def _next_to_step4(self):
        """Navigate to step 4 (review)"""
        self.stepper.next()
    
    def _update_no_motion_setting(self, value, summary_container):
        """Update no motion detection setting"""
        self.alert_data['settings']['no_motion_detected']['enabled'] = value
        self._update_summary(summary_container)
    
    def _update_no_motion_delay(self, value, summary_container):
        """Update no motion delay setting"""
        self.alert_data['settings']['no_motion_detected']['delay_minutes'] = value
        self._update_summary(summary_container)
    
    def _update_camera_offline_setting(self, value, summary_container):
        """Update camera offline setting"""
        self.alert_data['settings']['camera_offline']['enabled'] = value
        self._update_summary(summary_container)
    
    def _update_system_error_setting(self, value, summary_container):
        """Update system error setting"""
        self.alert_data['settings']['system_error']['enabled'] = value
        self._update_summary(summary_container)
    
    def _update_experiment_complete_setting(self, value, summary_container):
        """Update experiment complete setting"""
        self.alert_data['settings']['experiment_completes']['enabled'] = value
        self._update_summary(summary_container)
    
    def _update_summary(self, summary_container):
        """Update configuration summary"""
        summary_container.clear()
        
        with summary_container:
            # Configuration name
            with ui.row().classes('gap-2 items-center'):
                ui.icon('label').classes('text-blue-600')
                ui.label(f'Name: {self.alert_data["name"] or "Not set"}').classes('font-medium')
            
            # Email recipients
            with ui.row().classes('gap-2 items-center'):
                ui.icon('email').classes('text-blue-600')
                ui.label(f'Recipients: {len(self.alert_data["emails"])} email address(es)')
            
            # Active alerts
            active_alerts = []
            for alert_type, settings in self.alert_data['settings'].items():
                if settings['enabled']:
                    if alert_type == 'no_motion_detected':
                        active_alerts.append(f'No Motion ({settings["delay_minutes"]} min delay)')
                    elif alert_type == 'camera_offline':
                        active_alerts.append('Camera Offline')
                    elif alert_type == 'system_error':
                        active_alerts.append('System Errors')
                    elif alert_type == 'experiment_completes':
                        active_alerts.append('Experiment Complete')
            
            with ui.row().classes('gap-2 items-center'):
                ui.icon('notifications').classes('text-blue-600')
                if active_alerts:
                    ui.label(f'Active Alerts: {", ".join(active_alerts)}')
                else:
                    ui.label('Active Alerts: None selected').classes('text-orange-600')
    
    def _save_configuration(self):
        """Save the alert configuration"""
        if not self.alert_data['name']:
            ui.notify('Please provide a configuration name', type='warning')
            return
            
        if not self.alert_data['emails']:
            ui.notify('Please add at least one email address', type='warning')
            return
        
        # Count active alerts
        active_count = sum(1 for settings in self.alert_data['settings'].values() if settings['enabled'])
        
        if active_count == 0:
            ui.notify('Please enable at least one alert type', type='warning')
            return
        
        # Here you would save the configuration to a file, database, etc.
        ui.notify(
            f'Configuration "{self.alert_data["name"]}" saved successfully! '
            f'{len(self.alert_data["emails"])} recipients, {active_count} alert types enabled.',
            type='positive'
        )

        if self.on_save:
            self.on_save(self.get_configuration())

        # Optional: Close wizard or reset
        self._reset_wizard()
    
    def _test_alerts(self):
        """Send test alerts to verify configuration"""
        if not self.alert_data['emails']:
            ui.notify('Please add email addresses before testing', type='warning')
            return
        
        # Simulate sending test emails
        ui.notify(
            f'Test alerts sent to {len(self.alert_data["emails"])} recipient(s). '
            'Check your email for the test message.',
            type='info'
        )
    
    def _reset_wizard(self):
        """Reset wizard to initial state"""
        self.alert_data = {
            'name': '',
            'emails': [],
            'settings': {
                'no_motion_detected': {'enabled': False, 'delay_minutes': 5},
                'camera_offline': {'enabled': False},
                'system_error': {'enabled': False},
                'experiment_completes': {'enabled': False}
            }
        }
        
        # Go back to first step
        self.stepper.value = 'alert_name'
        
        ui.notify('Wizard reset', type='info')
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get current configuration data"""
        return self.alert_data.copy()


class EmailAlertStatusDisplay:
    """Display current email alert configurations with overview and partially anonymized emails"""
    
    def __init__(self, alert_configurations: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the alert status display
        
        Args:
            alert_configurations: List of alert configurations to display
        """
        self.alert_configurations = alert_configurations or []
        self.update_callback: Optional[Callable[[], None]] = None
        
    def anonymize_email(self, email: str) -> str:
        """
        Partially anonymize email address for display
        Example: test.user@example.com -> t***r@e***e.com
        """
        if not email or '@' not in email:
            return email
            
        local_part, domain = email.split('@', 1)
        
        # Anonymize local part
        if len(local_part) <= 2:
            local_anonymized = local_part[0] + '*'
        else:
            local_anonymized = local_part[0] + '*' * (len(local_part) - 2) + local_part[-1]
        
        # Anonymize domain
        if '.' in domain:
            domain_parts = domain.split('.')
            domain_base = domain_parts[0]
            domain_ext = '.'.join(domain_parts[1:])
            
            if len(domain_base) <= 2:
                domain_anonymized = domain_base[0] + '*'
            else:
                domain_anonymized = domain_base[0] + '*' * (len(domain_base) - 2) + domain_base[-1]
            
            domain_anonymized += '.' + domain_ext
        else:
            if len(domain) <= 2:
                domain_anonymized = domain[0] + '*'
            else:
                domain_anonymized = domain[0] + '*' * (len(domain) - 2) + domain[-1]
        
        return f"{local_anonymized}@{domain_anonymized}"
    
    def get_alert_type_display_name(self, alert_key: str) -> tuple:
        """Get display name and icon for alert type"""
        alert_display_map = {
            'no_motion_detected': ('Keine Bewegung', 'motion_photos_off'),
            'camera_offline': ('Kamera Offline', 'videocam_off'),
            'system_error': ('Systemfehler', 'error'),
            'experiment_completes': ('Experiment Abgeschlossen', 'science')
        }
        return alert_display_map.get(alert_key, (alert_key.replace('_', ' ').title(), 'notifications'))
    
    def create_alert_overview(self) -> ui.card:
        """Create the main alert overview display"""
        with ui.card().classes('w-full') as overview_card:
            # Header
            with ui.row().classes('w-full items-center justify-between mb-4'):
                ui.label('E-Mail Alert Übersicht').classes('text-lg font-semibold')
                ui.button(
                    'Neue Konfiguration',
                    icon='add',
                    on_click=self._show_setup_wizard
                ).props('color=primary')
            
            if not self.alert_configurations:
                # No configurations available
                with ui.column().classes('items-center gap-4 p-8'):
                    ui.icon('notifications_off').classes('text-6xl text-gray-400')
                    ui.label('Keine E-Mail Alerts konfiguriert').classes('text-gray-600 text-center')
                    ui.label('Erstellen Sie eine neue Konfiguration um E-Mail Benachrichtigungen zu erhalten.').classes('text-sm text-gray-500 text-center')
                    ui.button(
                        'Erste Konfiguration erstellen',
                        icon='add_circle',
                        on_click=self._show_setup_wizard
                    ).props('color=primary')
            else:
                # Show configurations
                for config in self.alert_configurations:
                    self._create_configuration_card(config)
        
        return overview_card
    
    def _create_configuration_card(self, config: Dict[str, Any]):
        """Create a card for a single alert configuration"""
        with ui.card().classes('w-full mb-4 border-l-4 border-blue-500'):
            with ui.card_section():
                # Configuration header
                with ui.row().classes('w-full items-center justify-between mb-3'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('label').classes('text-blue-600')
                        ui.label(config.get('name', 'Unbenannte Konfiguration')).classes('font-semibold text-lg')
                    
                    # Status badge
                    active_count = sum(1 for settings in config.get('settings', {}).values() if settings.get('enabled', False))
                    status_color = 'positive' if active_count > 0 else 'grey'
                    status_text = f'{active_count} Alert(s) aktiv' if active_count > 0 else 'Inaktiv'
                    ui.chip(status_text, color=status_color).props('dense')
                
                # Email recipients
                emails = config.get('emails', [])
                with ui.row().classes('items-center gap-2 mb-3'):
                    ui.icon('email').classes('text-gray-600')
                    ui.label(f'Empfänger ({len(emails)}):').classes('font-medium')
                    
                if emails:
                    with ui.row().classes('gap-2 flex-wrap ml-6'):
                        for email in emails:
                            ui.chip(self.anonymize_email(email)).props('dense outline')
                else:
                    ui.label('Keine E-Mail Adressen konfiguriert').classes('text-orange-600 text-sm ml-6')
                
                # Alert types
                settings = config.get('settings', {})
                active_alerts = []
                inactive_alerts = []
                
                for alert_key, alert_settings in settings.items():
                    display_name, icon = self.get_alert_type_display_name(alert_key)
                    alert_info = {
                        'key': alert_key,
                        'name': display_name,
                        'icon': icon,
                        'settings': alert_settings
                    }
                    
                    if alert_settings.get('enabled', False):
                        active_alerts.append(alert_info)
                    else:
                        inactive_alerts.append(alert_info)
                
                # Active alerts
                if active_alerts:
                    with ui.row().classes('items-center gap-2 mb-2'):
                        ui.icon('notifications_active').classes('text-green-600')
                        ui.label('Aktive Alerts:').classes('font-medium')
                    
                    with ui.column().classes('gap-2 ml-6'):
                        for alert in active_alerts:
                            with ui.row().classes('items-center gap-2'):
                                ui.icon(alert['icon']).classes('text-green-600')
                                ui.label(alert['name']).classes('text-sm')
                                
                                # Show additional settings
                                if alert['key'] == 'no_motion_detected':
                                    delay = alert['settings'].get('delay_minutes', 5)
                                    ui.chip(f'{delay} Min Verzögerung', color='blue').props('dense outline')
                
                # Inactive alerts (if any active alerts exist, show inactive ones collapsed)
                if inactive_alerts and active_alerts:
                    with ui.expansion('Inaktive Alerts', icon='notifications_off').classes('w-full mt-2'):
                        with ui.column().classes('gap-1 p-2'):
                            for alert in inactive_alerts:
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon(alert['icon']).classes('text-gray-400')
                                    ui.label(alert['name']).classes('text-sm text-gray-600')
                  # Action buttons
                with ui.row().classes('gap-2 mt-4'):
                    ui.button(
                        'Bearbeiten',
                        icon='edit',
                        on_click=lambda e, c=config: self._edit_configuration(c)
                    ).props('size=sm color=primary')
                    
                    ui.button(
                        'Test senden',
                        icon='send',
                        on_click=lambda e, c=config: self._send_test_alert(c)
                    ).props('size=sm color=warning')
                    
                    ui.button(
                        'Löschen',
                        icon='delete',
                        on_click=lambda e, c=config: self._delete_configuration(c)
                    ).props('size=sm color=negative')
    
    def create_compact_status_widget(self) -> ui.card:
        """Create a compact status widget for dashboard integration"""
        with ui.card().classes('w-full max-w-sm') as status_widget:
            with ui.card_section():
                # Header
                with ui.row().classes('items-center justify-between mb-3'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('notifications').classes('text-blue-600')
                        ui.label('E-Mail Alerts').classes('font-semibold')
                    
                    # Quick status indicator
                    total_configs = len(self.alert_configurations)
                    active_configs = sum(1 for config in self.alert_configurations 
                                       if sum(1 for settings in config.get('settings', {}).values() 
                                             if settings.get('enabled', False)) > 0)
                    
                    if active_configs > 0:
                        ui.icon('check_circle').classes('text-green-600').tooltip(f'{active_configs} von {total_configs} Konfigurationen aktiv')
                    else:
                        ui.icon('warning').classes('text-orange-600').tooltip('Keine aktiven Alert-Konfigurationen')
                
                # Quick summary
                if total_configs == 0:
                    ui.label('Keine Konfigurationen').classes('text-gray-600 text-sm')
                else:
                    ui.label(f'{total_configs} Konfiguration(en)').classes('text-sm')
                    if active_configs > 0:
                        total_recipients = sum(len(config.get('emails', [])) for config in self.alert_configurations)
                        ui.label(f'{total_recipients} Empfänger insgesamt').classes('text-xs text-gray-600')
                
                # Quick action button
                ui.button(
                    'Verwalten' if total_configs > 0 else 'Einrichten',
                    icon='settings' if total_configs > 0 else 'add',
                    on_click=self._show_management_dialog
                ).props('size=sm color=primary outline').classes('w-full mt-2')
        
        return status_widget
    
    def add_configuration(self, config: Dict[str, Any]):
        """Add a new alert configuration"""
        self.alert_configurations.append(config)
    
    def remove_configuration(
        self,
        config: Dict[str, Any],
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Remove an alert configuration"""
        if config in self.alert_configurations:
            self.alert_configurations.remove(config)
        cb = callback or self.update_callback
        if cb:
            cb()
    
    def update_configuration(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        callback: Optional[Callable[[], None]] = None,
    ):
        """Update an existing configuration"""
        try:
            index = self.alert_configurations.index(old_config)
            self.alert_configurations[index] = new_config
        except ValueError:
            pass  # Configuration not found
        cb = callback or self.update_callback
        if cb:
            cb()
    
    # Event handlers for UI actions
    def _show_setup_wizard(self):
        """Show the setup wizard dialog"""
        def _on_save(config: Dict[str, Any]):
            self.add_configuration(config)
            dialog.close()

        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            create_email_alert_wizard(on_save=_on_save)
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Schließen', on_click=dialog.close).props('flat')

        dialog.open()

    def _edit_configuration(self, config: Dict[str, Any]):
        """Edit an existing configuration"""
        def _on_save(new_cfg: Dict[str, Any]):
            self.update_configuration(
                config,
                new_cfg,
                callback=self.update_callback,
            )
            dialog.close()

        wizard = EmailAlertWizard(on_save=_on_save)
        wizard.alert_data = config.copy()

        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            wizard.create_wizard()
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Schließen', on_click=dialog.close).props('flat')

        dialog.open()
    
    def _send_test_alert(self, config: Dict[str, Any]):
        """Send a test alert for the configuration"""
        service = get_email_alert_service()
        if service is None:
            ui.notify('EmailAlertService nicht verfügbar', type='warning')
            return

        subject = f"Test-Alert ({config.get('name', 'Alert')})"
        body = 'Dies ist ein Test des E-Mail-Alert-Systems.'
        sent = 0
        for email in config.get('emails', []):
            if service.send_alert(subject, body, recipient=email):
                sent += 1

        ui.notify(
            f'Test-Alert an {sent} Empfänger gesendet',
            type='positive' if sent else 'warning'
        )

    def _delete_configuration(
        self,
        config: Dict[str, Any],
        callback: Optional[Callable[[], None]] = None,
    ):
        """Delete a configuration with confirmation"""
        config_name = config.get('name', 'Unbenannte Konfiguration')

        with ui.dialog() as dialog:
            with ui.card():
                ui.label('Konfiguration löschen').classes('text-lg font-bold')
                ui.label(
                    f'Möchten Sie "{config_name}" wirklich löschen?'
                ).classes('mt-2')

                with ui.row().classes('gap-2 justify-end mt-4'):
                    ui.button('Abbrechen', on_click=dialog.close).props('flat')

                    def _confirm():
                        self.remove_configuration(config, callback)
                        dialog.close()

                    ui.button('Löschen', on_click=_confirm).props('color=negative')

        dialog.open()

    def _show_management_dialog(self):
        """Show the alert management dialog"""
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-6xl'):
            ui.label('E-Mail Alert Verwaltung').classes('text-xl font-bold mb-4')
            self.create_alert_overview()
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Schließen', on_click=dialog.close).props('flat')

        dialog.open()


def create_email_alert_wizard(on_save: Optional[Callable[[Dict[str, Any]], None]] = None) -> ui.card:
    """Factory function to create an Email Alert Setup Wizard"""
    wizard = EmailAlertWizard(on_save=on_save)
    return wizard.create_wizard()


def create_email_alert_status_display(configurations: Optional[List[Dict[str, Any]]] = None) -> ui.card:
    """Factory function to create an Email Alert Status Display"""
    display = EmailAlertStatusDisplay(configurations)
    return display.create_alert_overview()


def create_compact_alert_widget(configurations: Optional[List[Dict[str, Any]]] = None) -> ui.card:
    """Factory function to create a compact alert status widget"""
    display = EmailAlertStatusDisplay(configurations)
    return display.create_compact_status_widget()


# Example usage and test data
def create_demo_configurations() -> List[Dict[str, Any]]:
    """Create demo alert configurations for testing"""
    return [
        {
            'name': 'Labor Überwachung',
            'emails': ['admin@lab.example.com', 'security@lab.example.com', 'technician@lab.example.com'],
            'settings': {
                'no_motion_detected': {'enabled': True, 'delay_minutes': 10},
                'camera_offline': {'enabled': True},
                'system_error': {'enabled': True},
                'experiment_completes': {'enabled': False}
            }
        },
        {
            'name': 'Experiment Benachrichtigungen',
            'emails': ['researcher@university.edu', 'supervisor@university.edu'],
            'settings': {
                'no_motion_detected': {'enabled': False, 'delay_minutes': 5},
                'camera_offline': {'enabled': False},
                'system_error': {'enabled': True},
                'experiment_completes': {'enabled': True}
            }
        },
        {
            'name': 'Inaktive Konfiguration',
            'emails': ['test@example.com'],
            'settings': {
                'no_motion_detected': {'enabled': False, 'delay_minutes': 5},
                'camera_offline': {'enabled': False},
                'system_error': {'enabled': False},
                'experiment_completes': {'enabled': False}
            }
        }
    ]
