const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const comment = require('./comment-api-compatibility.cjs');

async function run(t, report, {previous = false, stale = false, changed = false, superseded = false} = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'compat-comment-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  process.env.COMPATIBILITY_REPORT = path.join(directory, 'report.json');
  if (report !== null) fs.writeFileSync(process.env.COMPATIBILITY_REPORT, JSON.stringify(report));
  const pr = {number: 12, state: 'open', base: {repo: {full_name: 'PrefectHQ/prefect'}},
    head: {sha: stale ? 'new' : 'head', repo: {full_name: 'contributor/prefect'}}};
  const writes = [];
  const github = {
    rest: {
      actions: {listWorkflowRuns: async () => ({data: {workflow_runs: [{id: 42, run_attempt: superseded ? 2 : 1}]}})},
      repos: {listPullRequestsAssociatedWithCommit: 'pulls'},
      pulls: {get: async () => ({data: changed ? {...pr, head: {...pr.head, sha: 'new'}} : pr})},
      issues: {listComments: 'comments',
        createComment: async data => writes.push({action: 'create', ...data}),
        updateComment: async data => writes.push({action: 'update', ...data})},
    },
    paginate: async method => method === 'pulls' ? [pr] : previous ? [
      {id: 7, user: {login: 'github-actions[bot]'}, body: '<!-- cloud-api-compatibility --> old warning'},
    ] : [],
  };
  await comment({github, core: {warning: () => {}}, context: {
    repo: {owner: 'PrefectHQ', repo: 'prefect'},
    payload: {workflow_run: {id: 42, run_attempt: 1, workflow_id: 9,
      path: '.github/workflows/api-compatibility-tests.yaml',
      head_sha: 'head', head_repository: {full_name: 'contributor/prefect'}}},
  }});
  return writes;
}

test('creates one advisory for a new incompatibility on a fork PR', async t => {
  const writes = await run(t, {status: 'incompatible', new_failures: ['test_route[POST: /api/new]']});
  assert.equal(writes.length, 1);
  assert.equal(writes[0].action, 'create');
  assert.equal(writes[0].issue_number, 12);
  assert.match(writes[0].body, /non-blocking/);
  assert.match(writes[0].body, /test_route\[POST: \/api\/new\]/);
});

test('updates the existing warning instead of adding a comment', async t => {
  const writes = await run(t, {status: 'incompatible', new_failures: ['test_sort']}, {previous: true});
  assert.equal(writes.length, 1);
  assert.equal(writes[0].action, 'update');
  assert.equal(writes[0].comment_id, 7);
});

test('clears the existing warning when the new incompatibility is resolved', async t => {
  const writes = await run(t, {status: 'compatible', new_failures: []}, {previous: true});
  assert.equal(writes[0].action, 'update');
  assert.match(writes[0].body, /no new compatibility failures/);
});

test('does not create comments for passing or unavailable checks', async t => {
  for (const report of [{status: 'compatible', new_failures: []}, {status: 'unavailable'}, null]) {
    assert.deepEqual(await run(t, report), []);
  }
});

test('updates an existing warning when a check is unavailable or malformed', async t => {
  for (const report of [null, {status: 'incompatible', new_failures: []}, {status: 'compatible', new_failures: [1]}]) {
    const writes = await run(t, report, {previous: true});
    assert.match(writes[0].body, /could not be evaluated/);
  }
});

test('ignores obsolete runs, including a head changed during processing', async t => {
  const report = {status: 'incompatible', new_failures: ['test_route']};
  assert.deepEqual(await run(t, report, {stale: true}), []);
  assert.deepEqual(await run(t, report, {changed: true}), []);
  assert.deepEqual(await run(t, report, {superseded: true}), []);
});

test('escapes report content instead of posting markup or mentions', async t => {
  const writes = await run(t, {status: 'incompatible', new_failures: ['</code>@someone & <img>']});
  assert.match(writes[0].body, /&lt;\/code&gt;&#64;someone &amp; &lt;img&gt;/);
  assert.doesNotMatch(writes[0].body, /@someone|<img>/);
});

test('uses the opened report when its path is replaced before partial reads', async t => {
  let replaced = false;
  const replace = () => {
    if (replaced) return;
    const reportPath = process.env.COMPATIBILITY_REPORT;
    const replacement = `${reportPath}.replacement`;
    fs.writeFileSync(replacement, JSON.stringify({status: 'incompatible', new_failures: ['replacement']}) + ' '.repeat(1024 * 1024));
    fs.renameSync(replacement, reportPath);
    replaced = true;
  };
  const readFile = fs.readFileSync;
  t.mock.method(fs, 'readFileSync', (file, ...args) => {replace(); return readFile(file, ...args);});
  const read = fs.readSync;
  t.mock.method(fs, 'readSync', (fd, buffer, offset, length, position) => {
    replace();
    return read(fd, buffer, offset, Math.min(length, 13), position);
  });
  const writes = await run(t, {status: 'compatible', new_failures: [], padding: '🚀'}, {previous: true});
  assert.equal(replaced, true);
  assert.match(writes[0].body, /no new compatibility failures/);
});

for (const bytes of [1024 * 1024, 1024 * 1024 + 1]) {
  test(`enforces the ${bytes}-byte report boundary and closes its descriptor`, async t => {
    const report = {status: 'incompatible', new_failures: ['test_route'], padding: '🚀'};
    report.padding += ' '.repeat(bytes - Buffer.byteLength(JSON.stringify(report)));
    let descriptor;
    let bytesRead = 0;
    const read = fs.readSync;
    t.mock.method(fs, 'readSync', (...args) => {
      descriptor = args[0];
      const count = read(...args);
      bytesRead += count;
      return count;
    });
    const writes = await run(t, report, {previous: true});
    assert.match(writes[0].body, bytes === 1024 * 1024 ? /new or changed failures/ : /could not be evaluated/);
    assert.ok(bytesRead <= 1024 * 1024 + 1);
    assert.throws(() => fs.fstatSync(descriptor), {code: 'EBADF'});
  });
}
