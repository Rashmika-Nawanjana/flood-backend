// =============================================
// FloodSense LK — Socket Service Configuration
// Centralised env-var access for all modules.
// =============================================

require('dotenv').config();

const config = {
  // ── Server ──────────────────────────────────────────
  port: parseInt(process.env.PORT || '3001', 10),
  socketPath: process.env.SOCKET_PATH || '/ws/live',
  corsOrigin: process.env.CORS_ORIGIN || 'http://localhost:3000',

  // ── Kafka (Mock WS Broker) ──────────────────────────
  kafkaUrl: process.env.KAFKA_URL || 'ws://127.0.0.1:19092',

  // ── Clerk Auth ──────────────────────────────────────
  clerkJwksUrl: process.env.CLERK_JWKS_URL || '',
  clerkIssuer: process.env.CLERK_ISSUER || '',

  // ── Zone Service (Internal) ─────────────────────────
  zoneServiceUrl: process.env.ZONE_SERVICE_URL || 'http://localhost:8004',

  // ── Zone Resolver ───────────────────────────────────
  zoneRefreshIntervalMs: parseInt(process.env.ZONE_REFRESH_INTERVAL_MS || '300000', 10), // 5 min
};

module.exports = config;
