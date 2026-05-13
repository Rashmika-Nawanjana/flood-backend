// =============================================
// FloodSense LK — Officer Namespace
// Path: /officer
//
// • JWT required (role: officer)
// • zone_id extracted from JWT (public_metadata)
// • Auto-joins zone:<zone_id> room on connect
// • Receives ALL 7 events but only for own zone
// =============================================

const { authMiddleware } = require('../auth');

/**
 * Register the officer namespace on a Socket.IO server.
 *
 * @param {import('socket.io').Server} io
 * @returns {import('socket.io').Namespace}
 */
function registerOfficerNamespace(io) {
  const nsp = io.of('/officer');

  // ── Auth middleware: only role=officer ──────────────
  nsp.use(authMiddleware(['officer']));

  // ── Post-auth: enforce zone_id presence ────────────
  nsp.use((socket, next) => {
    const user = socket.data.user;
    if (!user.zone_id) {
      return next(
        new Error('Officer account is not assigned to a zone (missing zone_id in JWT claims)')
      );
    }
    next();
  });

  // ── Connection handler ─────────────────────────────
  nsp.on('connection', (socket) => {
    const user = socket.data.user;
    const zoneId = user.zone_id;

    // Auto-join the officer's assigned zone room
    socket.join(`zone:${zoneId}`);

    console.log(
      `[Officer] Connected: ${socket.id} (user: ${user.user_id}, zone: ${zoneId})`
    );

    // Officers can also subscribe to specific sensors within their zone
    socket.on('subscribe:sensor', (sensorId) => {
      if (typeof sensorId !== 'string' || !sensorId.trim()) return;
      socket.join(`sensor:${sensorId}`);
      console.log(`[Officer] ${socket.id} joined room sensor:${sensorId}`);
    });

    socket.on('unsubscribe:sensor', (sensorId) => {
      if (typeof sensorId !== 'string' || !sensorId.trim()) return;
      socket.leave(`sensor:${sensorId}`);
      console.log(`[Officer] ${socket.id} left room sensor:${sensorId}`);
    });

    // ── Disconnect ───────────────────────────────────
    socket.on('disconnect', (reason) => {
      console.log(
        `[Officer] Disconnected: ${socket.id} (${reason}) — ${nsp.sockets.size} remaining`
      );
    });
  });

  console.log('[Officer] Namespace registered at /officer');
  return nsp;
}

module.exports = { registerOfficerNamespace };
