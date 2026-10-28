// Exercise the installed OpenClaw runner with synthetic failures; no model requests or credentials.
import assert from 'node:assert/strict';
import { readdir } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const dist = path.join(root, '.runtime/node_modules/openclaw/dist');
const files = await readdir(dist);
async function imported(prefix, symbol) {
  const file = files.find(name => name.startsWith(prefix) && name.endsWith('.mjs'));
  assert.ok(file, `Installed runtime module missing: ${prefix}`);
  return (await import(pathToFileURL(path.join(dist, file))))[symbol];
}
const runFallback = await imported('model-fallback-runner-BX', 't');
const FailoverError = await imported('error-Cmm', 'n');
const applyOverride = await imported('model-overrides-', 'r');
const cfg = {plugins: {enabled: false}, agents: {defaults: {
  model: {primary: 'openai/gpt-6-astra', fallbacks: ['deepseek/deepseek-flash']},
  models: {
    'openai/gpt-6-astra': {agentRuntime: {id: 'openclaw'}},
    'deepseek/deepseek-flash': {agentRuntime: {id: 'openclaw'}},
  },
}}};
const results = [];
for (const [reason, status] of [['rate_limit', 429], ['billing', 402], ['timeout', 504], ['auth', 401]]) {
  const calls = [];
  const result = await runFallback({cfg, provider: 'openai', model: 'gpt-6-astra',
    manifestPlugins: [], skipAuthProfileRuntime: true,
    run: async (provider, model) => {
      calls.push(`${provider}/${model}`);
      if (provider === 'openai') throw new FailoverError('Synthetic provider failure', {reason, status, provider, model});
      return {text: 'synthetic backup response'};
    },
  });
  assert.deepEqual(calls, ['openai/gpt-6-astra', 'deepseek/deepseek-flash']);
  assert.equal(result.provider, 'deepseek');
  results.push(reason);
}
const calls = [];
await runFallback({cfg, provider: 'openai', model: 'gpt-6-astra',
  manifestPlugins: [], skipAuthProfileRuntime: true,
  run: async (provider) => {
    calls.push(provider);
    if (provider === 'openai') throw new TypeError('fetch failed', {
      cause: Object.assign(new Error('read ECONNRESET'), {code: 'ECONNRESET'}),
    });
    return {text: 'synthetic network backup'};
  },
});
assert.deepEqual(calls, ['openai', 'deepseek']);
results.push('ECONNRESET');
const entry = {};
applyOverride({entry, selection: {provider: 'deepseek', model: 'deepseek-flash', isDefault: false}});
assert.equal(entry.modelOverrideSource, 'user');
applyOverride({entry, selection: {provider: 'openai', model: 'gpt-6-astra', isDefault: true}});
assert.equal(entry.modelOverride, undefined);
assert.equal(entry.modelOverrideSource, undefined);
console.log(JSON.stringify({synthetic_failover: results, default_selection_clears_pin: true,
  real_network_failure_tested: false, messages_sent: false}));
