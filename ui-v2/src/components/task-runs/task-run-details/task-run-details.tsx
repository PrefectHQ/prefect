import humanizeDuration from "humanize-duration";
import type { TaskRun } from "@/api/task-runs";
import { Icon } from "@/components/ui/icons";
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
	if (!taskRun) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-4 rounded-md">
				<span className="text-gray-500">No task run details available</span>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-2 p-2 text-xs">
			{taskRun.flow_run_name && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-gray-500">Flow Run</dt>
					<dd>
						<span className="text-blue-500 hover:underline cursor-pointer flex items-center">
							<Icon id="ExternalLink" className="mr-1 size-4" />
							{taskRun.flow_run_name}
						</span>
					</dd>
				</dl>
			)}

			{taskRun.start_time && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className="text-gray-500">Start Time</dt>
					<dd className="font-mono">{formatTaskDate(taskRun.start_time)}</dd>
				</dl>
			)}

			{taskRun.estimated_run_time !== null &&
				taskRun.estimated_run_time !== undefined && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className="text-gray-500">Duration</dt>
						<dd className="">
							<span className="flex items-center">
								<Icon id="Clock" className="mr-1 size-4" />
								{formatTaskDuration(taskRun.total_run_time)}
							</span>
						</dd>
					</dl>
				)}

			{taskRun.run_count !== null && taskRun.run_count !== undefined && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Run Count</dt>
					<dd className="">{taskRun.run_count.toString()}</dd>
				</dl>
			)}

			{taskRun.estimated_run_time !== null &&
				taskRun.estimated_run_time !== undefined && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className=" text-gray-500">Estimated Run Time</dt>
						<dd className="">
							{formatTaskDuration(taskRun.estimated_run_time)}
						</dd>
					</dl>
				)}

			{taskRun.created && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Created</dt>
					<dd className="font-mono ">{formatTaskDate(taskRun.created)}</dd>
				</dl>
			)}

			{taskRun.updated && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Last Updated</dt>
					<dd className="font-mono ">{formatTaskDate(taskRun.updated)}</dd>
				</dl>
			)}

			{taskRun.cache_key && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Cache Key</dt>
					<dd className="font-mono ">{taskRun.cache_key}</dd>
				</dl>
			)}

			{taskRun.cache_expiration && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Cache Expiration</dt>
					<dd className="font-mono ">
						{formatTaskDate(taskRun.cache_expiration)}
					</dd>
				</dl>
			)}

			{taskRun.dynamic_key && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Dynamic Key</dt>
					<dd className="font-mono ">{taskRun.dynamic_key}</dd>
				</dl>
			)}

			<dl className="flex flex-col gap-1 mb-2">
				<dt className=" text-gray-500">Task Run ID</dt>
				<dd className="font-mono ">{taskRun.id}</dd>
			</dl>

			<div className="border-t border-gray-200 mt-2 pt-4" />
			<h3 className="text-sm font-semibold mb-2">Task configuration</h3>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className=" text-gray-500">Version</dt>
				<dd className="">{taskRun.task_version || "None"}</dd>
			</dl>

			<dl className="flex flex-col gap-1 mb-2">
				<dt className=" text-gray-500">Retries</dt>
				<dd className="">
					{taskRun.empirical_policy?.retries?.toString() || "0"}
				</dd>
			</dl>

			{typeof taskRun.empirical_policy?.retry_delay === "number" && (
				<dl className="flex flex-col gap-1 mb-2">
					<dt className=" text-gray-500">Retry Delay</dt>
					<dd className="">
						{formatTaskDuration(taskRun.empirical_policy.retry_delay)}
					</dd>
				</dl>
			)}

			{taskRun.empirical_policy?.retry_jitter_factor !== null &&
				taskRun.empirical_policy?.retry_jitter_factor !== undefined && (
					<dl className="flex flex-col gap-1 mb-2">
						<dt className=" text-gray-500">Retry Jitter Factor</dt>
						<dd className="">
							{taskRun.empirical_policy.retry_jitter_factor.toString()}
						</dd>
					</dl>
				)}

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
