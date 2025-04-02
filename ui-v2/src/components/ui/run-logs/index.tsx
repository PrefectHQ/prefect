import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cva } from "class-variance-authority";
import { isSameDay } from "date-fns";
import { format } from "date-fns-tz";
import { Fragment } from "react";

type RunLogsProps = {
	logs: components["schemas"]["Log"][];
	taskRun?: components["schemas"]["TaskRun"];
};

export const RunLogs = ({ logs, taskRun }: RunLogsProps) => {
	const showDivider = (index: number): boolean => {
		if (index === 0) {
			return true;
		}

		const previous = logs[index - 1];
		const current = logs[index];

		return !isSameDay(previous.timestamp, current.timestamp);
	};

	if (logs.length === 0) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-2 rounded-md font-mono">
				<span className="text-gray-500">No logs found</span>
			</div>
		);
	}
	return (
		<ol className="flex flex-col gap-4 bg-gray-100 p-2 rounded-md font-mono">
			{logs.map((log, index) => (
				<Fragment key={log.id}>
					{showDivider(index) && <LogDivider date={new Date(log.timestamp)} />}
					<RunLogRow key={log.id} log={log} taskRunName={taskRun?.name} />
				</Fragment>
			))}
		</ol>
	);
};

type RunLogRowProps = {
	log: components["schemas"]["Log"];
	taskRunName?: string;
};

const RunLogRow = ({ log, taskRunName }: RunLogRowProps) => {
	return (
		<li className="grid grid-cols-[84px_minmax(0,1fr)_150px] gap-2 text-sm">
			<div>
				<LogLevelBadge level={log.level} />
			</div>
			<div className="select-auto whitespace-pre-wrap break-words">
				{log.message}
			</div>
			<div className="text-xs grid grid-cols-1 gap-1 justify-items-end text-gray-500 truncate">
				<span>{format(log.timestamp, "pp")}</span>
				{taskRunName && <span>{taskRunName}</span>}
				<span className="font-bold break-all whitespace-normal">
					{log.name}
				</span>
			</div>
		</li>
	);
};

const logLevelBadgeVariants = cva("gap-1", {
	variants: {
		level: {
			CRITICAL: "bg-red-600 text-red-50 hover:bg-red-600",
			ERROR: "bg-red-600 text-red-50 hover:bg-red-600",
			WARNING: "bg-orange-600 text-orange-50 hover:bg-orange-600",
			INFO: "bg-sky-600 text-blue-50 hover:bg-sky-600",
			DEBUG: "bg-gray-700 text-gray-50 hover:bg-gray-700",
			CUSTOM: "bg-gray-700 text-gray-50 hover:bg-gray-700",
		} satisfies Record<LogLevel, string>,
	},
});

export const LogLevelBadge = ({ level }: { level: number }) => {
	const levelLabel = logLevelLabel(level);
	return (
		<Badge className={logLevelBadgeVariants({ level: levelLabel })}>
			{levelLabel}
		</Badge>
	);
};

type LogLevel = "CRITICAL" | "ERROR" | "WARNING" | "INFO" | "DEBUG" | "CUSTOM";

function logLevelLabel(level: number): LogLevel {
	const [first] = level.toString();

	switch (first) {
		case "5":
			return "CRITICAL";
		case "4":
			return "ERROR";
		case "3":
			return "WARNING";
		case "2":
			return "INFO";
		case "1":
			return "DEBUG";
		default:
			return "CUSTOM";
	}
}

const LogDivider = ({ date }: { date: Date }) => {
	return (
		<div className="flex flex-row justify-center items-center gap-2">
			<div className="h-[1px] w-full bg-gray-300" />
			<span className="text-xs text-gray-500 whitespace-nowrap">
				{format(date, "MMM d, yyyy")}
			</span>
			<div className="h-[1px] w-full bg-gray-300" />
		</div>
	);
};
