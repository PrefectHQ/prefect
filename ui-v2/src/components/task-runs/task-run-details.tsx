import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { formatDate } from "@/utils/date";
import humanizeDuration from "humanize-duration";
import React from "react";
import { DetailItem } from "./detail-item";

type TaskRun = components["schemas"]["TaskRun"];

export type TaskRunDetailsProps = {
	taskRun: TaskRun;
};

export const TaskRunDetails = ({ taskRun }: TaskRunDetailsProps) => {
	if (!taskRun) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-4 rounded-md">
				<span className="text-gray-500">No task run details available</span>
			</div>
		);
	}

	// Inline helper functions
	function formatTaskDate(dateString: string | null | undefined): string {
		if (!dateString) return "N/A";
		return formatDate(dateString, "dateTimeNumericShort");
	}

	function formatTaskDuration(seconds: number | null | undefined): string {
		if (seconds === null || seconds === undefined) return "N/A";
		return humanizeDuration(seconds, { maxDecimalPoints: 2, units: ["s"] });
	}

	return (
		<Card className="flex flex-col gap-4 p-4 text-sm">
			<DetailItem
				label="Flow Run"
				value={
					<span className="text-blue-500 hover:underline cursor-pointer flex items-center">
						<Icon id="ExternalLink" className="mr-1 size-4" />
						{taskRun.name ? taskRun.name.split("-")[0] : "Flow Run"}
					</span>
				}
			/>

			<DetailItem
				label="Start Time"
				value={formatTaskDate(taskRun.start_time)}
				monospace
			/>

			<DetailItem
				label="Duration"
				value={
					<span className="flex items-center">
						<Icon id="Clock" className="mr-1 size-4" />
						{formatTaskDuration(taskRun.estimated_run_time)}
					</span>
				}
			/>

			<DetailItem label="Run Count" value={taskRun.run_count?.toString()} />

			<DetailItem
				label="Estimated Run Time"
				value={
					taskRun.estimated_run_time
						? formatTaskDuration(taskRun.estimated_run_time)
						: "1s"
				}
			/>

			<DetailItem
				label="Created"
				value={formatTaskDate(taskRun.created)}
				monospace
			/>

			<DetailItem
				label="Last Updated"
				value={formatTaskDate(taskRun.updated)}
				monospace
			/>

			<DetailItem
				label="Cache Key"
				value={taskRun.cache_key || "None"}
				monospace={!!taskRun.cache_key}
			/>

			<DetailItem
				label="Cache Expiration"
				value={
					taskRun.cache_expiration
						? formatTaskDate(taskRun.cache_expiration)
						: "None"
				}
				monospace={!!taskRun.cache_expiration}
			/>

			<DetailItem label="Dynamic Key" value={taskRun.dynamic_key} monospace />

			<DetailItem label="Task Run ID" value={taskRun.id} monospace />

			<div className="border-t border-gray-200 mt-2 pt-4">
				<h3 className="text-md font-semibold mb-2">Task configuration</h3>

				<DetailItem label="Version" value={taskRun.task_version || "None"} />

				<DetailItem
					label="Retries"
					value={taskRun.empirical_policy?.retries?.toString() || "0"}
				/>

				<DetailItem
					label="Retry Delay"
					value={
						typeof taskRun.empirical_policy?.retry_delay === "number"
							? formatTaskDuration(taskRun.empirical_policy.retry_delay)
							: "0s"
					}
				/>

				<DetailItem
					label="Retry Jitter Factor"
					value={
						taskRun.empirical_policy?.retry_jitter_factor?.toString() || "None"
					}
				/>

				<DetailItem
					label="Tags"
					value={
						taskRun.tags && taskRun.tags.length > 0 ? (
							<div className="flex flex-wrap gap-2">
								{taskRun.tags.map((tag, index) => (
									<Badge key={`tag-${index}-${tag}`}>{tag}</Badge>
								))}
							</div>
						) : (
							"None"
						)
					}
				/>
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
