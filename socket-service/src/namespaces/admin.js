// =============================================
// FloodSense LK — Admin Namespace
// Path: /admin
//
// • JWT required (role: admin)
// • Receives ALL 7 events for ALL zones
// • Can subscribe to specific zone/sensor rooms
// =============================================

const { authMiddleware } = require('../auth');

/**
 * Register the admin namespace on a Socket.IO server.
 *
 * @param {import('socket.io').Server} io
 * @returns {import('socket.io').Namespace}
 */
function registerAdminNamespace(io) {
  const nsp = io.of('/admin');

  // ── Auth middleware: only role=admin ────────────────
  nsp.use(authMiddleware(['admin']));

  // ── Connection handler ─────────────────────────────
  nsp.on('connection', (socket) => {
    const user = socket.data.user;
    console.log(
      `[Admin] Connected: ${socket.id} (user: ${user.user_id}, role: ${user.role})`
    );

    // ── Optional room subscriptions ──────────────────
    socket.on('subscribe:zone', (zoneId) => {
      if (typeof zoneId !== 'string' || !zoneId.trim()) return;
      socket.join(`zone:${zoneId}`);
      console.log(`[Admin] ${socket.id} joined room zone:${zoneId}`);
    });

    socket.on('unsubscribe:zone', (zoneId) => {
      if (typeof zoneId !== 'string' || !zoneId.trim()) return;
      socket.leave(`zone:${zoneId}`);
      console.log(`[Admin] ${socket.id} left room zone:${zoneId}`);
    });

    socket.on('subscribe:sensor', (sensorId) => {
      if (typeof sensorId !== 'string' || !sensorId.trim()) return;
      socket.join(`sensor:${sensorId}`);
      console.log(`[Admin] ${socket.id} joined room sensor:${sensorId}`);
    });

    socket.on('unsubscribe:sensor', (sensorId) => {
      if (typeof sensorId !== 'string' || !sensorId.trim()) return;
      socket.leave(`sensor:${sensorId}`);
      console.log(`[Admin] ${socket.id} left room sensor:${sensorId}`);
    });

    // ── Disconnect ───────────────────────────────────
    socket.on('disconnect', (reason) => {
      console.log(
        `[Admin] Disconnected: ${socket.id} (${reason}) — ${nsp.sockets.size} remaining`
      );
    });
  });

  console.log('[Admin] Namespace registered at /admin');
  return nsp;
}

module.exports = { registerAdminNamespace };
