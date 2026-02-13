import type { PrefectApiClient } from "../api-client";

export async function createLogs(
	client: PrefectApiClient,
	params: {
		flowRunId: string;
		taskRunId?: string;
		logs: Array<{
			message: string;
			level?: number;
			timestamp?: string;
		}>;
	},
): Promise<void> {
	const logEntries = params.logs.map((log, index) => ({
		name: "prefect.flow_runs",
		level: log.level ?? 20,
		message: log.message,
		timestamp: log.timestamp ?? new Date(Date.now() + index).toISOString(),
		flow_run_id: params.flowRunId,
		task_run_id: params.taskRunId ?? null,
	}));

	const { error } = await client.POST("/logs/", {
		body: logEntries,
	});
	if (error) {
		throw new Error(`Failed to create logs: ${JSON.stringify(error)}`);
	}
}
