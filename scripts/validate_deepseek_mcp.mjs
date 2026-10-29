/** Exercise the real DSH tool registry + official MCP client against TOMC.
 * No fake MCP client, model, network API, or private notebook is used.
 * Usage: node scripts/validate_deepseek_mcp.mjs <dsh/package.json> <python> <new-output-dir>
 */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [anchor, python, output] = process.argv.slice(2);
if (!anchor || !python || !output) {
  throw new Error('Expected DSH package.json, TOMC Python executable, and a new output directory.');
}
const requireDsh = createRequire(resolve(anchor));
const dependency = (name) => import(pathToFileURL(requireDsh.resolve(name)).href);
const { Context } = await dependency('@deepseek-ai/cordis');
const { default: SystemPrompt } = await dependency('@deepseek-ai/dsh-system-prompt');
const { default: ToolRuntime } = await dependency('@deepseek-ai/dsh-tools');
const mcp = await dependency('@deepseek-ai/dsh-mcp-client');
const directory = resolve(output);
await mkdir(directory, { recursive: false });
const database = join(directory, 'synthetic-memory.sqlite3');
const report = {
  schema: 'tomc-dsh-mcp-validation-v1',
  timestamp_utc: new Date().toISOString(),
  platform: process.platform,
  node: process.version,
  dsh: JSON.parse(await readFile(resolve(anchor), 'utf8')).version,
  scope: 'Real DSH ToolRuntime and official MCP client; no model inference in this test.',
  checks: [],
};

async function boot() {
  const ctx = new Context();
  await ctx.plugin(SystemPrompt, {}).await();
  await ctx.plugin(ToolRuntime, {}).await();
  try {
    await ctx.plugin(mcp, {
      serverName: 'tomc', transport: 'stdio', command: resolve(python),
      args: ['-m', 'tomc', 'mcp', '--store', database],
      failOnStartupError: true, reconnect: { enabled: false },
    }).await();
    return ctx;
  } catch (error) {
    await ctx.fiber.dispose();
    throw error;
  }
}

let calls = 0;
async function call(ctx, name, args = {}) {
  const result = await ctx.tools.execute({
    callId: `tomc-validation-${++calls}`, name: `mcp__tomc__${name}`,
    arguments: args, signal: AbortSignal.timeout(30_000),
  });
  assert.equal(result.isError, false, JSON.stringify(result));
  const canonical = result.value;
  assert.ok(canonical, 'DSH must return a canonical MCP value');
  return canonical.structuredContent ?? JSON.parse(canonical.content.find(x => x.type === 'text').text);
}

let ctx = await boot();
try {
  const names = ctx.tools.schemas().map(x => x.name).filter(x => x.startsWith('mcp__tomc__')).sort();
  assert.equal(names.length, 10);
  report.tools = names;
  report.checks.push({ name: 'DSH discovery of all ten TOMC tools', passed: true });
  const saved = await call(ctx, 'remember_memory', {
    name: 'dsh-validation-lark',
    content: 'Project Lark uses port 4317. Keep the public API unchanged. Pagination tests remain pending.',
  });
  await call(ctx, 'remember_memory', {
    name: 'dsh-validation-other', content: 'Unrelated project: ORANGE-ISOLATION-MARKER.',
  });
  report.checks.push({ name: 'Write via official DSH MCP bridge', passed: true, result: saved });
} finally {
  await ctx.fiber.dispose();
}

// A fresh DSH context starts a fresh Python server; persistence cannot come from chat history.
ctx = await boot();
try {
  const recalled = await call(ctx, 'recall_memory', {
    name: 'dsh-validation-lark', task: 'What port, constraint, and unfinished tests does Lark have?',
    budget: 512,
  });
  assert.match(recalled.memory, /4317/);
  assert.match(recalled.memory, /public API unchanged/);
  assert.match(recalled.memory, /Pagination tests remain pending/);
  assert.doesNotMatch(recalled.memory, /ORANGE-ISOLATION-MARKER/);
  report.checks.push({ name: 'Restart persistence and notebook isolation', passed: true, memory: recalled.memory });
  const history = Array.from({length: 1500}, (_, i) =>
    `Turn ${i}: unrelated sensor ${i} emitted routine heartbeat. No action is needed.`
  ).join('\n') + '\nProject Lark final decision: port 4317; public API unchanged; pagination tests pending.';
  const prepared = await call(ctx, 'prepare_context', {
    history, task: 'Summarize the final Project Lark decisions and remaining work.', budget: 512,
  });
  assert.match(prepared.memory, /4317/);
  assert.ok(prepared.memory_estimated_tokens <= 512);
  assert.ok(prepared.memory_estimated_tokens < prepared.input_estimated_tokens);
  report.checks.push({
    name: 'Separate synthetic external-history preparation', passed: true,
    input_estimated_tokens: prepared.input_estimated_tokens,
    memory_estimated_tokens: prepared.memory_estimated_tokens,
    budget: prepared.budget, memory: prepared.memory,
  });
  const status = await call(ctx, 'get_status');
  report.checks.push({ name: 'Status through DSH bridge', passed: true, runtime_version: status.version ?? null });
} finally {
  await ctx.fiber.dispose();
}
report.passed = true;
await writeFile(join(directory, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
