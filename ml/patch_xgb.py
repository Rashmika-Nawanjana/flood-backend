import re

with open("ml/predict_xgb.py", "r") as f:
    content = f.read()

kafka_code = """
def publish_prediction_events(predictions_df, args):
    try:
        from kafka import KafkaProducer
        from datetime import datetime, timezone
        import json
        
        producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Example of publishing prediction:new for the latest prediction
        latest = predictions_df.iloc[-1]
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        event = {
            "event": "prediction:new",
            "timestamp": timestamp,
            "data": {
                "prediction_id": f"PRED-ML-{int(datetime.now().timestamp())}",
                "zone_id": "ZONE-K1",
                "predicted_peak_level_m": float(latest.get("y_pred_t_plus_5", 0.0)),
                "estimated_flood_time": timestamp, # Should be calculated based on horizon
                "severity": "HIGH" if float(latest.get("y_pred_t_plus_5", 0)) > 4.5 else "NORMAL",
                "top_risk_factors": [
                    {"factor": "XGBoost Evaluation", "value": "Completed", "impact": "High"}
                ]
            }
        }
        producer.send("analytics.predictions", event)
        
        if event["data"]["severity"] == "HIGH":
            alert_event = {
                "event": "alert:new",
                "timestamp": timestamp,
                "data": {
                    "alert_id": f"ALT-ML-{int(datetime.now().timestamp())}",
                    "zone_id": "ZONE-K1",
                    "severity": "HIGH",
                    "title": "Evacuation Warning: Automated ML Alert",
                    "message": "Water levels predicted to rise rapidly.",
                    "recommended_action": "EVACUATE",
                    "recommended_shelters": [
                        {"shelter_id": "SH-K001", "name": "Getambe Temple Hall", "lat": 7.2715, "lng": 80.6125}
                    ]
                }
            }
            producer.send("system.alerts", alert_event)
            
            risk_event = {
                "event": "zone:risk:update",
                "timestamp": timestamp,
                "data": {
                    "zone_id": "ZONE-K1",
                    "zone_name": "Getambe Basin",
                    "previous_level": "WARNING",
                    "current_level": "HIGH",
                    "risk_score": 85.0,
                    "color_code": "#F97316"
                }
            }
            producer.send("analytics.predictions", risk_event)
            
        producer.flush()
        print("Successfully published ML events to Kafka.")
    except Exception as e:
        print(f"Failed to publish to Kafka: {e}")

"""

# Insert kafka_code before main()
insert_idx = content.find("def main():")
if insert_idx != -1:
    new_content = content[:insert_idx] + kafka_code + "\n" + content[insert_idx:]
    
    # inject call inside main() before print("Predictions saved to:")
    inject_str = "    publish_prediction_events(predictions, args)\n\n"
    inject_idx = new_content.rfind('print(f"Predictions saved to: {output_path}")')
    
    final_content = new_content[:inject_idx] + inject_str + new_content[inject_idx:]
    
    with open("ml/predict_xgb.py", "w") as f:
        f.write(final_content)
        print("Updated ML script.")
