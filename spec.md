# FloodSense Backend API Specification

This document defines the current backend API contract for the FloodSense frontend and the updated service endpoints.

## Base Path

All endpoints are exposed under:

`/api/v1`

## Public Endpoints

### 1. GET /api/v1/sensors

Response:

```json
{
  "status": "success",
  "timestamp": "2026-04-22T23:05:00Z",
  "count": 2,
  "data": [
    {
      "sensor_id": "MR-KND-001",
      "name": "Mahaweli River — Getambe Bridge",
      "location": {
        "lat": 7.2721,
        "lng": 80.6132,
        "zone_id": "ZONE-K1",
        "zone_name": "Getambe Basin"
      },
      "readings": {
        "water_level_m": 4.53,
        "rainfall_mm_per_hr": 8.2,
        "flow_velocity_mps": 0.85,
        "temperature_c": 28.5,
        "air_pressure_hpa": 1011.2
      },
      "status": {
        "device_online": true,
        "battery_percent": 75,
        "signal_strength_dbm": -68,
        "last_seen": "2026-04-22T23:04:12Z"
      },
      "thresholds": {
        "water_level_warning_m": 5.0,
        "water_level_critical_m": 6.5
      }
    },
    {
      "sensor_id": "MR-KND-002",
      "name": "Mahaweli River — Peradeniya",
      "location": {
        "lat": 7.252,
        "lng": 80.5921,
        "zone_id": "ZONE-K2",
        "zone_name": "Peradeniya Basin"
      },
      "readings": {
        "water_level_m": 2.1,
        "rainfall_mm_per_hr": 0.0,
        "flow_velocity_mps": 0.42,
        "temperature_c": 27.8,
        "air_pressure_hpa": 1012.5
      },
      "device_health": {
        "is_online": true,
        "battery_percent": 92,
        "signal_strength_dbm": -55,
        "last_seen": "2026-04-22T23:00:05Z"
      },
      "thresholds": {
        "warning_m": 3.5,
        "critical_m": 5.0
      }
    }
  ]
}
```

### 2. GET /api/v1/sensors/{sensor_id}

Response:

```json
{
  "status": "success",
  "data": {
    "sensor_id": "MR-KND-001",
    "name": "Mahaweli River — Getambe Bridge",
    "installed_date": "2025-11-20",
    "is_active": true,
    "location": {
      "lat": 7.2721,
      "lng": 80.6132,
      "zone_id": "ZONE-K1",
      "address": "Under Getambe Bridge, Peradeniya Road, Kandy"
    },
    "current_reading": {
      "water_level_m": 4.53,
      "rainfall_mm_per_hr": 8.2,
      "flow_velocity_mps": 0.85,
      "temperature_c": 28.5,
      "air_pressure_hpa": 1011.2,
      "recorded_at": "2026-04-22T23:36:12Z"
    },
    "device_health": {
      "is_online": true,
      "battery_percent": 75,
      "signal_strength_dbm": -68,
      "last_maintenance": "2026-03-10",
      "firmware_version": "v1.0.2-esp32"
    },
    "thresholds": {
      "watch_m": 3.5,
      "advisory_m": 4.5,
      "warning_m": 5.0,
      "critical_m": 6.5
    }
  }
}
```

### 3. GET /api/v1/sensors/{sensor_id}/history

Response:

