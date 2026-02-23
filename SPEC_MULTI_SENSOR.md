# Specification: Multi-Sensor Support

## Goal
Transform the application from a single-sensor utility to a multi-sensor platform. A "sensor" represents a logical brightness measurement derived from one or more camera sources.

## Requirements
1.  **Multiple Sensors:** Support defining multiple sensors in the configuration.
2.  **Aggregate Sources:** Each sensor can calculate its brightness from the mean of multiple image sources.
3.  **Independent Topics:** Each sensor publishes to its own configured MQTT topic.
4.  **Delayed Variants:** Each sensor can optionally publish a delayed value (e.g., "what was the brightness 30 minutes ago?").
5.  **History Persistence:** History must be tracked per sensor in the database.

## Configuration Changes
The `config.yaml` will be restructured to support a list of sensors.

### New Schema (Example)
```yaml
log_level: "INFO"
interval: 60  # Global default interval in seconds

mqtt:
  host: "192.168.9.5"
  port: 1883

sensors:
  - name: "indoor_brightness"
    sources:
      - "http://camera1.local/latest.jpg"
      - "http://camera2.local/latest.jpg"
    topic: "house/brightness/indoor"
    delay_seconds: 1800  # 30 minutes
    delayed_topic: "house/brightness/indoor/delayed"

  - name: "outdoor_brightness"
    sources:
      - "http://camera3.local/latest.jpg"
    topic: "house/brightness/outdoor"
    # No delay configured for this one
```

## MQTT Topic Structure
To ensure discoverability and prevent message collisions, topics should follow a hierarchical pattern.

### Recommended Pattern
`{prefix}/{sensor_name}/{measurement_type}`

*   **Prefix:** Default is `cameralight`.
*   **Sensor Name:** The unique name defined in the config.
*   **Measurement Type:** `brightness` for real-time or `brightness_delayed` for history-based values.

### Example
| Sensor | Type | Topic |
| :--- | :--- | :--- |
| `indoor` | Real-time | `cameralight/indoor/brightness` |
| `indoor` | Delayed | `cameralight/indoor/brightness_delayed` |
| `outdoor` | Real-time | `cameralight/outdoor/brightness` |

This structure allows for powerful wildcard subscriptions, such as `cameralight/+/brightness` to monitor all sensors simultaneously.

## Technical Design

### 1. Data Model
*   **Settings/Config:** Use Pydantic to validate the list of `SensorConfig` objects.
*   **Database Schema:** Update the `history` table to include a `sensor_name` column.
    ```sql
    CREATE TABLE history (
        ts INTEGER,
        sensor_name TEXT,
        value REAL
    );
    CREATE INDEX idx_history_sensor_ts ON history(sensor_name, ts);
    ```

### 2. Execution Loop
The `main.py` loop will be updated to:
1.  Iterate through each configured sensor.
2.  For each sensor:
    a. Fetch images from all defined `sources`.
    b. Calculate the average brightness for each image.
    c. Calculate the mean of those averages.
    d. Publish the current mean to `topic`.
    e. Record the mean and current timestamp in the database.
    f. If `delayed_topic` and `delay_seconds` are set:
        i. Query the database for the value closest to `current_time - delay_seconds`.
        ii. Publish the result to `delayed_topic`.

### 3. Database Migration
Since this is a breaking change for the database schema, the application should:
*   Automatically migrate the existing `history` table if it lacks the `sensor_name` column (defaulting existing data to a generic name like "default").
*   Or, simply recreate the table if data persistence is not critical during the transition.

## Implementation Steps
1.  Update `settings.py` to reflect the new nested Pydantic models.
2.  Update `database.py` to handle `sensor_name` in queries and insertion.
3.  Update `main.py` to loop over sensors and aggregate multiple sources.
4.  Update existing tests (if any) and add new ones for multi-source aggregation.
