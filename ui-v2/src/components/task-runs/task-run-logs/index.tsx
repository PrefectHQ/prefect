import { buildFilterLogsQuery } from "@/api/logs";
import type { components } from "@/api/prefect";
import { RunLogs } from "@/components/ui/run-logs";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";

type TaskRunLogsProps = {
	taskRun: components["schemas"]["TaskRun"];
};

export const TaskRunLogs = ({ taskRun }: TaskRunLogsProps) => {
	const [levelFilter, setLevelFilter] = useState<number>(0);
	const [sortOrder, setSortOrder] = useState<
		"TIMESTAMP_ASC" | "TIMESTAMP_DESC"
	>("TIMESTAMP_ASC");

	const { data: logs } = useSuspenseQuery(
		buildFilterLogsQuery({
			limit: 200,
			offset: 0,
			sort: sortOrder,
			logs: {
				operator: "and_",
				level: {
					ge_: levelFilter,
				},
				task_run_id: {
					any_: [taskRun.id],
				},
			},
		}),
	);

	return (
		<div className="flex flex-col gap-2">
			<div className="flex flex-row gap-2 justify-end">
				<LogLevelFilter
					levelFilter={levelFilter}
					setLevelFilter={setLevelFilter}
				/>
				<LogSortOrder sortOrder={sortOrder} setSortOrder={setSortOrder} />
			</div>
			<RunLogs taskRun={taskRun} logs={logs} />
		</div>
	);
};

const LEVEL_FILTER_OPTIONS = [
	{ label: "All", value: 0 },
	{ label: "Critical only", value: 50 },
	{ label: "Error and above", value: 40 },
	{ label: "Warning and above", value: 30 },
	{ label: "Info and above", value: 20 },
	{ label: "Debug and above", value: 10 },
] as const;

const LogLevelFilter = ({
	levelFilter,
	setLevelFilter,
}: { levelFilter: number; setLevelFilter: (level: number) => void }) => {
	return (
		<Select
			value={levelFilter.toString()}
			onValueChange={(value) => setLevelFilter(Number(value))}
		>
			<SelectTrigger aria-label="log level filter">
				<span>
					{`Level:
							${
								LEVEL_FILTER_OPTIONS.find(
									(option) => option.value === levelFilter,
								)?.label
							}`}
				</span>
			</SelectTrigger>
			<SelectContent>
				{LEVEL_FILTER_OPTIONS.map((option) => (
					<SelectItem key={option.value} value={option.value.toString()}>
						{option.label}
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
};

const LogSortOrder = ({
	sortOrder,
	setSortOrder,
}: {
	sortOrder: "TIMESTAMP_ASC" | "TIMESTAMP_DESC";
	setSortOrder: (sortOrder: "TIMESTAMP_ASC" | "TIMESTAMP_DESC") => void;
}) => (
	<Select
		value={sortOrder}
		onValueChange={(value) =>
			setSortOrder(value as "TIMESTAMP_ASC" | "TIMESTAMP_DESC")
		}
	>
		<SelectTrigger aria-label="log sort order">
			<SelectValue placeholder="Sort log order" />
		</SelectTrigger>
		<SelectContent>
			<SelectItem value="TIMESTAMP_ASC">Oldest to newest</SelectItem>
			<SelectItem value="TIMESTAMP_DESC">Newest to oldest</SelectItem>
		</SelectContent>
	</Select>
);
