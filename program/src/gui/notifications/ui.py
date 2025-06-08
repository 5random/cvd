"""UI helper mixin for the NotificationCenter."""
from datetime import datetime, timedelta
from typing import List

from nicegui import ui

from src.gui.notifications.models import Notification, NotificationSeverity, NotificationSource

class NotificationUIMixin:
    """Mixin providing UI rendering helpers for NotificationCenter."""

    notifications: List[Notification]
    _notification_list: None
    _badge_counter: None
    _dialog: None
    _menu: None
    _notification_list_container: None
    _severity_filter: str
    _source_filter: str

    def create_notification_button(self) -> ui.button:
        with ui.row().classes('relative'):
            button = ui.button(icon='notifications', color='5898d4').props('flat round').classes('relative')
            unread_count = self.get_unread_count()
            self._badge_counter = ui.badge(str(unread_count) if unread_count > 0 else '', color='red').props('floating').classes('absolute -top-2 -right-2')
            if unread_count == 0:
                self._badge_counter.set_visibility(False)
            with button:
                self._create_notification_menu()
        return button

    def _create_notification_menu(self) -> None:
        with ui.menu().props('max-width=400px') as menu:
            self._menu = menu
            with ui.card().classes('w-96 max-h-[70vh]'):
                with ui.card_section().classes('bg-blue-600 text-white'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label('Benachrichtigungen').classes('text-h6')
                        ui.button(icon='close', color='5898d4', on_click=menu.close).props('flat round dense')
                with ui.card_section().classes('py-2'):
                    with ui.row().classes('items-center gap-2'):
                        with ui.select(['all', 'info', 'warning', 'error', 'success'], value=self._severity_filter, label='Priorität', on_change=self._on_severity_filter_change).props('dense options-dense').classes('text-xs w-28'):
                            pass
                        with ui.select(['all', 'experiment', 'sensor', 'controller', 'system', 'config'], value=self._source_filter, label='Quelle', on_change=self._on_source_filter_change).props('dense options-dense').classes('text-xs w-28'):
                            pass
                with ui.card_section().classes('overflow-auto max-h-[50vh]') as list_container:
                    self._notification_list_container = list_container
                    self._create_notification_list()
                with ui.card_section().classes('py-2 bg-gray-100'):
                    with ui.row().classes('justify-between'):
                        ui.button('Alle gelesen', on_click=self.mark_all_as_read, icon='mark_email_read').props('outline flat dense')
                        ui.button('Alle löschen', on_click=self._confirm_clear_all, icon='clear_all').props('outline flat dense color=negative')

    def show_notification_dialog(self) -> None:
        if self._menu:
            self._menu.open()

    def _create_notification_list(self) -> None:
        filtered_notifications = self._get_filtered_notifications()
        if not filtered_notifications:
            with ui.column().classes('w-full items-center justify-center p-4'):
                ui.icon('notifications_none', size='2rem').classes('text-gray-400')
                ui.label('Keine Benachrichtigungen').classes('text-sm text-gray-500')
            return
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        grouped_notifications = {'Heute': [], 'Gestern': [], 'Älter': []}
        for notification in filtered_notifications:
            notif_date = notification.timestamp.date()
            if notif_date == today:
                grouped_notifications['Heute'].append(notification)
            elif notif_date == yesterday:
                grouped_notifications['Gestern'].append(notification)
            else:
                grouped_notifications['Älter'].append(notification)
        for group_name, group_notifications in grouped_notifications.items():
            if not group_notifications:
                continue
            ui.label(group_name).classes('text-xs font-bold mt-2 mb-1 text-gray-500')
            for notification in group_notifications:
                self._create_notification_item(notification)

    def _create_notification_item(self, notification: Notification) -> None:
        card_classes = 'w-full mb-1 cursor-pointer hover:shadow-md transition-shadow rounded-sm'
        if not notification.read:
            card_classes += ' border-l-4'
            if notification.severity == NotificationSeverity.ERROR:
                card_classes += ' border-red-500 bg-red-50'
            elif notification.severity == NotificationSeverity.WARNING:
                card_classes += ' border-orange-500 bg-orange-50'
            elif notification.severity == NotificationSeverity.SUCCESS:
                card_classes += ' border-green-500 bg-green-50'
            else:
                card_classes += ' border-blue-500 bg-blue-50'
        with ui.card().classes(card_classes):
            with ui.card_section().classes('p-2'):
                with ui.row().classes('items-center gap-1 mb-1'):
                    icon_map = {
                        NotificationSeverity.ERROR: ('error', 'text-red-500'),
                        NotificationSeverity.WARNING: ('warning', 'text-orange-500'),
                        NotificationSeverity.SUCCESS: ('check_circle', 'text-green-500'),
                        NotificationSeverity.INFO: ('info', 'text-blue-500')
                    }
                    icon, icon_class = icon_map.get(notification.severity, ('info', 'text-gray-500'))
                    ui.icon(icon, size='xs').classes(icon_class)
                    title_classes = 'text-sm flex-1'
                    if not notification.read:
                        title_classes += ' font-bold'
                    ui.label(notification.title).classes(title_classes).on('click', lambda e, notif_id=notification.id: self.mark_as_read(notif_id))
                    ui.button(icon='close', on_click=lambda e, notif_id=notification.id: self.delete_notification(notif_id)).props('flat dense size=xs').classes('text-gray-400 hover:text-red-500')
                    if not notification.read:
                        ui.icon('circle', size='xs').classes('text-blue-500')
                message_classes = 'text-xs text-gray-600'
                if not notification.read:
                    message_classes = 'text-xs text-gray-800'
                message = notification.message
                if len(message) > 100:
                    message = message[:97] + '...'
                ui.label(message).classes(message_classes)
                with ui.row().classes('items-center justify-between mt-1'):
                    source_display = notification.source.value.replace('_', ' ').capitalize()
                    ui.label(source_display).classes('text-xs text-gray-500')
                    time_str = notification.timestamp.strftime('%H:%M')
                    ui.label(time_str).classes('text-xs text-gray-400')
                if notification.action_label and notification.action_callback:
                    ui.button(notification.action_label, on_click=notification.action_callback).props('dense flat size="xs"').classes('mt-1 text-xs')

    def _get_filtered_notifications(self) -> List[Notification]:
        filtered = self.notifications
        if self._severity_filter != 'all':
            filtered = [n for n in filtered if n.severity.value == self._severity_filter]
        if self._source_filter != 'all':
            filtered = [n for n in filtered if n.source.value == self._source_filter]
        return sorted(filtered, key=lambda n: n.timestamp, reverse=True)

    def _on_severity_filter_change(self, event) -> None:
        self._severity_filter = event.value
        self._update_notification_list()

    def _on_source_filter_change(self, event) -> None:
        self._source_filter = event.value
        self._update_notification_list()

    def _update_notification_list(self) -> None:
        if self._notification_list_container:
            self._notification_list_container.clear()
            with self._notification_list_container:
                self._create_notification_list()

    def _confirm_clear_all(self) -> None:
        with ui.dialog() as confirm_dialog:
            with ui.card().classes('w-72'):
                ui.label('Alle Benachrichtigungen löschen?').classes('text-base mb-2')
                ui.label('Diese Aktion kann nicht rückgängig gemacht werden.').classes('text-xs text-gray-600 mb-2')
                with ui.row().classes('gap-2 justify-end'):
                    ui.button('Abbrechen', on_click=confirm_dialog.close).props('dense')
                    ui.button('Löschen', on_click=lambda: (self.clear_notifications(), confirm_dialog.close()), color='negative').props('dense')
        confirm_dialog.open()

    def _update_ui(self) -> None:
        if self._badge_counter:
            unread_count = self.get_unread_count()
            self._badge_counter.set_text(str(unread_count) if unread_count > 0 else '')
            self._badge_counter.set_visibility(unread_count > 0)
        self._update_notification_list()
