-- Migrates from version 1 to version 2

ALTER TABLE user_registration ADD COLUMN subscription_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE user_registration ADD COLUMN registered_at DATETIME;

DROP TABLE vaccination_center_by_type;
DROP TABLE available_day;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY
);
INSERT INTO schema_version VALUES (2);
