import { useVirtualizer } from "@tanstack/react-virtual";
import { cva } from "class-variance-authority";
import { isSameDay } from "date-fns";
import { format } from "date-fns-tz";
import { useEffect, useRef } from "react";
import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils";

type RunLogsProps = {
	logs: components["schemas"]["Log"][];
	taskRun?: components["schemas"]["TaskRun"];
	onBottomReached: () => void;
	virtualize?: boolean;
	className?: string;
};

/**
 * Displays logs from a run in a virtualized list.
 *
 * @param logs - Array of log entries to display
 * @param taskRun - Optional task run information to display with logs
 * @param onBottomReached - Callback function triggered when the user scrolls to the bottom of the logs
 *
 */
export const RunLogs = ({
	logs,
	taskRun,
	onBottomReached,
	virtualize = true,
	className,
}: RunLogsProps) => {
	const parentRef = useRef<HTMLDivElement>(null);
	const virtualizer = useVirtualizer({
		count: logs.length,
		getScrollElement: () => parentRef.current,
		estimateSize: () => 75,
		overscan: 5,
	});

	const virtualItems = virtualize
		? virtualizer.getVirtualItems()
		: Array.from({ length: logs.length }, (_, i) => ({
				index: i,
				size: 75,
				start: i * 75,
			}));

	/**
	 * This effect detects when the user has scrolled to the bottom of the logs.
	 * It works by checking if the last visible virtual item is also the last item in the logs array.
	 * When this condition is met, it calls the bottomReached callback to potentially load more logs.
	 */
	useEffect(() => {
		const [lastItem] = [...virtualItems].reverse();

		if (!lastItem) {
			return;
		}

		if (lastItem.index >= logs.length - 1) {
			onBottomReached();
		}
	}, [logs.length, virtualItems, onBottomReached]);

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
		<div
			ref={parentRef}
			className={cn(
				"bg-gray-100 rounded-md font-mono p-4 overflow-y-auto",
				className,
			)}
			role="log"
		>
			<ol
				className="relative"
				style={{
					height: `${virtualizer.getTotalSize()}px`,
				}}
			>
				{virtualItems.map((virtualRow) => {
					const log = logs[virtualRow.index];
					const shouldShowDivider = showDivider(virtualRow.index);

					return (
						<li
							key={log.id}
							style={{
								position: "absolute",
								top: 0,
								left: 0,
								width: "100%",
								height: `${virtualRow.size}px`,
								transform: `translateY(${virtualRow.start}px)`,
							}}
						>
							{shouldShowDivider && (
								<LogDivider date={new Date(log.timestamp)} />
							)}
							<RunLogRow log={log} taskRunName={taskRun?.name} />
						</li>
					);
				})}
			</ol>
		</div>
	);
};

type RunLogRowProps = {
	log: components["schemas"]["Log"];
	taskRunName?: string;
};

const RunLogRow = ({ log, taskRunName }: RunLogRowProps) => {
	return (
		<div className="grid grid-cols-[84px_minmax(0,1fr)_150px] gap-2 text-sm">
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
		</div>
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
