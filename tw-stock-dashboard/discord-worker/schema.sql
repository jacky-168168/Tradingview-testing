CREATE TABLE IF NOT EXISTS discord_cursor (
 channel_id TEXT PRIMARY KEY NOT NULL,
 last_message_id TEXT NOT NULL DEFAULT '0',
 last_checked_ms INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',
 last_inserted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS discord_signals (
 id TEXT PRIMARY KEY NOT NULL,
 discord_message_id TEXT NOT NULL,
 channel_id TEXT NOT NULL,
 source TEXT NOT NULL,
 symbol TEXT NOT NULL,
 signal TEXT NOT NULL CHECK (signal IN ('BOTTOM','TOP')),
 variant TEXT NOT NULL CHECK (variant IN ('SS','NORMAL')),
 price REAL NOT NULL CHECK (price > 0),
 timeframe TEXT,
 time_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discord_time ON discord_signals(time_ms DESC);
CREATE INDEX IF NOT EXISTS idx_discord_symbol_time ON discord_signals(symbol,time_ms DESC);
CREATE INDEX IF NOT EXISTS idx_discord_channel ON discord_signals(channel_id,discord_message_id);