```json
{
  "status": "success",
  "sensor_id": "MR-KND-001",
  "from": "2026-04-21T00:00:00Z",
  "to": "2026-04-22T00:00:00Z",
  "interval": "1h",
  "count": 3,
  "data": [
    {
      "timestamp": "2026-04-21T00:00:00Z",
      "water_level_m": 2.15,
      "rainfall_mm": 0.0,
      "flow_velocity_mps": 0.45,
      "temperature_c": 24.5,
      "air_pressure_hpa": 1012.1
    },
    {
      "timestamp": "2026-04-21T01:00:00Z",
      "water_level_m": 2.18,
      "rainfall_mm": 0.2,
      "flow_velocity_mps": 0.48,
      "temperature_c": 24.2,
      "air_pressure_hpa": 1011.8
    },
    {
      "timestamp": "2026-04-21T02:00:00Z",
      "water_level_m": 2.22,
      "rainfall_mm": 0.5,
      "flow_velocity_mps": 0.52,
      "temperature_c": 24.0,
      "air_pressure_hpa": 1011.5
    }
  ],
  "statistics": {
    "max_water_level_m": 4.53,
    "min_water_level_m": 2.1,
    "avg_water_level_m": 2.85,
    "total_rainfall_mm": 45.2,
    "max_flow_velocity_mps": 1.12
  }
}
```

### 4. GET /api/v1/zones

Response:

```json
{
  "status": "success",
  "timestamp": "2026-04-23T21:24:00Z",
  "count": 1,
  "data": [
    {
      "zone_id": "ZONE-4",
      "zone_name": "Kolonnawa Basin",
      "description": "Lower Mahaweli region near Peradeniya",
      "risk_level": "HIGH",
      "risk_score": 78.4,
      "color_code": "#F97316",
      "population_at_risk": 45200,
      "sensors_in_zone": ["KR-001", "KR-002", "KR-003"],
      "active_alerts": 2,
      "last_updated": "2026-04-23T21:20:00Z",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [79.85, 6.91],
            [79.87, 6.91],
            [79.87, 6.94],
            [79.85, 6.94],
            [79.85, 6.91]
          ]
        ]
      },
      "current_conditions": {
        "avg_water_level_m": 3.2,
        "max_water_level_m": 3.8,
        "avg_flow_velocity_mps": 0.95,
        "total_rainfall_mm": 145.2,
        "trend": "RISING"
      }
    }
  ]
}
```

### 5. GET /api/v1/zones/{zone_id}

Response:

```json
{
  "status": "success",
  "data": {
    "zone_id": "ZONE-K1",
    "zone_name": "Getambe Basin",
    "description": "Lower Mahaweli region near Peradeniya",
    "risk_level": "HIGH",
    "risk_score": 78.4,
    "color_code": "#F97316",
    "geometry": {
      "type": "Polygon",
      "coordinates": [
        [
          [80.61, 7.27],
          [80.62, 7.27],
          [80.62, 7.28],
          [80.61, 7.28],
          [80.61, 7.27]
        ]
      ]
    },
    "prediction": {
      "flood_probability_percent": 82.3,
      "predicted_peak_level_m": 4.8,
      "estimated_flood_time": "2026-04-25T23:45:00Z",
      "confidence_percent": 87.1,
      "model_version": "v3.2.1-xgboost"
    },
    "current_conditions": {
      "avg_water_level_m": 3.2,
      "max_water_level_m": 3.8,
      "avg_flow_velocity_mps": 0.95,
      "total_rainfall_mm": 145.2,
      "trend": "RISING"
    },
    "population_at_risk": 20500,
    "shelters": [
      {
        "shelter_id": "SH-K001",
        "name": "Getambe Temple Hall",
        "capacity": 400,
        "current_occupancy": 150,
        "lat": 7.2715,
        "lng": 80.6125,
        "distance_km": 0.8,
        "contact_number": "+94812222222"
      }
    ]
  }
}
```

### 6. GET /api/v1/predictions

Supported query parameters:

- `severity=HIGH,CRITICAL`
- `zone_id=ZONE-K1`
- `timeframe=next_24h`

