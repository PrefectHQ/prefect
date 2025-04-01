import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { formatDate } from "@/utils/date";
import humanizeDuration from "humanize-duration";

type TaskRun = components["schemas"]["TaskRun"];

function formatTaskDate(dateString: string | null | undefined): string {
	if (!dateString) return "N/A";
	return formatDate(dateString, "dateTimeNumericShort");
}

function formatTaskDuration(seconds: number | null | undefined): string {
	if (seconds === null || seconds === undefined) return "N/A";
	return humanizeDuration(seconds, { maxDecimalPoints: 2, units: ["s"] });
}

export type TaskRunsDetailsProps = {
	taskRun: TaskRun | null | undefined;
};

export const TaskRuns = ({ taskRun }: TaskRunsDetailsProps) => {
	if (!taskRun) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-4 rounded-md">
				<span className="text-gray-500">No task run details available</span>
			</div>
		);
	}

	return (
		<Card className="flex flex-col gap-4 p-4 text-sm">
			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-xs text-gray-500">Flow Run</dt>
				<dd className="text-sm">
					<span className="text-blue-500 hover:underline cursor-pointer flex items-center">
						<Icon id="ExternalLink" className="mr-1 size-4" />
						{taskRun.name ? taskRun.name.split("-")[0] : "Flow Run"}
					</span>
				</dd>
			</dl>

			{taskRun.start_time && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Start Time</dt>
					<dd className="font-mono text-sm">
						{formatTaskDate(taskRun.start_time)}
					</dd>
				</dl>
			)}

			{taskRun.estimated_run_time !== null &&
				taskRun.estimated_run_time !== undefined && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className="text-xs text-gray-500">Duration</dt>
						<dd className="text-sm">
							<span className="flex items-center">
								<Icon id="Clock" className="mr-1 size-4" />
								{formatTaskDuration(taskRun.estimated_run_time)}
							</span>
						</dd>
					</dl>
				)}

			{taskRun.run_count !== null && taskRun.run_count !== undefined && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Run Count</dt>
					<dd className="text-sm">{taskRun.run_count.toString()}</dd>
				</dl>
			)}

			{taskRun.estimated_run_time !== null &&
				taskRun.estimated_run_time !== undefined && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className="text-xs text-gray-500">Estimated Run Time</dt>
						<dd className="text-sm">
							{formatTaskDuration(taskRun.estimated_run_time)}
						</dd>
					</dl>
				)}

			{taskRun.created && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Created</dt>
					<dd className="font-mono text-sm">
						{formatTaskDate(taskRun.created)}
					</dd>
				</dl>
			)}

			{taskRun.updated && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Last Updated</dt>
					<dd className="font-mono text-sm">
						{formatTaskDate(taskRun.updated)}
					</dd>
				</dl>
			)}

			{taskRun.cache_key && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Cache Key</dt>
					<dd className="font-mono text-sm">{taskRun.cache_key}</dd>
				</dl>
			)}

			{taskRun.cache_expiration && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Cache Expiration</dt>
					<dd className="font-mono text-sm">
						{formatTaskDate(taskRun.cache_expiration)}
					</dd>
				</dl>
			)}

			{taskRun.dynamic_key && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Dynamic Key</dt>
					<dd className="font-mono text-sm">{taskRun.dynamic_key}</dd>
				</dl>
			)}

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-xs text-gray-500">Task Run ID</dt>
				<dd className="font-mono text-sm">{taskRun.id}</dd>
			</dl>

			<div className="border-t border-gray-200 mt-2 pt-4">
				<h3 className="text-md font-semibold mb-2">Task configuration</h3>

				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Version</dt>
					<dd className="text-sm">{taskRun.task_version || "None"}</dd>
				</dl>

				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Retries</dt>
					<dd className="text-sm">
						{taskRun.empirical_policy?.retries?.toString() || "0"}
					</dd>
				</dl>

				{typeof taskRun.empirical_policy?.retry_delay === "number" && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className="text-xs text-gray-500">Retry Delay</dt>
						<dd className="text-sm">
							{formatTaskDuration(taskRun.empirical_policy.retry_delay)}
						</dd>
					</dl>
				)}

				{taskRun.empirical_policy?.retry_jitter_factor !== null &&
					taskRun.empirical_policy?.retry_jitter_factor !== undefined && (
						<dl className="flex flex-col gap-1 mb-2">
							<dt className="text-xs text-gray-500">Retry Jitter Factor</dt>
							<dd className="text-sm">
								{taskRun.empirical_policy.retry_jitter_factor.toString()}
							</dd>
						</dl>
					)}

				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-xs text-gray-500">Tags</dt>
					<dd className="text-sm">
						{taskRun.tags && taskRun.tags.length > 0 ? (
							<div className="flex flex-wrap gap-2">
								{taskRun.tags.map((tag, index) => (
									<Badge key={`tag-${index}-${tag}`}>{tag}</Badge>
								))}
							</div>
						) : (
							"None"
						)}
					</dd>
				</dl>
			</div>

			{taskRun.task_inputs && Object.keys(taskRun.task_inputs).length > 0 && (
				<div className="mt-2 pt-4">
					<h3 className="text-md font-semibold mb-2">Task Inputs</h3>
					<pre className="bg-gray-100 p-2 rounded-md text-sm overflow-auto">
						{JSON.stringify(taskRun.task_inputs, null, 2)}
					</pre>
				</div>
			)}
		</Card>
	);
};
