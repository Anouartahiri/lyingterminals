-- Daily aggregate counters only. No IPs, user agents or per-visitor data.
CREATE TABLE IF NOT EXISTS counts (
  day  TEXT NOT NULL,      -- UTC date, YYYY-MM-DD
  kind TEXT NOT NULL,      -- visits | ref | cc | hits | theme
  k    TEXT NOT NULL,      -- 'all', referrer host, country code or theme key
  n    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, kind, k)
);
