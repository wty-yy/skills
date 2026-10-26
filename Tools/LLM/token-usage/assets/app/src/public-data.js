'use strict';

const crypto = require('node:crypto');
const { aggregateDevices } = require('../vendor/token-monitor/src/shared/usage');

const PERIODS = ['today', 'month', 'allTime'];
const COUNTERS = ['totalTokens', 'costUsd', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens', 'unclassifiedTokens', 'unpricedTokens'];
const MAPS = ['clients', 'clientCosts', 'models', 'modelCosts', 'modelCacheReads', 'modelCacheWrites', 'modelOutputs', 'modelUnclassifiedTokens'];

function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, value) : 0;
}

function numericMap(value) {
  return Object.fromEntries(Object.entries(value || {}).filter(([, count]) => typeof count === 'number' && Number.isFinite(count)).map(([key, count]) => [key.slice(0, 160), number(count)]));
}

function publicPeriod(value = {}) {
  return {
    componentsAvailable: value.capabilities?.tokenComponents === true,
    ...Object.fromEntries(COUNTERS.map((key) => [key, number(value[key])])),
    ...Object.fromEntries(MAPS.map((key) => [key, numericMap(value[key])]))
  };
}

function publicDeviceId(userId, deviceId) {
  return crypto.createHash('sha256').update(`${userId}:${deviceId}`).digest('hex').slice(0, 16);
}

function publicUser(user, hub, deviceName = () => '', deviceHistory = () => undefined) {
  const stats = hub.getStats();
  const records = hub.getDevices();
  return {
    id: user.id,
    name: user.name,
    periods: Object.fromEntries(PERIODS.map((period) => [period, publicPeriod(stats.periods[period])])),
    devices: stats.devices.map((device, index) => {
      const record = records.find((entry) => entry.deviceId === device.deviceId);
      const periods = aggregateDevices([record]).periods;
      return {
      id: publicDeviceId(user.id, device.deviceId),
      name: user.devices?.[device.deviceId] || deviceName(device.deviceId) || `设备 ${String(index + 1).padStart(2, '0')}`,
      platform: String(device.platform || 'unknown').slice(0, 40),
      updatedAt: device.receivedAt || device.updatedAt || null,
      stale: device.stale,
      historyAvailable: records.find((record) => record.deviceId === device.deviceId)?.historyAvailable === true,
      activeDays: (record.history?.daily || []).filter((day) => day.tokens > 0).length,
      history: deviceHistory(device.deviceId),
      periods: Object.fromEntries(PERIODS.map((period) => [period, publicPeriod(periods[period])]))
      };
    })
  };
}

function combinePeriods(values) {
  const result = publicPeriod();
  result.componentsAvailable = values.every((value) => value.componentsAvailable);
  for (const value of values) {
    for (const key of COUNTERS) result[key] += number(value[key]);
    for (const key of MAPS) {
      const entries = new Map(Object.entries(result[key]));
      for (const [label, count] of Object.entries(value[key])) entries.set(label, (entries.get(label) || 0) + count);
      result[key] = Object.fromEntries(entries);
    }
  }
  return result;
}

function historyRow(row, key = 'date') {
  if (!row || !new RegExp(key === 'date' ? '^\\d{4}-\\d{2}-\\d{2}$' : '^\\d{4}-\\d{2}$').test(row[key])) return null;
  const breakdown = (value) => Object.fromEntries(Object.entries(value || {}).map(([name, counters]) => [name.slice(0, 160), {
    tokens: number(counters?.tokens), cost: number(counters?.cost),
    cacheReadTokens: number(counters?.cacheReadTokens), cacheWriteTokens: number(counters?.cacheWriteTokens), outputTokens: number(counters?.outputTokens),
    unclassifiedTokens: typeof counters?.unclassifiedTokens === 'number' ? number(counters.unclassifiedTokens)
      : row.tokenComponentsAvailable === true ? 0 : Math.max(0, number(counters?.tokens) - number(counters?.cacheReadTokens) - number(counters?.cacheWriteTokens) - number(counters?.outputTokens))
  }]));
  return {
    [key]: row[key], tokens: number(row.tokens), cost: number(row.cost),
    unpricedTokens: number(row.unpricedTokens),
    messages: number(row.messages),
    cacheReadTokens: number(row.cacheReadTokens), cacheWriteTokens: number(row.cacheWriteTokens),
    outputTokens: number(row.outputTokens),
    unclassifiedTokens: typeof row.unclassifiedTokens === 'number' ? number(row.unclassifiedTokens)
      : row.tokenComponentsAvailable === true ? 0 : Math.max(0, number(row.tokens) - number(row.cacheReadTokens) - number(row.cacheWriteTokens) - number(row.outputTokens)),
    perClient: breakdown(row.perClient), perModel: breakdown(row.perModel)
  };
}

module.exports = { number, publicPeriod, publicUser, publicDeviceId, combinePeriods, historyRow };