Response:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "prediction_id": "PRED-KND-001",
      "zone_id": "ZONE-K1",
      "zone_name": "Getambe Basin",
      "created_at": "2026-04-25T19:30:00Z",
      "prediction_window": {
        "from": "2026-04-25T20:00:00Z",
        "to": "2026-04-26T08:00:00Z"
      },
      "flood_probability_percent": 82.3,
      "predicted_peak_level_m": 4.8,
      "estimated_flood_time": "2026-04-25T23:45:00Z",
      "severity": "HIGH",
      "confidence_percent": 87.1,
      "model_version": "XGB-v1.0",
      "top_risk_factors": [
        {
          "factor": "Upstream Water Level",
          "value": "3.9m",
          "impact": "High"
        },
        {
          "factor": "Rainfall (Last 6h)",
          "value": "145.2mm",
          "impact": "High"
        },
        {
          "factor": "Flow Velocity",
          "value": "0.95 m/s",
          "impact": "Medium"
        }
      ]
    }
  ]
}
```

### 7. GET /api/v1/alerts

Response:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "alert_id": "ALT-KND-001",
      "zone_id": "ZONE-K1",
      "zone_name": "Getambe Basin",
      "source_prediction_id": "PRED-KND-001",
      "severity": "HIGH",
      "severity_code": 3,
      "title": "Evacuation Warning: Getambe Lowlands",
      "message": "Water levels are rising rapidly. Please evacuate to the nearest designated shelter immediately.",
      "triggered_at": "2026-04-25T20:00:00Z",
      "triggered_by": "XGBOOST_AUTOMATED",
      "status": "ACTIVE",
      "resolved_at": null,
      "affected_population": 12500,
      "recommended_action": "EVACUATE",
      "recommended_shelters": [
        {
          "shelter_id": "SH-K001",
          "name": "Getambe Temple Hall",
          "lat": 7.2715,
          "lng": 80.6125
        }
      ],
      "notifications_sent": {
        "push": 1200,
        "sms": 800,
        "email": 50
      }
    }
  ]
}
```

### 8. GET /api/v1/anomalies

Supported query parameters:

- `status=UNRESOLVED`
- `sensor_id=MR-KND-001`

Response:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "anomaly_id": "ANM-KND-042",
      "sensor_id": "MR-KND-001",
      "detected_at": "2026-04-25T20:45:00Z",
      "type": "SUDDEN_SPIKE",
      "description": "Water level rose 0.8m in 10 mins without corresponding rainfall.",
      "severity": "HIGH",
      "anomaly_score": 0.94,
      "reading_at_detection": {
        "water_level_m": 4.2,
        "rate_of_change_m_per_hr": 4.8
      },
      "expected_range": {
        "min_m": 1.5,
        "max_m": 2.8
      },
      "status": "UNRESOLVED",
      "auto_alert_triggered": true,
      "alert_id": "ALT-KND-001"
    }
  ]
}
```

## Admin Endpoints

### 9. POST /api/v1/admin/sensors

Request body:

```json
{
  "sensor_id": "MR-KND-003",
  "name": "Mahaweli River — Katugastota",
  "location": {
    "lat": 7.2721,
    "lng": 80.6132,
    "zone_id": "ZONE-K1",
    "address": "Under Getambe Bridge, Peradeniya Road, Kandy"
  },
  "installed_date": "2026-04-22",
  "firmware_version": "v1.0.0",
  "thresholds": {
    "watch_m": 3.0,
    "advisory_m": 4.0,
    "warning_m": 5.0,
    "critical_m": 6.0
  }
}
```

### 10. PATCH /api/v1/admin/sensors/{sensor_id}

Request body:

```json
{
  "device_health": {
    "last_maintenance": "2026-04-22",
    "firmware_version": "v1.0.3-esp32"
  },
  "thresholds": {
    "warning_m": 5.2,
    "critical_m": 6.8
  },
  "justification": "Revised thresholds due to increased siltation at the riverbed"
}
```

### 11. DELETE /api/v1/admin/sensors/{sensor_id}

Response:

```json
{
  "status": "success",
  "message": "Sensor MR-KND-001 has been successfully deactivated.",
  "deactivated_at": "2026-04-22T23:45:00Z",
  "note": "Historical data preserved for XGBoost model training and audit."
}
```

### 12. POST /api/v1/admin/zones

Request body:

```json
{
  "zone_id": "ZONE-K1",
  "zone_name": "Getambe Basin",
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [80.61, 7.27],
        [80.62, 7.27],
        [80.62, 7.28],
        [80.61, 7.27]
      ]
    ]
  },
  "population_at_risk": 20500,
  "description": "Lower Mahaweli region near Peradeniya"
}
```

### 13. PATCH /api/v1/admin/zones/{zone_id}

Request body:

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [80.611, 7.271],
        [80.621, 7.271],
        [80.621, 7.281],
        [80.611, 7.271]
      ]
    ]
  }
}
```

