import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cva } from "class-variance-authority";

type RunLogsProps = {
	logs: components["schemas"]["Log"][];
};

export const RunLogs = ({ logs }: RunLogsProps) => {
	return (
		<div className="flex flex-col gap-2 ">
			{logs.map((log) => (
				<RunLogRow key={log.id} log={log} />
			))}
		</div>
	);
};

const RunLogRow = ({ log }: { log: components["schemas"]["Log"] }) => {
	return (
		<div className="bg-gray-100 p-2 rounded-md flex flex-row gap-2">
			<div>
				<LogLevelBadge level={log.level} />
			</div>
			<div>{log.message}</div>
		</div>
	);
};

const logLevelBadgeVariants = cva("gap-1", {
	variants: {
		level: {
			CRITICAL: "bg-red-50 text-red-600 hover:bg-red-50",
			ERROR: "bg-red-50 text-red-600 hover:bg-red-50",
			WARNING: "bg-orange-50 text-orange-600 hover:bg-orange-50",
			INFO: "bg-blue-800 text-blue-50 hover:bg-blue-800",
			DEBUG: "bg-gray-50 text-gray-600 hover:bg-gray-50",
			CUSTOM: "bg-gray-50 text-gray-600 hover:bg-gray-50",
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
