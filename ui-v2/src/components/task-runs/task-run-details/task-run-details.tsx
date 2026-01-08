import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import humanizeDuration from "humanize-duration";
import { buildGetTaskRunResultQuery } from "@/api/artifacts";
import type { TaskRun } from "@/api/task-runs";
import { Icon } from "@/components/ui/icons";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";
import { TagBadge } from "@/components/ui/tag-badge";
import { formatDate } from "@/utils/date";

function formatTaskDate(dateString: string | null | undefined): string {
	if (!dateString) return "N/A";
	return formatDate(dateString, "dateTimeNumeric");
}

function formatTaskDuration(seconds: number | null | undefined): string {
	if (seconds === null || seconds === undefined) return "N/A";
	return humanizeDuration(seconds * 1000, {
		maxDecimalPoints: 2,
		units: ["s"],
	});
}

export type TaskRunDetailsProps = {
	taskRun: TaskRun | null | undefined;
};

export const TaskRunDetails = ({ taskRun }: TaskRunDetailsProps) => {
	const { data: resultArtifact } = useQuery({
		...buildGetTaskRunResultQuery(taskRun?.id ?? ""),
		enabled: !!taskRun?.id,
	});

	if (!taskRun) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-4 rounded-md">
				<span className="text-gray-500">No task run details available</span>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-2 p-2 text-xs">
			{taskRun.flow_run_id ? (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-gray-500">Flow Run</dt>
					<dd>
						<Link
							to="/runs/flow-run/$id"
							params={{ id: taskRun.flow_run_id }}
							className="text-blue-500 hover:underline cursor-pointer flex items-center"
						>
							<Icon id="ExternalLink" className="mr-1 size-4" />
							{taskRun.flow_run_name}
						</Link>
					</dd>
				</dl>
			) : (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-gray-500">Flow Run</dt>
					<dd>None</dd>
				</dl>
			)}

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Start Time</dt>
				<dd className="font-mono">
					{taskRun.start_time ? formatTaskDate(taskRun.start_time) : "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Duration</dt>
				<dd className="">
					<span className="flex items-center">
						<Icon id="Clock" className="mr-1 size-4" />
						{taskRun.total_run_time !== null &&
						taskRun.total_run_time !== undefined
							? formatTaskDuration(taskRun.total_run_time)
							: "None"}
					</span>
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Run Count</dt>
				<dd className="">{taskRun.run_count ?? 0}</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Estimated Run Time</dt>
				<dd className="">
					{taskRun.estimated_run_time !== null &&
					taskRun.estimated_run_time !== undefined
						? formatTaskDuration(taskRun.estimated_run_time)
						: "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Created</dt>
				<dd className="font-mono">
					{taskRun.created ? formatTaskDate(taskRun.created) : "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Last Updated</dt>
				<dd className="font-mono">
					{taskRun.updated ? formatTaskDate(taskRun.updated) : "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Cache Key</dt>
				<dd className="font-mono">{taskRun.cache_key || "None"}</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Cache Expiration</dt>
				<dd className="font-mono">
					{taskRun.cache_expiration
						? formatTaskDate(taskRun.cache_expiration)
						: "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Dynamic Key</dt>
				<dd className="font-mono">{taskRun.dynamic_key || "None"}</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Task Run ID</dt>
				<dd className="font-mono">{taskRun.id}</dd>
			</dl>

			{resultArtifact?.description && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-muted-foreground">Result</dt>
					<dd>
						<div className="prose max-w-none dark:prose-invert">
							<LazyMarkdown>{resultArtifact.description}</LazyMarkdown>
						</div>
					</dd>
				</dl>
			)}

			<div className="border-t border-gray-200 mt-2 pt-4" />
			<h3 className="text-sm font-semibold mb-2">Task configuration</h3>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className=" text-gray-500">Version</dt>
				<dd className="">{taskRun.task_version || "None"}</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Retries</dt>
				<dd className="">
					{taskRun.empirical_policy?.retries?.toString() ?? "0"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Retry Delay</dt>
				<dd className="">
					{typeof taskRun.empirical_policy?.retry_delay === "number"
						? formatTaskDuration(taskRun.empirical_policy.retry_delay)
						: "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className="text-gray-500">Retry Jitter Factor</dt>
				<dd className="">
					{taskRun.empirical_policy?.retry_jitter_factor !== null &&
					taskRun.empirical_policy?.retry_jitter_factor !== undefined
						? taskRun.empirical_policy.retry_jitter_factor.toString()
						: "None"}
				</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className=" text-gray-500">Tags</dt>
				<dd className="">
					{taskRun.tags && taskRun.tags.length > 0 ? (
						<div className="flex flex-wrap gap-1">
							{taskRun.tags.map((tag) => (
								<TagBadge key={tag} tag={tag} />
							))}
						</div>
					) : (
						"None"
					)}
				</dd>
			</dl>
		</div>
	);
};
