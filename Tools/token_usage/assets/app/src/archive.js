'use strict';

const { DatabaseSync } = require('node:sqlite');
const { historyRow } = require('./public-data');

class HistoryArchive {
  constructor(filename) {
    this.db = new DatabaseSync(filename);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS history (
        user_id TEXT NOT NULL, device_id TEXT NOT NULL, kind TEXT NOT NULL,
        bucket TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY (user_id, device_id, kind, bucket)
      );`);
    this.upsert = this.db.prepare(`INSERT INTO history VALUES (?, ?, ?, ?, ?)
      ON CONFLICT (user_id, device_id, kind, bucket) DO UPDATE SET payload=excluded.payload
      WHERE payload != excluded.payload`);
  }

  capture(userId, devices) {
    this.db.exec('BEGIN');
    try {
      const active = new Set(devices.map((device) => device.deviceId));
      for (const row of this.db.prepare('SELECT DISTINCT device_id FROM history WHERE user_id=?').all(userId)) {
        if (!active.has(row.device_id)) this.db.prepare('DELETE FROM history WHERE user_id=? AND device_id=?').run(userId, row.device_id);
      }
      for (const device of devices) {
        for (const [kind, key] of [['daily', 'date'], ['monthly', 'month']]) {
          for (const raw of device.history?.[kind] || []) {
            const row = historyRow(raw, key);
            if (row) this.upsert.run(userId, device.deviceId, kind, row[key], JSON.stringify(row));
          }
        }
      }
      this.db.exec('COMMIT');
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  read(userId, kind = 'daily') {
    const rows = this.db.prepare('SELECT payload FROM history WHERE user_id=? AND kind=? ORDER BY bucket').all(userId, kind);
    const result = new Map();
    const key = kind === 'daily' ? 'date' : 'month';
    for (const { payload } of rows) {
      const row = JSON.parse(payload);
      const current = result.get(row[key]) || { [key]: row[key], tokens: 0, cost: 0, unpricedTokens: 0, messages: 0,
        cacheReadTokens: 0, cacheWriteTokens: 0, outputTokens: 0, unclassifiedTokens: 0, perClient: {}, perModel: {} };
      current.tokens += row.tokens;
      current.cost += row.cost;
      current.unpricedTokens += row.unpricedTokens;
      for (const field of ['messages', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens']) current[field] += row[field] || 0;
      current.unclassifiedTokens += row.unclassifiedTokens ?? row.tokens;
      for (const map of ['perClient', 'perModel']) {
        const merged = new Map(Object.entries(current[map]));
        for (const [name, count] of Object.entries(row[map])) {
          const old = merged.get(name) || { tokens: 0, cost: 0, cacheReadTokens: 0, cacheWriteTokens: 0, outputTokens: 0, unclassifiedTokens: 0 };
          for (const field of ['tokens', 'cost', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens']) old[field] += count[field] || 0;
          old.unclassifiedTokens += count.unclassifiedTokens ?? count.tokens;
          merged.set(name, old);
        }
        current[map] = Object.fromEntries(merged);
      }
      result.set(row[key], current);
    }
    return [...result.values()];
  }

  close() {
    this.db.close();
  }
}

module.exports = { HistoryArchive };
