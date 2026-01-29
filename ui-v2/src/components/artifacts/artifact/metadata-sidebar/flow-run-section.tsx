import humanizeDuration from "humanize-duration";
import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import { TagBadge } from "@/components/ui/tag-badge";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";

type FlowRunSectionProps = {
	flowRun: FlowRun;
};

export const FlowRunSection = ({ flowRun }: FlowRunSectionProps) => {
	const startTime = useMemo(() => {
		if (!flowRun.start_time) return null;
		return formatDate(flowRun.start_time, "dateTime");
	}, [flowRun.start_time]);

	const duration = useMemo(() => {
		if (!flowRun.estimated_run_time) return null;
		return humanizeDuration(Math.ceil(flowRun.estimated_run_time) * 1000);
	}, [flowRun.estimated_run_time]);

	const createdDate = useMemo(() => {
		if (!flowRun.created) return null;
		return formatDate(flowRun.created, "dateTime");
	}, [flowRun.created]);

	const updatedDate = useMemo(() => {
		if (!flowRun.updated) return null;
		return formatDate(flowRun.updated, "dateTime");
	}, [flowRun.updated]);

	return (
		<div className="mt-4">
			<Typography variant="bodyLarge" className="font-bold">
				Flow Run
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Start time
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 flex items-center text-foreground"
			>
				<Icon id="Calendar" className="inline w-4 mr-2" />
				{startTime ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Duration
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 flex items-center text-foreground"
			>
				<Icon id="Clock" className="inline w-4 mr-2" />
				{duration ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Created
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{createdDate ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Last Updated
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{updatedDate ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Tags
			</Typography>
			<div className="mt-1 flex flex-wrap">
				{flowRun.tags && flowRun.tags.length > 0 ? (
					flowRun.tags.map((tag) => <TagBadge key={tag} tag={tag} />)
				) : (
					<Typography
						variant="bodySmall"
						fontFamily="mono"
						className="text-foreground"
					>
						None
					</Typography>
				)}
			</div>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				State Message
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{flowRun.state?.message ?? "None"}
			</Typography>
		</div>
	);
};
