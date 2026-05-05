// =============================================
// FloodSense LK — Zone Resolver
// Resolves GPS coordinates → zone_id using cached
// zone polygons fetched from the zone-service API.
// Uses ray-casting point-in-polygon algorithm.
// =============================================

const config = require('./config');

// ── In-memory zone cache ─────────────────────────────
let zoneCache = [];       // [{ zone_id, zone_name, polygon }]
let lastFetchedAt = null;
let fetchTimer = null;

/**
 * Fetch all zones from the zone-service and cache their polygons.
 */
async function refreshZoneCache() {
  try {
    const url = `${config.zoneServiceUrl}/api/v1/zones`;
    console.log(`[ZoneResolver] Fetching zone polygons from ${url}...`);

    const response = await fetch(url, {
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      throw new Error(`Zone service returned ${response.status}`);
    }

    const body = await response.json();
    const zones = body.data || [];

    zoneCache = zones
      .filter((z) => z.geometry && z.geometry.coordinates)
      .map((z) => ({
        zone_id: z.zone_id,
        zone_name: z.zone_name,
        // GeoJSON Polygon: coordinates[0] is the outer ring
        polygon: z.geometry.coordinates[0],
      }));

    lastFetchedAt = new Date();
    console.log(
      `[ZoneResolver] Cached ${zoneCache.length} zone polygons (${lastFetchedAt.toISOString()})`
    );
  } catch (err) {
    console.error(`[ZoneResolver] Failed to refresh zone cache: ${err.message}`);
    // Keep using stale cache if available
  }
}

/**
 * Start the periodic zone cache refresh.
 */
function startZoneRefresh() {
  // Initial fetch
  refreshZoneCache();

  // Periodic refresh
  fetchTimer = setInterval(refreshZoneCache, config.zoneRefreshIntervalMs);

  // Don't block process exit
  if (fetchTimer.unref) fetchTimer.unref();
}

/**
 * Stop the periodic zone cache refresh.
 */
function stopZoneRefresh() {
  if (fetchTimer) {
    clearInterval(fetchTimer);
    fetchTimer = null;
  }
}

// ── Ray-Casting Point-in-Polygon ─────────────────────
// GeoJSON uses [lng, lat] ordering in coordinates

/**
 * Determine if a point is inside a polygon using the
 * ray-casting (even-odd rule) algorithm.
 *
 * @param {number} lat  — Latitude of the point
 * @param {number} lng  — Longitude of the point
 * @param {number[][]} polygon — Array of [lng, lat] coordinate pairs
 * @returns {boolean}
 */
function pointInPolygon(lat, lng, polygon) {
  let inside = false;
  const n = polygon.length;

  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [xi, yi] = [polygon[i][0], polygon[i][1]]; // [lng, lat]
    const [xj, yj] = [polygon[j][0], polygon[j][1]];

    // yi/yj = lat of polygon vertex, xi/xj = lng of polygon vertex
    const intersect =
      yi > lat !== yj > lat &&
      lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;

    if (intersect) inside = !inside;
  }

  return inside;
}

/**
 * Resolve GPS coordinates to a zone.
 *
 * @param {number} lat — Latitude
 * @param {number} lng — Longitude
 * @returns {{ zone_id: string, zone_name: string } | null}
 */
function resolveZone(lat, lng) {
  for (const zone of zoneCache) {
    if (pointInPolygon(lat, lng, zone.polygon)) {
      return { zone_id: zone.zone_id, zone_name: zone.zone_name };
    }
  }
  return null;
}

/**
 * Get current cache status (for health checks / debugging).
 */
function getCacheStatus() {
  return {
    cachedZones: zoneCache.length,
    lastFetchedAt: lastFetchedAt ? lastFetchedAt.toISOString() : null,
  };
}

module.exports = {
  startZoneRefresh,
  stopZoneRefresh,
  refreshZoneCache,
  resolveZone,
  getCacheStatus,
};
