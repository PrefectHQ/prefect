import { execSync } from "node:child_process";
import path from "node:path";

export interface SimpleTaskResult {
	flow_run_id: string;
	flow_run_name: string;
	task_run_ids: string[];
	task_run_names: string[];
}

export interface ParentChildResult {
	parent_flow_run_id: string;
	parent_flow_run_name: string;
	child_flow_run_id: string;
	child_flow_run_name: string;
	task_run_ids: string[];
	task_run_names: string[];
}

export interface FlowWithTasksResult {
	flow_run_id: string;
	flow_run_name: string;
	task_run_ids: string[];
	task_run_names: string[];
}

const REPO_ROOT = path.resolve(__dirname, "../..");

function runScenario(scenario: string, prefix: string): string {
	try {
		const stdout = execSync(
			`uv run python ui-v2/e2e/helpers/run_flows.py --scenario ${scenario} --prefix ${prefix}`,
			{
				cwd: REPO_ROOT,
				env: { ...process.env },
				encoding: "utf-8",
				timeout: 120_000,
			},
		);
		return stdout.trim();
	} catch (error: unknown) {
		const err = error as { stderr?: string; message?: string };
		const stderr = err.stderr ?? err.message ?? "Unknown error";
		throw new Error(`Failed to run scenario '${scenario}': ${stderr}`);
	}
}

export function runSimpleTask(prefix: string): SimpleTaskResult {
	const output = runScenario("simple-task", prefix);
	return JSON.parse(output) as SimpleTaskResult;
}

export function runParentChild(prefix: string): ParentChildResult {
	const output = runScenario("parent-child", prefix);
	return JSON.parse(output) as ParentChildResult;
}

export function runFlowWithTasks(prefix: string): FlowWithTasksResult {
	const output = runScenario("flow-with-tasks", prefix);
	return JSON.parse(output) as FlowWithTasksResult;
}
