// =============================================
// FloodSense LK — Socket.IO Real-Time Server
// Entry point: wires up HTTP, Socket.IO, namespaces,
// Kafka consumer, dispatcher, and zone resolver.
//
// Listens on: http://localhost:3001 (path: /ws/live)
// Namespaces: /admin, /officer, /public
// =============================================

const http = require('http');
const { Server } = require('socket.io');
const config = require('./config');

// ── Modules ──────────────────────────────────────────
const { registerAdminNamespace } = require('./namespaces/admin');
const { registerOfficerNamespace } = require('./namespaces/officer');
const { registerPublicNamespace } = require('./namespaces/public');
const { initDispatcher, dispatch } = require('./dispatcher');
const { startKafkaConsumer, stopKafkaConsumer } = require('./kafka');
const { startZoneRefresh, stopZoneRefresh, getCacheStatus } = require('./zone-resolver');

// ── HTTP Server ──────────────────────────────────────
const server = http.createServer((req, res) => {
  // Health check endpoint
  if (req.url === '/health') {
    const zoneStatus = getCacheStatus();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify({
        status: 'ok',
        service: 'flood-socket',
        uptime: process.uptime(),
        namespaces: ['/admin', '/officer', '/public'],
        zone_cache: zoneStatus,
      })
    );
    return;
  }

  res.writeHead(404);
  res.end();
});

// ── Socket.IO Server ────────────────────────────────
const io = new Server(server, {
  path: config.socketPath,
  cors: {
    origin: config.corsOrigin.split(',').map((o) => o.trim()),
    methods: ['GET', 'POST'],
    credentials: true,
  },
  transports: ['websocket', 'polling'],
  pingInterval: 25000,
  pingTimeout: 20000,
});

// ── Register Namespaces ──────────────────────────────
const adminNsp = registerAdminNamespace(io);
const officerNsp = registerOfficerNamespace(io);
const publicNsp = registerPublicNamespace(io);

// ── Initialise Dispatcher ────────────────────────────
initDispatcher({
  admin: adminNsp,
  officer: officerNsp,
  public: publicNsp,
});

// ── Start Zone Resolver ──────────────────────────────
startZoneRefresh();

// ── Start Kafka Consumer ─────────────────────────────
startKafkaConsumer(dispatch);

// ── Start Server ─────────────────────────────────────
server.listen(config.port, () => {
  console.log('');
  console.log('  ╔══════════════════════════════════════════════════╗');
  console.log('  ║    FloodSense LK — Socket.IO Real-Time Server   ║');
  console.log('  ╠══════════════════════════════════════════════════╣');
  console.log(`  ║  URL:        http://localhost:${config.port}              ║`);
  console.log(`  ║  Path:       ${config.socketPath.padEnd(36)}║`);
  console.log(`  ║  CORS:       ${config.corsOrigin.substring(0, 36).padEnd(36)}║`);
  console.log('  ║  Namespaces: /admin, /officer, /public          ║');
  console.log('  ╚══════════════════════════════════════════════════╝');
  console.log('');
});

// ── Graceful Shutdown ────────────────────────────────
function shutdown(signal) {
  console.log(`\n[Server] ${signal} received — shutting down...`);

  stopKafkaConsumer();
  stopZoneRefresh();

  io.close(() => {
    console.log('[Server] Socket.IO closed');
    server.close(() => {
      console.log('[Server] HTTP server closed');
      process.exit(0);
    });
  });

  // Force exit after 5 seconds
  setTimeout(() => {
    console.error('[Server] Forced exit after timeout');
    process.exit(1);
  }, 5000);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
