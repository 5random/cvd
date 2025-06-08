# Notification Center Configuration

The notification center collects events from sensors, controllers and other parts of
the application. Several parameters can be tuned through the configuration file
under the key `ui.notification_center`.

Example snippet:

```json
{
  "ui": {
    "notification_center": {
      "max_notifications": 500,
      "history_file": "data/notifications/history.json",
      "update_interval_s": 5
    }
  }
}
```

* `max_notifications` – maximum number of notifications kept in memory.
* `history_file` – path of the JSON file used to persist notification history.
* `update_interval_s` – interval in seconds used by the background timer that
  checks for new notifications.
