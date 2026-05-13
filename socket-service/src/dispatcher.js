// =============================================
// FloodSense LK — Event Dispatcher
// Central fan-out: receives events from Kafka and
// routes them to the correct namespace + room.
//
// Access Matrix:
//   Admin   → all 7 events, all zones (broadcast)
//   Officer → all 7 events, own zone only (room)
//   Public  → 3 events only, GPS zone only (room)
// =============================================

// Events the public namespace is allowed to receive
const PUBLIC_EVENTS = new Set([
  'zone:risk:update',
  'alert:new',
  'alert:resolved',
]);

// ── Namespace references (set during init) ───────────
let adminNsp = null;
let officerNsp = null;
let publicNsp = null;

/**
 * Initialise the dispatcher with Socket.IO namespace references.
 *
 * @param {{ admin: Namespace, officer: Namespace, public: Namespace }} namespaces
 */
function initDispatcher(namespaces) {
  adminNsp = namespaces.admin;
  officerNsp = namespaces.officer;
  publicNsp = namespaces.public;
  console.log('[Dispatcher] Initialised with 3 namespaces');
}

/**
 * Dispatch an event from Kafka to the correct namespaces.
 * Called by the Kafka consumer for every incoming message.
 *
 * @param {string} eventName — Socket.IO event name (e.g. 'sensor:update')
 * @param {object} payload   — The full event payload
 * @param {string|null} zoneId — Zone the event relates to (if any)
 */
function dispatch(eventName, payload, zoneId) {
  // ── Admin: broadcast ALL events to ALL connected admins ──
  if (adminNsp) {
    adminNsp.emit(eventName, payload);
  }

  // ── Officer: emit ALL events, but only to the matching zone room ──
  if (officerNsp && zoneId) {
    officerNsp.to(`zone:${zoneId}`).emit(eventName, payload);
  }

  // ── Public: emit only 3 allowed events, to matching zone room ──
  if (publicNsp && PUBLIC_EVENTS.has(eventName) && zoneId) {
    publicNsp.to(`zone:${zoneId}`).emit(eventName, payload);
  }
}

module.exports = { initDispatcher, dispatch, PUBLIC_EVENTS };