### 14. DELETE /api/v1/admin/zones/{zone_id}

Response:

```json
{
  "status": "success",
  "message": "Zone ZONE-K1 deactivated. All historical sensor links preserved for audit."
}
```

### 15. POST /api/v1/admin/shelters

Request body:

```json
{
  "zone_id": "ZONE-K1",
  "name": "Getambe Temple Hall",
  "lat": 7.2715,
  "lng": 80.6125,
  "capacity": 400,
  "contact_number": "+94812222222",
  "status": "OPEN"
}
```

### 16. PATCH /api/v1/admin/shelters/{shelter_id}

Request body:

```json
{
  "current_occupancy": 310,
  "status": "FULL"
}
```

### 17. DELETE /api/v1/admin/shelters/{shelter_id}

Response:

```json
{
  "status": "success",
  "message": "Shelter SH-K001 has been removed from the registry. Historical data preserved for audit."
}
```

### 18. PATCH /api/v1/admin/anomalies/{anomaly_id}

Request body:

```json
{
  "status": "RESOLVED",
  "resolution_note": "Sensor cleared of debris. Data flow back to normal.",
  "resolved_by": "TECH-04"
}
```

## Zone-scoped Endpoints

### 19. GET /api/v1/zones/{zone_id}/sensors

Returns all sensors belonging to a specific zone.

Response:

```json
{
  "status": "success",
  "timestamp": "2026-04-22T23:05:00Z",
  "zone_id": "ZONE-K1",
  "zone_name": "Getambe Basin",
  "count": 2,
  "data": [
    {
      "sensor_id": "MR-KND-001",
      "name": "Mahaweli River — Getambe Bridge",
      "location": {
        "lat": 7.2721,
        "lng": 80.6132,
        "zone_id": "ZONE-K1",
        "zone_name": "Getambe Basin"
      },
      "readings": {
        "water_level_m": 4.53,
        "rainfall_mm_per_hr": 8.2,
        "flow_velocity_mps": 0.85,
        "temperature_c": 28.5,
        "air_pressure_hpa": 1011.2
      },
      "status": {
        "device_online": true,
        "battery_percent": 75,
        "signal_strength_dbm": -68,
        "last_seen": "2026-04-22T23:04:12Z"
      },
      "thresholds": {
        "water_level_warning_m": 5.0,
        "water_level_critical_m": 6.5
      }
    },
    {
      "sensor_id": "MR-KND-002",
      "name": "Mahaweli River — Peradeniya",
      "location": {
        "lat": 7.252,
        "lng": 80.5921,
        "zone_id": "ZONE-K1",
        "zone_name": "Getambe Basin"
      },
      "readings": {
        "water_level_m": 2.1,
        "rainfall_mm_per_hr": 0.0,
        "flow_velocity_mps": 0.42,
        "temperature_c": 27.8,
        "air_pressure_hpa": 1012.5
      },
      "status": {
        "device_online": true,
        "battery_percent": 92,
        "signal_strength_dbm": -55,
        "last_seen": "2026-04-22T23:00:05Z"
      },
      "thresholds": {
        "water_level_warning_m": 3.5,
        "water_level_critical_m": 5.0
      }
    }
  ]
}
```

### 20. GET /api/v1/zones/{zone_id}/alerts

Supported query parameters:

