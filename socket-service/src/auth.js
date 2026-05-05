// =============================================
// FloodSense LK — Clerk JWT Verification
// Validates RS256 JWTs using Clerk's JWKS endpoint.
// Used as Socket.IO middleware for admin & officer.
// =============================================

const { createRemoteJWKSet, jwtVerify } = require('jose');
const config = require('./config');

// ── JWKS Key Set (cached by jose) ────────────────────
let jwks = null;

function getJWKS() {
  if (!jwks && config.clerkJwksUrl) {
    jwks = createRemoteJWKSet(new URL(config.clerkJwksUrl));
  }
  return jwks;
}

/**
 * Verify a Clerk-issued JWT and extract user claims.
 *
 * @param {string} token  — Raw Bearer token
 * @returns {Promise<{ user_id: string, role: string, zone_id: string|null }>}
 */
async function verifyClerkJWT(token) {
  const keySet = getJWKS();
  if (!keySet) {
    throw new Error('CLERK_JWKS_URL is not configured');
  }

  const verifyOptions = { algorithms: ['RS256'] };

  // Only enforce issuer if configured
  if (config.clerkIssuer) {
    verifyOptions.issuer = config.clerkIssuer;
  }

  const { payload } = await jwtVerify(token, keySet, verifyOptions);

  // Clerk stores custom data in public_metadata
  const publicMetadata = payload.public_metadata || payload.publicMetadata || {};
  const role = publicMetadata.role || 'citizen';
  const zoneId = publicMetadata.zone_id || null;

  return {
    user_id: payload.sub,
    username: payload.username || payload.email || '',
    email: payload.email || '',
    role,
    zone_id: zoneId,
  };
}

/**
 * Socket.IO middleware factory — authenticates a connection
 * and attaches user data to `socket.data.user`.
 *
 * @param {string[]} allowedRoles — Roles permitted on this namespace
 * @returns {Function} Socket.IO middleware (socket, next)
 */
function authMiddleware(allowedRoles) {
  return async (socket, next) => {
    try {
      // Token can come from auth header or handshake query
      const token =
        socket.handshake.auth?.token ||
        socket.handshake.headers?.authorization?.replace('Bearer ', '') ||
        socket.handshake.query?.token;

      if (!token) {
        return next(new Error('Authentication required: no token provided'));
      }

      const user = await verifyClerkJWT(token);

      // Enforce role
      if (!allowedRoles.includes(user.role)) {
        return next(
          new Error(`Access denied: role '${user.role}' is not permitted on this namespace`)
        );
      }

      // Attach user info to socket
      socket.data.user = user;
      next();
    } catch (err) {
      console.error(`[Auth] JWT verification failed: ${err.message}`);
      next(new Error(`Authentication failed: ${err.message}`));
    }
  };
}

module.exports = { verifyClerkJWT, authMiddleware };
