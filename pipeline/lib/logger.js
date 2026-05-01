/**
 * pipeline/lib/logger.js - 结构化日志
 */
const LEVELS = {
  info: 'ℹ️',
  warn: '⚠️',
  error: '❌',
  success: '✅',
};

export function log(level, msg, data) {
  const ts = new Date().toISOString().slice(11, 19);
  const icon = LEVELS[level] || '📝';
  const prefix = `[${ts}] ${icon} [${level.toUpperCase()}]`;
  
  if (data !== undefined) {
    console.log(`${prefix} ${msg}`, data);
  } else {
    console.log(`${prefix} ${msg}`);
  }
}

export function info(msg, data) { log('info', msg, data); }
export function warn(msg, data) { log('warn', msg, data); }
export function error(msg, data) { log('error', msg, data); }
export function success(msg, data) { log('success', msg, data); }
