import { useVirtualizer } from "@tanstack/react-virtual";
import { cva } from "class-variance-authority";
import { isSameDay } from "date-fns";
import { format } from "date-fns-tz";
import { useCallback, useEffect, useRef } from "react";
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

	// Use a ref to store logs for stable getItemKey callback
	const logsRef = useRef(logs);
	logsRef.current = logs;

	const getItemKey = useCallback(
		(index: number) => logsRef.current[index]?.id ?? index,
		[],
	);

	const virtualizer = useVirtualizer({
		count: logs.length,
		getScrollElement: () => parentRef.current,
		estimateSize: () => 75,
		overscan: 5,
		getItemKey,
	});

	// Wrap measureElement in a stable callback to prevent infinite re-renders
	const measureElement = useCallback(
		(el: HTMLElement | null) => {
			if (el) {
				virtualizer.measureElement(el);
			}
		},
		[virtualizer],
	);

	const virtualItems = virtualize
		? virtualizer.getVirtualItems()
		: Array.from({ length: logs.length }, (_, i) => ({
				index: i,
				size: 75,
				start: i * 75,
			}));

	// Get the last visible item index for stable effect dependency
	const lastVisibleIndex = virtualItems.at(-1)?.index;

	/**
	 * This effect detects when the user has scrolled to the bottom of the logs.
	 * It works by checking if the last visible virtual item is also the last item in the logs array.
	 * When this condition is met, it calls the bottomReached callback to potentially load more logs.
	 */
	useEffect(() => {
		if (lastVisibleIndex === undefined) {
			return;
		}

		if (lastVisibleIndex >= logs.length - 1) {
			onBottomReached();
		}
	}, [logs.length, lastVisibleIndex, onBottomReached]);

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
			<div className="flex flex-col gap-2 bg-muted p-2 rounded-md font-mono">
				<span className="text-muted-foreground">No logs found</span>
			</div>
		);
	}

	return (
		<div
			ref={parentRef}
			className={cn(
				"bg-muted rounded-md font-mono p-4 overflow-y-auto",
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
							data-index={virtualRow.index}
							ref={measureElement}
							style={{
								position: "absolute",
								top: 0,
								left: 0,
								width: "100%",
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
			<div className="text-xs grid grid-cols-1 gap-1 justify-items-end text-muted-foreground truncate">
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
			<div className="h-[1px] w-full bg-muted-foreground/30" />
			<span className="text-xs text-muted-foreground whitespace-nowrap">
				{format(date, "MMM d, yyyy")}
			</span>
			<div className="h-[1px] w-full bg-muted-foreground/30" />
		</div>
	);
};
