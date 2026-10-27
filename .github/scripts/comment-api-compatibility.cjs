const fs = require('node:fs');

const marker = '<!-- cloud-api-compatibility -->';

module.exports = async ({github, context, core}) => {
  const run = context.payload.workflow_run;
  const repository = context.repo;
  if (run.path !== '.github/workflows/api-compatibility-tests.yaml') return;
  const {data: latest} = await github.rest.actions.listWorkflowRuns({
    ...repository, workflow_id: run.workflow_id, event: 'pull_request', head_sha: run.head_sha, per_page: 1,
  });
  if (latest.workflow_runs[0]?.id !== run.id || latest.workflow_runs[0]?.run_attempt !== run.run_attempt) return;
  // Resolve the PR from GitHub, never from the artifact uploaded by PR code.
  const pulls = await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit, {
    ...repository, commit_sha: run.head_sha,
  });
  const matching = pulls.filter(pr => pr.state === 'open' &&
    pr.base.repo.full_name === `${repository.owner}/${repository.repo}` &&
    pr.head.repo?.full_name === run.head_repository.full_name && pr.head.sha === run.head_sha);
  if (matching.length !== 1) return;
  const issue_number = matching[0].number;
  const comments = await github.paginate(github.rest.issues.listComments, {...repository, issue_number});
  const previous = comments.find(comment => comment.user.login === 'github-actions[bot]' &&
    comment.body.startsWith(marker));

  let report = {status: 'unavailable'};
  try {
    const path = process.env.COMPATIBILITY_REPORT;
    if (fs.statSync(path).size > 1024 * 1024) throw new Error('Report exceeds size limit');
    report = JSON.parse(fs.readFileSync(path, 'utf8'));
    if (!['compatible', 'incompatible', 'unavailable'].includes(report.status) ||
        (report.status !== 'unavailable' && (!Array.isArray(report.new_failures) ||
          report.new_failures.length > 10000 || report.new_failures.some(name =>
            typeof name !== 'string' || name.length > 2000) ||
          (report.status === 'incompatible') !== (report.new_failures.length > 0)))) {
      throw new Error('Invalid compatibility report');
    }
  } catch (error) {
    core.warning(`Compatibility report unavailable: ${error.message}`);
    report = {status: 'unavailable'};
  }
  if (!previous && report.status !== 'incompatible') return;

  const url = `https://github.com/${repository.owner}/${repository.repo}/actions/runs/${run.id}`;
  let body = `${marker}\n**Cloud API compatibility (advisory)**\n\n`;
  if (report.status === 'incompatible') {
    // Escape artifact content before including it in a privileged bot comment.
    const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;').replaceAll('@', '&#64;');
    body += 'The compatibility suite found new or changed failures against the deployed Cloud API. ' +
      'A maintainer should check whether Cloud needs a corresponding change before merging. ' +
      'This check is non-blocking; contributors do not need to coordinate Cloud changes unless a maintainer asks.\n\n';
    body += report.new_failures.slice(0, 20).map(name => `- <code>${escape(name)}</code>`).join('\n');
    if (report.new_failures.length > 20) body += '\n\nAdditional failures are in the report.';
  } else if (report.status === 'compatible') {
    body += 'The latest run found no new compatibility failures. Existing differences on the base revision are excluded.';
  } else {
    body += 'Compatibility could not be evaluated in the latest run. See the logs for the test or infrastructure error.';
  }
  body += `\n\n[View the report and logs](${url}).`;
  // Recheck after reading artifacts and comments so an obsolete run cannot clear a newer warning.
  const {data: current} = await github.rest.pulls.get({...repository, pull_number: issue_number});
  if (current.state !== 'open' || current.head.sha !== run.head_sha) return;
  if (previous) {
    await github.rest.issues.updateComment({...repository, comment_id: previous.id, body});
  } else {
    await github.rest.issues.createComment({...repository, issue_number, body});
  }
};
