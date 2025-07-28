import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { buildListWorkPoolWorkersQuery } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { cn } from "@/lib/utils";

export interface WorkerMonitoringProps {
	workPoolName: string;
	className?: string;
}

export function WorkerMonitoring({
	workPoolName,
	className,
}: WorkerMonitoringProps) {
	const { data: workers = [] } = useSuspenseQuery(
		buildListWorkPoolWorkersQuery(workPoolName),
	);

	const lastPolled = useMemo(() => {
		if (workers.length === 0) return null;

		const heartbeats = workers
			.map((w) => w.last_heartbeat_time)
			.filter((time): time is string => Boolean(time))
			.sort((a, b) => new Date(b).getTime() - new Date(a).getTime());

		return heartbeats[0] || null;
	}, [workers]);

	// Don't render if no workers
	if (workers.length === 0) {
		return null;
	}

	return (
		<div className={cn("space-y-2", className)}>
			<h3 className="text-sm font-medium">Worker Monitoring</h3>
			<div className="text-sm text-muted-foreground">
				{lastPolled ? (
					<div className="flex items-center gap-2">
						<span>Last Polled:</span>
						<FormattedDate date={lastPolled} />
					</div>
				) : (
					<span>No recent worker activity</span>
				)}
			</div>
		</div>
	);
}
