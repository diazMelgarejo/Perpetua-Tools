CREATE TABLE IF NOT EXISTS prompt_records (
  owner_id TEXT NOT NULL,
  id TEXT NOT NULL,
  request_key TEXT NOT NULL,
  original TEXT NOT NULL,
  improved TEXT NOT NULL,
  mode TEXT NOT NULL,
  version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0, 1)),
  PRIMARY KEY(owner_id, id),
  UNIQUE(owner_id, request_key)
);
CREATE INDEX IF NOT EXISTS prompt_records_owner_history ON prompt_records(owner_id, archived, created_at, id);
