// =============================================
// FloodSense LK — Public Namespace
// Path: /public
//
// • No authentication required
// • Receives only 4 events:
//     zone:risk:update, prediction:new,
//     alert:new, alert:resolved
// • Zone determined by client GPS via
//   subscribe:location { lat, lng }
// =============================================

const { resolveZone } = require('../zone-resolver');

/**
 * Register the public namespace on a Socket.IO server.
 *
 * @param {import('socket.io').Server} io
 * @returns {import('socket.io').Namespace}
 */
function registerPublicNamespace(io) {
  const nsp = io.of('/public');

  // No auth middleware — public access

  // ── Connection handler ─────────────────────────────
  nsp.on('connection', (socket) => {
    console.log(`[Public] Connected: ${socket.id}`);

    // Track the client's current zone for room management
    socket.data.currentZoneId = null;

    // ── GPS-based zone subscription ──────────────────
    // Frontend emits: socket.emit('subscribe:location', { lat: 7.27, lng: 80.61 })
    socket.on('subscribe:location', (location) => {
      if (!location || typeof location.lat !== 'number' || typeof location.lng !== 'number') {
        socket.emit('error:location', {
          message: 'Invalid location: expected { lat: number, lng: number }',
        });
        return;
      }

      const { lat, lng } = location;
      const zone = resolveZone(lat, lng);

      // Leave the previous zone room (if any)
      if (socket.data.currentZoneId) {
        socket.leave(`zone:${socket.data.currentZoneId}`);
        console.log(`[Public] ${socket.id} left zone:${socket.data.currentZoneId}`);
      }

      if (zone) {
        // Join the new zone room
        socket.join(`zone:${zone.zone_id}`);
        socket.data.currentZoneId = zone.zone_id;

        console.log(`[Public] ${socket.id} resolved GPS (${lat}, ${lng}) → ${zone.zone_id}`);

        // Acknowledge to the client
        socket.emit('location:resolved', {
          zone_id: zone.zone_id,
          zone_name: zone.zone_name,
          lat,
          lng,
        });
      } else {
        socket.data.currentZoneId = null;

        console.log(`[Public] ${socket.id} GPS (${lat}, ${lng}) → no matching zone`);

        socket.emit('location:resolved', {
          zone_id: null,
          zone_name: null,
          lat,
          lng,
          message: 'Your location is not within a monitored flood zone',
        });
      }
    });

    // ── Manual zone subscription (fallback) ──────────
    // In case frontend already knows the zone_id
    socket.on('subscribe:zone', (zoneId) => {
      if (typeof zoneId !== 'string' || !zoneId.trim()) return;

      // Leave the previous zone room
      if (socket.data.currentZoneId) {
        socket.leave(`zone:${socket.data.currentZoneId}`);
      }

      socket.join(`zone:${zoneId}`);
      socket.data.currentZoneId = zoneId;
      console.log(`[Public] ${socket.id} manually joined zone:${zoneId}`);
    });

    socket.on('unsubscribe:zone', () => {
      if (socket.data.currentZoneId) {
        socket.leave(`zone:${socket.data.currentZoneId}`);
        console.log(`[Public] ${socket.id} left zone:${socket.data.currentZoneId}`);
        socket.data.currentZoneId = null;
      }
    });

    // ── Disconnect ───────────────────────────────────
    socket.on('disconnect', (reason) => {
      console.log(
        `[Public] Disconnected: ${socket.id} (${reason}) — ${nsp.sockets.size} remaining`
      );
    });
  });

  console.log('[Public] Namespace registered at /public');
  return nsp;
}

module.exports = { registerPublicNamespace };
