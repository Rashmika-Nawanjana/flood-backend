-- Add zone_id foreign key to users table
-- Links users to their assigned zone(s)

ALTER TABLE users ADD COLUMN IF NOT EXISTS zone_id VARCHAR(64) REFERENCES zones(zone_id) ON DELETE SET NULL;

-- Create index for zone_id lookups
CREATE INDEX IF NOT EXISTS idx_users_zone_id ON users(zone_id);
