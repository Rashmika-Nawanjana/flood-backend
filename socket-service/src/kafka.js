// =============================================
// FloodSense LK — Kafka WebSocket Consumer
// Connects to the mock Kafka broker via WebSocket,
// subscribes to all 7 topics, and forwards messages
// to the dispatcher for namespace-based fan-out.
// =============================================

const WebSocket = require('ws');
const config = require('./config');

// ── Kafka Topic → Socket.IO Event Mapping ────────────
const TOPIC_EVENT_MAP = {
  'sensor-updates': 'sensor:update',
  'zone-risk-updates': 'zone:risk:update',
  'predictions': 'prediction:new',
  'alerts-new': 'alert:new',
  'alerts-resolved': 'alert:resolved',
  'sensor-offline': 'sensor:offline',
  'anomalies': 'anomaly:new',
};

const ALL_TOPICS = Object.keys(TOPIC_EVENT_MAP);

// ── State ────────────────────────────────────────────
let kafkaWs = null;
let dispatcher = null;
let reconnectTimer = null;
let isShuttingDown = false;
let reconnectAttempts = 0;

/**
 * Start consuming from the mock Kafka broker.
 *
 * @param {Function} dispatchFn — callback(eventName, payload) from dispatcher
 */
function startKafkaConsumer(dispatchFn) {
  dispatcher = dispatchFn;
  isShuttingDown = false;
  reconnectAttempts = 0;

  // Skip Kafka entirely if URL is not configured
  if (!config.kafkaUrl) {
    console.log('[Kafka] No KAFKA_URL configured — running without Kafka');
    return;
  }

  connect();
}

/**
 * Stop the Kafka consumer and clean up.
 */
function stopKafkaConsumer() {
  isShuttingDown = true;

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (kafkaWs) {
    kafkaWs.removeAllListeners();
    kafkaWs.close();
    kafkaWs = null;
  }
}

// ── Internal: Connect to Kafka ───────────────────────
function connect() {
  if (isShuttingDown) return;

  // Only log the first 3 connection attempts
  if (reconnectAttempts < 3) {
    console.log(`[Kafka] Connecting to broker at ${config.kafkaUrl}...`);
  }

  kafkaWs = new WebSocket(config.kafkaUrl, {
    headers: { 'x-client-id': 'socketio-server' },
  });

  kafkaWs.on('open', () => {
    console.log('[Kafka] Connected to broker');
    reconnectAttempts = 0; // Reset on successful connection
    kafkaWs.send(
      JSON.stringify({
        action: 'subscribe',
        topics: ALL_TOPICS,
      })
    );
    console.log(`[Kafka] Subscribed to ${ALL_TOPICS.length} topics: ${ALL_TOPICS.join(', ')}`);
  });

  kafkaWs.on('message', (raw) => {
    let data;
    try {
      data = JSON.parse(raw.toString());
    } catch {
      return; // Ignore malformed messages
    }

    // Ignore non-message payloads (e.g. subscription confirmations)
    if (!data.topic || !data.message) return;

    const eventName = TOPIC_EVENT_MAP[data.topic];
    if (!eventName) return;

    const payload = data.message;

    // Extract zone_id from the payload (most events have it at top level)
    const zoneId = payload.zone_id || payload.data?.zone_id || null;

    // Forward to dispatcher
    if (dispatcher) {
      dispatcher(eventName, payload, zoneId);
    }
  });

  kafkaWs.on('close', () => {
    if (isShuttingDown) return;
    reconnectAttempts++;
    // Exponential backoff: 3s → 6s → 12s → 24s → cap at 30s
    const delay = Math.min(3000 * Math.pow(2, reconnectAttempts - 1), 30000);
    if (reconnectAttempts <= 3) {
      console.warn(`[Kafka] Connection lost. Retry #${reconnectAttempts} in ${delay / 1000}s...`);
    } else if (reconnectAttempts === 4) {
      console.warn('[Kafka] Broker unavailable — retrying silently in background...');
    }
    scheduleReconnect(delay);
  });

  kafkaWs.on('error', (err) => {
    // Only log first 3 errors to avoid spam
    if (reconnectAttempts < 3) {
      console.error(`[Kafka] Connection error: ${err.message}`);
    }
    // on('close') will fire after this, triggering reconnect
  });
}

function scheduleReconnect(delay = 3000) {
  if (isShuttingDown) return;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delay);
}

module.exports = {
  startKafkaConsumer,
  stopKafkaConsumer,
  TOPIC_EVENT_MAP,
  ALL_TOPICS,
};