- `status=ACTIVE`
- `severity=HIGH,CRITICAL`

Response:

```json
{
  "status": "success",
  "zone_id": "ZONE-K1",
  "zone_name": "Getambe Basin",
  "count": 1,
  "data": [
    {
      "alert_id": "ALT-KND-001",
      "zone_id": "ZONE-K1",
      "zone_name": "Getambe Basin",
      "source_prediction_id": "PRED-KND-001",
      "severity": "HIGH",
      "severity_code": 3,
      "title": "Evacuation Warning: Getambe Lowlands",
      "message": "Water levels are rising rapidly. Please evacuate to the nearest designated shelter immediately.",
      "triggered_at": "2026-04-25T20:00:00Z",
      "triggered_by": "XGBOOST_AUTOMATED",
      "status": "ACTIVE",
      "resolved_at": null,
      "affected_population": 12500,
      "recommended_action": "EVACUATE",
      "recommended_shelters": [
        {
          "shelter_id": "SH-K001",
          "name": "Getambe Temple Hall",
          "lat": 7.2715,
          "lng": 80.6125
        }
      ],
      "notifications_sent": {
        "push": 1200,
        "sms": 800,
        "email": 50
      }
    }
  ]
}
```

### 21. GET /api/v1/zones/{zone_id}/predictions

Supported query parameters:

- `severity=HIGH,CRITICAL`
- `timeframe=next_24h`

Response:

```json
{
  "status": "success",
  "zone_id": "ZONE-K1",
  "zone_name": "Getambe Basin",
  "count": 1,
  "data": [
    {
      "prediction_id": "PRED-KND-001",
      "zone_id": "ZONE-K1",
      "zone_name": "Getambe Basin",
      "created_at": "2026-04-25T19:30:00Z",
      "prediction_window": {
        "from": "2026-04-25T20:00:00Z",
        "to": "2026-04-26T08:00:00Z"
      },
      "flood_probability_percent": 82.3,
      "predicted_peak_level_m": 4.8,
      "estimated_flood_time": "2026-04-25T23:45:00Z",
      "severity": "HIGH",
      "confidence_percent": 87.1,
      "model_version": "XGB-v1.0",
      "top_risk_factors": [
        {
          "factor": "Upstream Water Level",
          "value": "3.9m",
          "impact": "High"
        },
        {
          "factor": "Rainfall (Last 6h)",
          "value": "145.2mm",
          "impact": "High"
        },
        {
          "factor": "Flow Velocity",
          "value": "0.95 m/s",
          "impact": "Medium"
        }
      ]
    }
  ]
}
```

### 22. GET /api/v1/zones/{zone_id}/anomalies

Supported query parameters:

- `status=UNRESOLVED`
- `severity=HIGH`

Response:

```json
{
  "status": "success",
  "zone_id": "ZONE-K1",
  "zone_name": "Getambe Basin",
  "count": 1,
  "data": [
    {
      "anomaly_id": "ANM-KND-042",
      "sensor_id": "MR-KND-001",
      "zone_id": "ZONE-K1",
      "detected_at": "2026-04-25T20:45:00Z",
      "type": "SUDDEN_SPIKE",
      "description": "Water level rose 0.8m in 10 mins without corresponding rainfall.",
      "severity": "HIGH",
      "anomaly_score": 0.94,
      "reading_at_detection": {
        "water_level_m": 4.2,
        "rate_of_change_m_per_hr": 4.8
      },
      "expected_range": {
        "min_m": 1.5,
        "max_m": 2.8
      },
      "status": "UNRESOLVED",
      "auto_alert_triggered": true,
      "alert_id": "ALT-KND-001"
    }
  ]
}
```

## Notes

- The API gateway base path remains `/api/v1` for all frontend requests.
- The spec now includes both the existing public/admin routes and the new zone-scoped endpoints.
- If backend implementation is needed for the new zone-scoped endpoints, those routes should be added in the appropriate router(s) with matching response schemas.
