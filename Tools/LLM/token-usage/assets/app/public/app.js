'use strict';

const ZH = {
  "All devices": "全部设备",
  "Device filter": "设备筛选",
  "OVERVIEW": "总览",
  "LIVE SYNC": "实时同步",
  "Mon": "周一",
  "Wed": "周三",
  "Fri": "周五",
  "Waiting for device usage": "等待设备上传用量数据",
  "All users · AI usage tracker": "所有用户 · AI 用量统计",
  "MULTI-DEVICE": "多设备同步",
  "Refresh": "刷新",
  "Share": "分享",
  "Copied": "已复制",
  "All-time tokens": "累计 Token",
  "All-time cost": "累计估算费用",
  "Active days": "活跃天数",
  "(1y)": "（近一年）",
  "Devices": "设备",
  "Usage": "用量",
  "Models": "模型",
  "Lifetime": "累计",
  "This month": "本月",
  "Last month": "上月",
  "30d": "近30天",
  "7d": "近7天",
  "Contributions": "贡献记录",
  "Recent year": "最近一年",
  "Daily contribution density across the latest 12 months.": "查看每天的 AI 用量，点击日期查看明细。",
  "Color": "配色",
  "Low": "少",
  "High": "多",
  "DAY BREAKDOWN": "单日明细",
  "Total tokens": "Token 总量",
  "Total": "总量",
  "Unattributed": "未归属",
  "Cost": "费用",
  "Messages": "消息数",
  "Token categories": "Token 构成",
  "Clients and models": "工具与模型",
  "Usage over time": "用量趋势",
  "Range total tokens": "所选范围 Token",
  "Display": "显示",
  "30d average": "30日均值",
  "Daily": "每日",
  "Newest first": "最新在前",
  "Provider": "工具",
  "All": "全部",
  "Usage details": "用量详情",
  "Scope is shown for each fact.": "各项数据的统计范围如下。",
  "Favorite model": "最常用模型",
  "Tools": "工具数",
  "(latest)": "（最新）",
  "Providers": "使用工具",
  "Token mix": "Token 构成",
  "Distribution across input, output and cache tokens.": "输入、输出及缓存 Token 的占比。",
  "Model": "模型",
  "Tokens": "Token",
  "Cache hit": "缓存命中率",
  "Share (cost)": "费用占比",
  "(cost)": "（费用）",
  "Devices · all-time": "设备 · 累计用量",
  "Device": "设备",
  "User": "用户",
  "User usage": "用户使用量",
  "User activity for the selected range.": "按用户查看所选范围内的使用趋势。",
  "Status": "状态",
  "Public · read only": "公开 · 只读",
  "Cost is estimated": "费用按模型价格估算",
  "Auto-refresh 30s": "每30秒更新",
  "Blue": "蓝色",
  "Green": "绿色",
  "Teal": "青色",
  "Purple": "紫色",
  "Pink": "粉色",
  "Orange": "橙色",
  "Monochrome": "黑白",
  "Input": "输入",
  "Output": "输出",
  "Cache read": "缓存读取",
  "Cache write": "缓存写入",
  "Unclassified": "未分类",
  "Clients": "工具",
  "Updated": "更新于",
  "Waiting for first sync": "等待首次同步",
  "user": "位用户",
  "users": "位用户",
  "device": "台设备",
  "devices": "台设备",
  "active days": "个活跃日",
  "Model activity for the selected range, grouped by provider.": "按模型查看所选范围内的使用趋势。",
  "activity for the selected range.": "在所选范围内的使用趋势。",
  "No client or model detail was recorded for this day.": "当天没有记录工具或模型明细。",
  "Range total cost": "所选范围估算费用",
  "Show less": "收起",
  "more": "更多",
  "No data yet": "暂无数据",
  "No model usage for this range.": "此范围没有模型用量。",
  "Synced": "同步正常",
  "Awaiting sync": "待更新",
  "Last synced": "最近同步",
  "connected": "台设备",
  "Includes reasoning where reported together": "包含来源合并报告的推理用量",
  "Cache read / total input (including cache writes)": "缓存读取 Token ÷ 总输入 Token（含缓存写入）",
  "Token components were not recorded": "未提供可靠的 Token 拆分",
  "Connection interrupted. Showing the last synced data.": "连接暂时中断，当前显示上次同步的数据。",
  "Unable to load usage. Please refresh later.": "暂时无法加载用量，请稍后刷新。",
  "Page URL": "当前页面地址",
  "Light theme": "切换浅色主题",
  "Dark theme": "切换深色主题",
  "Switch language": "切换语言"
};
const t = (value) => state.lang === 'zh' ? ZH[value] || value : value;

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const compact = (value) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value || 0);
const exact = (value) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value || 0);
const money = (value) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: value >= 1000 ? 'compact' : 'standard', maximumFractionDigits: 2 }).format(value || 0);
const LABELS = { codex: 'Codex CLI', claude: 'Claude Code', opencode: 'OpenCode', cursor: 'Cursor', openclaw: 'OpenClaw', copilot: 'Copilot', gemini: 'Gemini CLI', grok: 'Grok Build', commandcode: 'Command Code' };
const PALETTES = {
  Blue: ['#202633', '#1d3d70', '#255cb0', '#277fe8', '#62a4ff'], Green: ['#202b29', '#14452c', '#206b3e', '#2ba558', '#53d47c'],
  Teal: ['#202b30', '#14494d', '#1d7a7d', '#27afb1', '#62d6d0'], Purple: ['#282332', '#48346c', '#6b48a0', '#9165d1', '#b995ed'],
  Pink: ['#2c232d', '#603348', '#9c4668', '#d6698e', '#f19fba'], Orange: ['#2e2924', '#65411f', '#a66522', '#dc933b', '#f6c171'],
  Monochrome: ['#222731', '#454c59', '#707887', '#9da5b4', '#d3d9e3']
};
const query = new URLSearchParams(location.search);
const savedLanguage = localStorage.getItem('token-usage-language');
const language = ['zh', 'en'].includes(savedLanguage) ? savedLanguage : /^zh/i.test(navigator.languages?.[0] || navigator.language) ? 'zh' : 'en';
const state = { lang: language, theme: localStorage.getItem('token-usage-theme') === 'light' ? 'light' : 'dark', user: query.get('user') || 'all', device: query.get('device') || 'all', modelSort: 'tokens', modelOrder: 'desc', tab: 'usage', period: '30d', data: null, day: '', year: 'recent', heatView: '2d', color: 'Blue', metric: 'tokens', average: false, newest: false, provider: 'all', showAllLegend: false, fetching: false, chartRows: [], chartPlot: { left: 42, width: 1 } };
const timezone = () => state.data?.timeZone || 'Asia/Shanghai';
const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: timezone(), year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const shift = (day, delta) => new Date(Date.parse(day + 'T12:00:00Z') + delta * 86400000).toISOString().slice(0, 10);
const dateLabel = (day, long = false) => new Date(day + 'T12:00:00Z').toLocaleDateString(state.lang === 'zh' ? 'zh-CN' : 'en-US', long ? { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' } : { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
const availableUsers = () => state.data.users.filter((user) => state.user === 'all' || user.id === state.user);
const availableDevices = () => availableUsers().flatMap((user) => user.devices.map((device) => ({ ...device, owner: user.name })));
function users() {
  if (state.device === 'all') return availableUsers();
  return availableUsers().flatMap((user) => {
    const device = user.devices.find((entry) => entry.id === state.device);
    return device ? [{ ...user, periods: device.periods, devices: [device] }] : [];
  });
}
const sorted = (map) => Object.entries(map || {}).filter(([, value]) => value > 0).sort((a, b) => b[1] - a[1]);

function color(name) {
  const hash = Array.from(name).reduce((sum, letter) => (sum * 31 + letter.charCodeAt(0)) >>> 0, 0);
  const hue = /gpt|codex|openai/.test(name) ? 158 : /claude/.test(name) ? 19 : /deepseek/.test(name) ? 188 : /gemini/.test(name) ? 266 : 205 + hash % 70;
  return `hsl(${hue} ${48 + hash % 22}% ${45 + hash % 18}%)`;
}

const userColor = (id) => ['#3694ff', '#b287f4', '#38b7bb', '#ebaa64', '#e786ad'][state.data.users.findIndex((user) => user.id === id) % 5];
const chartLabel = (label) => state.user === 'all' ? state.data.users.find((user) => user.id === label)?.name || label : LABELS[label] || t(label);
const chartColor = (label) => state.user === 'all' ? userColor(label) : color(label);

function mergeRows(selectedUsers = users()) {
  const result = new Map();
  for (const user of selectedUsers) for (const source of (state.device === 'all' ? state.data.history[user.id]?.daily : user.devices[0]?.history?.daily) || []) {
    const row = result.get(source.date) || { date: source.date, tokens: 0, cost: 0, messages: 0, cacheReadTokens: 0, cacheWriteTokens: 0, outputTokens: 0, unclassifiedTokens: 0, perClient: Object.create(null), perModel: Object.create(null), perUser: Object.create(null) };
    row.perUser[user.id] = source;
    for (const key of ['tokens', 'cost', 'messages', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens']) row[key] += source[key] || 0;
    row.unclassifiedTokens += source.unclassifiedTokens ?? source.tokens;
    for (const key of ['perClient', 'perModel']) for (const [label, entry] of Object.entries(source[key] || {})) {
      const old = row[key][label] || { tokens: 0, cost: 0, cacheReadTokens: 0, cacheWriteTokens: 0, outputTokens: 0, unclassifiedTokens: 0 };
      for (const field of ['tokens', 'cost', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens']) old[field] += entry[field] || 0;
      old.unclassifiedTokens += entry.unclassifiedTokens ?? entry.tokens;
      row[key][label] = old;
    }
    result.set(source.date, row);
  }
  return result;
}

function bounds() {
  const end = today();
  if (state.period === '7d') return [shift(end, -6), end];
  if (state.period === '30d') return [shift(end, -29), end];
  if (state.period === 'month') return [end.slice(0, 7) + '-01', end];
  if (state.period === 'last-month') { const last = shift(end.slice(0, 7) + '-01', -1); return [last.slice(0, 7) + '-01', last]; }
  const dates = [...mergeRows().keys()].sort();
  return [dates.length && dates[0] < shift(end, -365) ? dates[0] : shift(end, -365), end];
}

function emptyPeriod() { return { totalTokens: 0, costUsd: 0, cacheReadTokens: 0, cacheWriteTokens: 0, outputTokens: 0, unclassifiedTokens: 0, unpricedTokens: 0, componentsAvailable: true, clients: Object.create(null), clientCosts: Object.create(null), models: Object.create(null), modelCosts: Object.create(null), modelCacheReads: Object.create(null), modelCacheWrites: Object.create(null), modelOutputs: Object.create(null), modelUnclassifiedTokens: Object.create(null) }; }

function periodSummary(mode = state.period) {
  const result = emptyPeriod();
  if (mode === 'lifetime' || mode === 'month') {
    for (const user of users()) {
      const source = user.periods[mode === 'lifetime' ? 'allTime' : 'month'];
      result.componentsAvailable &&= source.totalTokens === 0 || source.componentsAvailable;
      for (const key of ['totalTokens', 'costUsd', 'cacheReadTokens', 'cacheWriteTokens', 'outputTokens', 'unclassifiedTokens', 'unpricedTokens']) result[key] += source[key] || 0;
      for (const key of ['clients', 'clientCosts', 'models', 'modelCosts', 'modelCacheReads', 'modelCacheWrites', 'modelOutputs', 'modelUnclassifiedTokens']) for (const [label, count] of Object.entries(source[key] || {})) result[key][label] = (result[key][label] || 0) + count;
    }
  } else {
    const [start, end] = bounds();
    for (const [date, row] of mergeRows()) if (date >= start && date <= end) {
      result.totalTokens += row.tokens; result.costUsd += row.cost;
      for (const key of ['cacheReadTokens', 'cacheWriteTokens', 'outputTokens', 'unclassifiedTokens']) result[key] += row[key] || 0;
      for (const [source, countKey, costKey] of [['perClient', 'clients', 'clientCosts'], ['perModel', 'models', 'modelCosts']]) for (const [label, count] of Object.entries(row[source])) {
        result[countKey][label] = (result[countKey][label] || 0) + count.tokens;
        result[costKey][label] = (result[costKey][label] || 0) + count.cost;
        if (source === 'perModel') for (const [field, target] of [['cacheReadTokens','modelCacheReads'],['cacheWriteTokens','modelCacheWrites'],['outputTokens','modelOutputs'],['unclassifiedTokens','modelUnclassifiedTokens']]) result[target][label] = (result[target][label] || 0) + (count[field] || 0);
      }
    }
  }
  return result;
}

function relative(value) {
  if (!value) return state.lang === 'zh' ? '尚未同步' : 'not synced';
  const seconds = Math.max(0, (Date.now() - Date.parse(value)) / 1000);
  if (state.lang === 'zh') return seconds < 60 ? '刚刚' : seconds < 3600 ? Math.floor(seconds / 60) + '分钟前' : seconds < 86400 ? Math.floor(seconds / 3600) + '小时前' : Math.floor(seconds / 86400) + '天前';
  return seconds < 60 ? 'just now' : seconds < 3600 ? Math.floor(seconds / 60) + 'm ago' : seconds < 86400 ? Math.floor(seconds / 3600) + 'h ago' : Math.floor(seconds / 86400) + 'd ago';
}

function renderProfile() {
  const selected = users(), all = periodSummary('lifetime'), people = state.user === 'all';
  $('user-tabs').innerHTML = [{ id: 'all', name: 'OVERVIEW' }, ...state.data.users].map((user) => `<button data-user="${esc(user.id)}" class="${state.user === user.id ? 'active' : ''}" aria-pressed="${state.user === user.id}">${esc(user.id === 'all' ? t(user.name) : user.name)}</button>`).join('');
  $('profile-name').textContent = people ? 'Token Usage' : selected[0].name;
  $('profile-avatar').textContent = people ? 'T' : Array.from(selected[0].name)[0].toUpperCase();
  $('profile-handle').textContent = people ? t('All users · AI usage tracker') : '@' + selected[0].name;
  const devices = selected.flatMap((user) => user.devices);
  $('profile-meta').textContent = `${selected.length} ${t(selected.length === 1 ? 'user' : 'users')} · ${devices.length} ${t(devices.length === 1 ? 'device' : 'devices')}`;
  const last = devices.map((device) => device.updatedAt).filter(Boolean).sort().at(-1);
  $('updated-at').textContent = last ? t('Updated') + ' ' + new Date(last).toLocaleString(state.lang === 'zh' ? 'zh-CN' : 'en-US', { timeZone: timezone(), hour12: state.lang !== 'zh' }) : t('Waiting for first sync');
  $('summary-tokens').textContent = compact(all.totalTokens); $('summary-tokens').title = exact(all.totalTokens);
  $('summary-cost').textContent = all.unpricedTokens && !all.costUsd ? '—' : money(all.costUsd);
  $('summary-days').textContent = [...mergeRows()].filter(([date, row]) => date >= shift(today(), -364) && date <= today() && row.tokens > 0).length;
  $('summary-devices').textContent = devices.length; $('display-timezone').textContent = timezone();
  $('device-select').innerHTML = `<option value="all">${t('All devices')}</option>` + availableDevices().map((device) => `<option value="${esc(device.id)}">${esc((state.user === 'all' ? device.owner + ' · ' : '') + device.name)}</option>`).join('');
  $('device-select').value = state.device;
  $('device-select').setAttribute('aria-label', t('Device filter'));
  document.title = (people ? 'Overview' : selected[0].name) + ' · Token Usage';
}

function heatDays() {
  const start = state.year === 'recent' ? shift(today(), -364) : state.year + '-01-01';
  const end = state.year === 'recent' || state.year === today().slice(0, 4) ? today() : state.year + '-12-31';
  const monday = shift(start, -(new Date(start + 'T12:00:00Z').getUTCDay() + 6) % 7);
  const count = Math.ceil((Date.parse(end) - Date.parse(monday) + 86400000) / (7 * 86400000)) * 7;
  return { start, end, days: Array.from({ length: count }, (_, index) => shift(monday, index)) };
}

function renderHeat() {
  const rows = mergeRows(), palette = PALETTES[state.color].slice(), { start, end, days } = heatDays();
  if (state.theme === 'light') palette[0] = '#e9edf3';
  const years = [...new Set([today().slice(0, 4), ...[...rows.keys()].map((date) => date.slice(0, 4))])].sort().reverse();
  $('heat-year').innerHTML = '<option value="recent">' + t('Recent year') + '</option>' + years.map((year) => `<option>${year}</option>`).join(''); $('heat-year').value = state.year;
  const peak = Math.max(0, ...days.map((date) => rows.get(date)?.tokens || 0));
  let months = '', previous = ''; const cubes = [];
  $('heatmap').innerHTML = days.map((date, index) => {
    const count = rows.get(date)?.tokens || 0, outside = date < start || date > end;
    const level = count > 0 ? Math.min(4, 1 + Math.floor(Math.sqrt(count / (peak || 1)) * 3)) : 0;
    if (index % 7 === 0) { const month = date.slice(0, 7); months += `<span>${month !== previous && (index > 0 || Number(date.slice(8)) <= 7) ? new Date(date + 'T12:00:00Z').toLocaleDateString(state.lang === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', timeZone: 'UTC' }) : ''}</span>`; previous = month; }
    if (!outside) {
      const week = Math.floor(index / 7), day = index % 7, x = 20 + week * 11 + day * 8, y = 145 + day * 7 - week * .6;
      const h = count > 0 ? 5 + Math.pow(count / (peak || 1), .65) * 78 : 1;
      cubes.push({ depth: y, markup: `<g data-day="${date}" role="button" aria-label="${date}: ${exact(count)} tokens"><title>${date}: ${compact(count)} tokens</title><path d="M${x+7.2},${y+5.5-h}l10.2,-1v${h}l-10.2,1z" fill="${palette[level]}" opacity=".6"/><path d="M${x},${y-h}l7.2,5.5v${h}l-7.2,-5.5z" fill="${palette[level]}" opacity=".82"/><path d="M${x},${y-h}l10.2,-1l7.2,5.5l-10.2,1z" fill="${palette[level]}" stroke="${date === state.day ? (state.theme === 'light' ? '#2866b1' : '#d7e5fa') : palette[0]}" stroke-width="${date === state.day ? 1 : .35}"/></g>` });
    }
    return `<button class="heat-cell${outside ? ' outside' : ''}${date === state.day ? ' selected' : ''}" style="background:${palette[level]}" data-day="${date}" tabindex="${date === state.day && !outside ? 0 : -1}" aria-pressed="${date === state.day}" aria-label="${date}: ${exact(count)} tokens" title="${date}: ${exact(count)} tokens"${outside ? ' disabled' : ''}></button>`;
  }).join('');
  const weeks = days.length / 7;
  $('heatmap').style.gridTemplateColumns = `repeat(${weeks},minmax(6px,1fr))`; $('heat-months').style.gridTemplateColumns = `repeat(${weeks},minmax(6px,1fr))`; $('heat-months').innerHTML = months;
  $('heat-3d').setAttribute('viewBox', '0 0 680 230');
  $('heat-3d').innerHTML = cubes.sort((a, b) => a.depth - b.depth).map((cube) => cube.markup).join('');
  $('heatmap').parentElement.hidden = state.heatView === '3d'; $('heat-months').hidden = state.heatView === '3d'; $('heat-3d').toggleAttribute('hidden', state.heatView !== '3d');
  $('heat-active').textContent = days.filter((date) => date >= start && date <= end && rows.get(date)?.tokens > 0).length + ' ' + t('active days');
  $('heat-range').textContent = dateLabel(start) + ' – ' + dateLabel(end);
  $('palette-preview').innerHTML = palette.slice(1).map((value) => `<i style="background:${value}"></i>`).join(''); $('heat-scale').innerHTML = palette.map((value) => `<i style="background:${value}"></i>`).join('');
}

function categories(source, total) {
  const read = source.cacheReadTokens || 0, write = source.cacheWriteTokens || 0, output = source.outputTokens || 0;
  const unknown = source.unclassifiedTokens ?? Math.max(0, total - read - write - output);
  return [['Input', Math.max(0, total - read - write - output - unknown), '#38b7bb'], ['Output', output, '#9177df'], ['Cache read', read, '#3694ff'], ['Cache write', write, '#ebaa64'], ['Unclassified', unknown, '#737e90']];
}

function cacheHit(tokens, cached, output, unknown = 0, available = true) {
  const input = Math.max(0, tokens - output);
  return available && unknown === 0 && input > 0 ? Math.min(1, cached / input) : null;
}

function cacheText(tokens, cached, output, unknown = 0, available = true) {
  const rate = cacheHit(tokens, cached, output, unknown, available);
  return { label: rate === null ? '—' : (rate * 100).toFixed(1) + '%', title: rate === null ? t('Token components were not recorded') : t('Cache read / total input (including cache writes)') + ': ' + exact(cached) + ' / ' + exact(tokens - output) };
}

function renderDay() {
  const row = mergeRows().get(state.day) || { tokens: 0, cost: 0, messages: 0, unclassifiedTokens: 0, perClient: {}, perModel: {} };
  $('day-title').textContent = dateLabel(state.day, true); $('day-tokens').textContent = exact(row.tokens); $('day-cost').textContent = money(row.cost); $('day-messages').textContent = row.messages || !row.tokens ? exact(row.messages) : '—';
  const overall = cacheText(row.tokens, row.cacheReadTokens || 0, row.outputTokens || 0, row.unclassifiedTokens || 0);
  $('day-cache-hit').textContent = overall.label; $('day-cache-hit').title = overall.title;
  $('day-categories').innerHTML = categories(row, row.tokens).map(([label, value]) => `<div class="category"><span${label === 'Output' ? ` title="${esc(t('Includes reasoning where reported together'))}"` : ''}>${t(label)}</span><strong title="${exact(value)}">${compact(value)}</strong></div>`).join('');
  $('day-users-section').hidden = state.user !== 'all';
  $('day-users').innerHTML = state.user === 'all' ? users().map((user) => ({ ...user, tokens: row.perUser?.[user.id]?.tokens || 0 })).sort((a, b) => b.tokens - a.tokens).map((user) => `<div class="breakdown-row"><i class="color-dot" style="background:${userColor(user.id)}"></i><span class="row-name">${esc(user.name)}</span><span class="row-value" title="${exact(user.tokens)}">${compact(user.tokens)}</span></div>`).join('') : '';
  const section = (map, heading) => Object.keys(map).length ? `<div class="breakdown-label">${t(heading)}${heading === 'Models' ? `<span>${t('Cache hit')}</span>` : ''}</div>` + Object.entries(map).filter(([, value]) => value.tokens > 0).sort((a, b) => b[1].tokens - a[1].tokens).slice(0, 6).map(([label, value]) => {
    const rate = cacheText(value.tokens, value.cacheReadTokens || 0, value.outputTokens || 0, value.unclassifiedTokens ?? value.tokens);
    return `<div class="breakdown-row"><i class="color-dot" style="background:${color(label)}"></i><span class="row-name" title="${esc(label)}">${esc(LABELS[label] || label)}</span><span class="row-value">${compact(value.tokens)}</span>${heading === 'Models' ? `<span class="cache-rate" title="${esc(rate.title)}">${rate.label}</span>` : ''}</div>`;
  }).join('') : '';
  $('day-breakdown').innerHTML = section(row.perClient, 'Clients') + section(row.perModel, 'Models') || t('No client or model detail was recorded for this day.');
}

function chartData() {
  const history = mergeRows(), [start, end] = bounds(), dates = [];
  for (let day = start; day <= end; day = shift(day, 1)) dates.push(day);
  const labels = new Map();
  const rows = dates.map((date) => {
    const row = history.get(date), values = Object.create(null);
    if (state.user === 'all') {
      for (const user of users()) {
        const entry = row?.perUser[user.id];
        values[user.id] = (state.provider === 'all' ? entry?.[state.metric] : entry?.perClient?.[state.provider]?.[state.metric]) || 0;
      }
    } else if (state.provider === 'all') {
      for (const [label, entry] of Object.entries(row?.perModel || {})) values[label] = entry[state.metric] || 0;
      const remainder = (row?.[state.metric] || 0) - Object.values(values).reduce((sum, value) => sum + value, 0);
      if (remainder > 0) values.Unattributed = remainder;
    } else values[state.provider] = row?.perClient?.[state.provider]?.[state.metric] || 0;
    for (const [label, value] of Object.entries(values)) labels.set(label, (labels.get(label) || 0) + value);
    return { date, values, total: Object.values(values).reduce((sum, value) => sum + value, 0) };
  });
  const order = [...labels].sort((a, b) => b[1] - a[1]).map(([label]) => label), rawTotal = rows.reduce((sum, row) => sum + row.total, 0);
  if (state.average) {
    const sums = Object.create(null);
    rows.forEach((row, index) => {
      const old = rows[index - 30];
      for (const label of order) sums[label] = (sums[label] || 0) + (row.values[label] || 0) - (old?.values[label] || 0);
      row.average = Object.fromEntries(order.map((label) => [label, sums[label] / Math.min(index + 1, 30)]));
    });
  }
  return { rows: state.newest ? rows.reverse() : rows, order, rawTotal };
}

function renderChart() {
  if ($('usage-view').hidden) return;
  const { rows, order, rawTotal } = chartData(); state.chartRows = rows;
  const valueAt = (row, label) => (state.average ? row.average : row.values)[label] || 0;
  const stackedView = state.user !== 'all';
  const width = Math.max(220, $('usage-chart').getBoundingClientRect().width), left = 42, right = width - 8, top = 15, bottom = 249;
  state.chartPlot = { left, width: right - left };
  $('usage-chart').setAttribute('viewBox', `0 0 ${width} 260`);
  const maximum = Math.max(0, ...rows.map((row) => stackedView ? order.reduce((sum, label) => sum + valueAt(row, label), 0) : Math.max(0, ...order.map((label) => valueAt(row, label))))) * 1.04 || 1;
  let svg = '<title>Usage over time</title>';
  for (let i = 0; i < 5; i++) { const y = top + (bottom - top) * i / 4, value = maximum * (1 - i / 4); svg += `<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" class="chart-grid"/><text x="${left - 7}" y="${y + 3}" text-anchor="end" class="chart-axis-label">${state.metric === 'tokens' ? compact(value) : money(value)}</text>`; }
  const stacked = rows.map(() => 0), x = (index) => left + index / Math.max(1, rows.length - 1) * (right - left), y = (value) => bottom - value / maximum * (bottom - top);
  let curves = '';
  for (const label of order) {
    const lower = stackedView ? stacked.slice() : rows.map(() => 0); rows.forEach((row, index) => { stacked[index] = (stackedView ? stacked[index] : 0) + valueAt(row, label); });
    const upper = stacked.map((value, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join('');
    const lowerPath = lower.map((value, index) => [x(index), y(value)]).reverse().map(([px, py]) => `L${px.toFixed(1)},${py.toFixed(1)}`).join('');
    svg += `<path d="${upper}${lowerPath}Z" fill="${chartColor(label)}" fill-opacity="${stackedView ? .38 : .16}"/>`;
    const curve = `<path d="${upper}" fill="none" stroke="${chartColor(label)}" stroke-width="${stackedView ? 1 : 2}" stroke-opacity=".9"/>`;
    if (stackedView) svg += curve; else curves += curve;
  }
  svg += curves;
  svg += `<line id="chart-cursor" y1="${top}" y2="${bottom}" stroke="#c7d9f0" stroke-dasharray="3 3" style="display:none"/>`;
  $('usage-chart').innerHTML = svg; $('usage-chart').setAttribute('tabindex', '0'); $('chart-empty').hidden = rawTotal > 0;
  $('range-total-label').textContent = t(state.metric === 'tokens' ? 'Range total tokens' : 'Range total cost'); $('range-total').textContent = state.metric === 'tokens' ? compact(rawTotal) : money(rawTotal);
  $('chart-start').textContent = dateLabel(rows[0].date); $('chart-end').textContent = dateLabel(rows.at(-1).date);
  $('chart-description').textContent = state.user === 'all' ? (state.provider === 'all' ? '' : (LABELS[state.provider] || state.provider) + ' · ') + t('User activity for the selected range.') : state.provider === 'all' ? t('Model activity for the selected range, grouped by provider.') : (LABELS[state.provider] || state.provider) + ' ' + t('activity for the selected range.');
  const shown = state.showAllLegend ? order : order.slice(0, 6);
  $('chart-legend').innerHTML = shown.map((label) => `<span><i class="color-dot" style="background:${chartColor(label)}"></i>${esc(chartLabel(label))}</span>`).join('') + (order.length > 6 ? `<button class="legend-more" id="legend-more">${state.showAllLegend ? t('Show less') : '+ ' + (order.length - 6) + ' ' + t('more')}</button>` : '');
  $('chart-provider').innerHTML = '<option value="all">' + t('All') + '</option>' + Object.keys(periodSummary('lifetime').clients).map((label) => `<option value="${esc(label)}">${esc(LABELS[label] || label)}</option>`).join(''); $('chart-provider').value = state.provider;
  $('chart-tooltip').hidden = true;
}

function inspectChart(index) {
  const row = state.chartRows[index]; if (!row) return;
  const width = $('usage-chart').getBoundingClientRect().width, position = state.chartPlot.left + index / Math.max(1, state.chartRows.length - 1) * state.chartPlot.width;
  const format = (value) => state.metric === 'tokens' ? compact(value) + ' Tokens' : money(value);
  const tooltip = $('chart-tooltip');
  const entries = Object.entries(row.values).filter(([, value]) => state.user === 'all' || value > 0).sort((a, b) => b[1] - a[1]);
  tooltip.innerHTML = `<strong>${dateLabel(row.date)}</strong><div class="chart-tooltip-total"><span>${t('Total')}</span><b>${format(row.total)}</b></div><dl>${entries.map(([label, value]) => `<div><dt><i class="color-dot" style="background:${chartColor(label)}"></i><span>${esc(chartLabel(label))}</span></dt><dd>${format(value)}</dd></div>`).join('')}</dl>`;
  tooltip.hidden = false;
  tooltip.style.left = Math.min(Math.max(12, position + 22), Math.max(12, width + 20 - tooltip.getBoundingClientRect().width)) + 'px';
  const cursor = $('chart-cursor'); cursor.style.display = ''; cursor.setAttribute('x1', position); cursor.setAttribute('x2', position); $('usage-chart').dataset.index = index;
}

function chartIndex(event) {
  const chart = $('usage-chart'), point = chart.createSVGPoint();
  point.x = event.clientX; point.y = event.clientY;
  const local = point.matrixTransform(chart.getScreenCTM().inverse());
  return Math.max(0, Math.min(state.chartRows.length - 1, Math.round((local.x - state.chartPlot.left) / state.chartPlot.width * (state.chartRows.length - 1))));
}

function hideChartTooltip() {
  $('chart-tooltip').hidden = true;
  if ($('chart-cursor')) $('chart-cursor').style.display = 'none';
}

function renderDetails() {
  const all = periodSummary('lifetime'), current = periodSummary(), models = Object.create(null);
  for (const [date, row] of mergeRows()) if (date >= shift(today(), -364)) for (const [label, value] of Object.entries(row.perModel)) models[label] = (models[label] || 0) + value.tokens;
  $('favorite-model').textContent = sorted(models)[0]?.[0] || '—'; $('favorite-model').title = $('favorite-model').textContent;
  $('tools-count').textContent = Object.keys(all.clients).length; $('models-count').textContent = Object.keys(all.models).length;
  $('tool-tags').innerHTML = Object.keys(all.clients).map((label) => `<span>${esc(label)}</span>`).join('') || '<span>' + t('No data yet') + '</span>';
  const mix = categories(current, current.totalTokens); let start = 0;
  $('mix-donut').style.background = current.totalTokens ? `conic-gradient(${mix.map(([, value, fill]) => { const old = start; start += value / current.totalTokens * 100; return `${fill} ${old}% ${start}%`; }).join(',')})` : state.theme === 'light' ? '#e9edf3' : '#222c3d';
  $('mix-total').textContent = compact(current.totalTokens);
  $('mix-legend').innerHTML = mix.map(([label, value, fill]) => `<div><dt><i class="color-dot" style="background:${fill}"></i>${t(label)}</dt><dd>${compact(value)}<small>${(current.totalTokens ? value / current.totalTokens * 100 : 0).toFixed(1)}%</small></dd></div>`).join('');
}

function renderModels() {
  const value = periodSummary();
  const metric = ([name, tokens]) => state.modelSort === 'model' ? name : state.modelSort === 'tokens' ? tokens
    : state.modelSort === 'cache' ? cacheHit(tokens, value.modelCacheReads[name] || 0, value.modelOutputs[name] || 0, value.modelUnclassifiedTokens[name] || 0, value.componentsAvailable || Object.hasOwn(value.modelUnclassifiedTokens, name))
    : state.modelSort === 'share' ? value.costUsd > 0 ? (value.modelCosts[name] || 0) / value.costUsd : null : value.modelCosts[name] ?? null;
  const models = Object.entries(value.models).sort((a, b) => {
    const first = metric(a), second = metric(b);
    if (first === null || second === null) return first === second ? a[0].localeCompare(b[0]) : first === null ? 1 : -1;
    const difference = typeof first === 'string' ? first.localeCompare(second, undefined, { numeric: true }) : first - second;
    return (state.modelOrder === 'asc' ? difference : -difference) || a[0].localeCompare(b[0]);
  });
  document.querySelectorAll('.models-table th[data-sort]').forEach((header) => {
    const active = header.dataset.sort === state.modelSort;
    header.setAttribute('aria-sort', active ? state.modelOrder === 'asc' ? 'ascending' : 'descending' : 'none');
    header.querySelector('.sort-indicator').textContent = active ? state.modelOrder === 'asc' ? '↑' : '↓' : '↕';
  });
  $('models-list').innerHTML = models.map(([name, tokens]) => {
    const rate = cacheText(tokens, value.modelCacheReads[name] || 0, value.modelOutputs[name] || 0, value.modelUnclassifiedTokens[name] || 0, value.componentsAvailable || Object.hasOwn(value.modelUnclassifiedTokens, name));
    return `<tr><td><i class="color-dot" style="background:${color(name)}"></i><span title="${esc(name)}">${esc(name)}</span></td><td title="${exact(tokens)}">${compact(tokens)}</td><td>${Object.hasOwn(value.modelCosts, name) ? money(value.modelCosts[name]) : '—'}</td><td class="cache-hit-cell" title="${esc(rate.title)}">${rate.label}</td><td>${value.costUsd ? ((value.modelCosts[name] || 0) / value.costUsd * 100).toFixed(1) + '%' : '—'}</td></tr>`;
  }).join('');
  $('models-empty').hidden = models.length > 0;
}

function renderDevices() {
  const list = users().flatMap((user) => user.devices.map((device) => ({ ...device, owner: user.name })));
  $('devices-total').textContent = list.length + ' ' + t('connected'); $('devices-empty').hidden = list.length > 0;
  $('devices-list').innerHTML = list.map((device) => `<tr><td><span class="device-title">${esc(device.name)}</span><span class="device-subtitle">${esc(device.platform)} · ${t('Last synced')} ${relative(device.updatedAt)}</span></td><td>${esc(device.owner)}</td><td><span class="status-pill${device.stale ? ' stale' : ''}">${t(device.stale ? 'Awaiting sync' : 'Synced')}</span></td><td title="${exact(device.periods.allTime.totalTokens)}">${compact(device.periods.allTime.totalTokens)}</td><td>${money(device.periods.allTime.costUsd)}</td><td>${device.activeDays ?? '—'}</td></tr>`).join('');
}

function renderControls() {
  for (const [attribute, value] of [['tab', state.tab], ['period', state.period], ['view', state.heatView], ['metric', state.metric]]) document.querySelectorAll('[data-' + attribute + ']').forEach((button) => { const active = button.dataset[attribute] === value; button.classList.toggle('active', active); button.setAttribute(attribute === 'tab' ? 'aria-selected' : 'aria-pressed', active); });
  $('usage-view').hidden = state.tab !== 'usage'; $('models-view').hidden = state.tab !== 'models';
}

function render() {
  if (!state.data) return;
  if (state.user !== 'all' && !state.data.users.some((user) => user.id === state.user)) state.user = 'all';
  if (state.device !== 'all' && !availableDevices().some((device) => device.id === state.device)) state.device = 'all';
  if (!state.day) state.day = today();
  translatePage(); renderProfile(); renderControls(); renderHeat(); renderDay(); renderChart(); renderDetails(); renderModels(); renderDevices();
}

async function refresh() {
  if (state.fetching) return; state.fetching = true; $('refresh').disabled = true;
  try {
    const response = await fetch('/api/public/stats', { cache: 'no-store', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    state.data = await response.json(); render(); $('notice').hidden = true;
  } catch { $('notice').textContent = t(state.data ? 'Connection interrupted. Showing the last synced data.' : 'Unable to load usage. Please refresh later.'); $('notice').hidden = false; }
  finally { state.fetching = false; $('refresh').disabled = false; }
}

document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-user],[data-tab],[data-period],[data-view],[data-metric],[data-day],[data-sort],#legend-more'); if (!target || target.disabled || !state.data) return;
  if (target.dataset.user) { state.user = target.dataset.user; state.device = 'all'; state.provider = 'all'; const url = new URL(location.href); url.searchParams.delete('device'); if (state.user === 'all') url.searchParams.delete('user'); else url.searchParams.set('user', state.user); history.replaceState(null, '', url); }
  if (target.dataset.sort) { state.modelOrder = state.modelSort === target.dataset.sort && state.modelOrder === 'desc' ? 'asc' : 'desc'; state.modelSort = target.dataset.sort; renderModels(); return; }
  if (target.dataset.tab) state.tab = target.dataset.tab;
  if (target.dataset.period) { state.period = target.dataset.period; state.day = bounds()[1]; }
  if (target.dataset.view) state.heatView = target.dataset.view;
  if (target.dataset.metric) state.metric = target.dataset.metric;
  if (target.dataset.day) state.day = target.dataset.day;
  if (target.id === 'legend-more') state.showAllLegend = !state.showAllLegend;
  render();
});
$('heat-year').addEventListener('change', (event) => { state.year = event.target.value; renderHeat(); });
$('device-select').addEventListener('change', (event) => { state.device = event.target.value; state.provider = 'all'; const url = new URL(location.href); if (state.device === 'all') url.searchParams.delete('device'); else url.searchParams.set('device', state.device); history.replaceState(null, '', url); render(); });
$('heat-color').addEventListener('change', (event) => { state.color = event.target.value; renderHeat(); });
$('chart-display').addEventListener('change', (event) => { state.average = event.target.value === 'average'; renderChart(); });
$('chart-provider').addEventListener('change', (event) => { state.provider = event.target.value; renderChart(); });
$('newest-first').addEventListener('change', (event) => { state.newest = event.target.checked; renderChart(); });
$('usage-chart').addEventListener('pointermove', (event) => { if (event.pointerType !== 'touch') inspectChart(chartIndex(event)); });
$('usage-chart').addEventListener('pointerleave', (event) => { if (event.pointerType !== 'touch') hideChartTooltip(); });
$('usage-chart').addEventListener('pointercancel', hideChartTooltip);
$('usage-chart').addEventListener('click', (event) => { const index = chartIndex(event), row = state.chartRows[index]; if (row) { inspectChart(index); state.day = row.date; renderHeat(); renderDay(); } });
$('usage-chart').addEventListener('keydown', (event) => { let index = Number(event.currentTarget.dataset.index || 0); if (event.key === 'ArrowRight') index++; else if (event.key === 'ArrowLeft') index--; else if (event.key === 'Home') index = 0; else if (event.key === 'End') index = state.chartRows.length - 1; else if (event.key === 'Escape') { hideChartTooltip(); return; } else return; event.preventDefault(); inspectChart(Math.max(0, Math.min(state.chartRows.length - 1, index))); });
document.addEventListener('pointerdown', (event) => { if (!event.target.closest('#usage-chart,#chart-tooltip')) hideChartTooltip(); });
$('heatmap').addEventListener('keydown', (event) => { const delta = { ArrowLeft: -7, ArrowRight: 7, ArrowUp: -1, ArrowDown: 1 }[event.key]; if (delta === undefined && !['Home', 'End'].includes(event.key)) return; event.preventDefault(); const { start, end } = heatDays(); state.day = event.key === 'Home' ? start : event.key === 'End' ? end : shift(state.day, delta); if (state.day < start) state.day = start; if (state.day > end) state.day = end; renderHeat(); renderDay(); document.querySelector(`[data-day="${state.day}"]`)?.focus(); });
$('refresh').addEventListener('click', refresh);
$('share').addEventListener('click', async () => { try { await navigator.clipboard.writeText(location.href); $('share').innerHTML = t('Copied'); setTimeout(() => { $('share').innerHTML = '↗ <span data-i18n="Share">' + t('Share') + '</span>'; }, 1500); } catch { $('notice').textContent = t('Page URL') + ': ' + location.href; $('notice').hidden = false; } });
window.addEventListener('resize', () => { if (state.data) renderChart(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
setInterval(() => { if (!document.hidden) refresh(); }, 30000);
refresh();

function translatePage() {
  document.documentElement.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
  document.documentElement.dataset.theme = state.theme;
  document.querySelectorAll('[data-i18n]').forEach((element) => { element.textContent = t(element.dataset.i18n); });
  $('language-toggle').textContent = state.lang === 'zh' ? 'EN' : '中文';
  $('language-toggle').title = t('Switch language');
  $('theme-toggle').textContent = state.theme === 'dark' ? '☀' : '☾';
  $('theme-toggle').title = t(state.theme === 'dark' ? 'Light theme' : 'Dark theme');
  $('theme-toggle').setAttribute('aria-label', $('theme-toggle').title);
}
$('language-toggle').addEventListener('click', () => { state.lang = state.lang === 'zh' ? 'en' : 'zh'; localStorage.setItem('token-usage-language', state.lang); translatePage(); render(); });
$('theme-toggle').addEventListener('click', () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('token-usage-theme', state.theme); translatePage(); render(); });
translatePage();
