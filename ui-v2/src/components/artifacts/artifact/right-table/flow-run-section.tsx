import { FlowRun } from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";
import humanizeDuration from "humanize-duration";
import { useMemo } from "react";

type FlowRunSectionProps = {
	flowRun: FlowRun;
	showHr: boolean;
};

export const FlowRunSection = ({ flowRun, showHr }: FlowRunSectionProps) => {
	const flowRunStartTime = useMemo(() => {
		const date = new Date(flowRun.start_time ?? "");
		return formatDate(date, "dateTime");
	}, [flowRun.start_time]);

	const flowRunCreated = useMemo(() => {
		const date = new Date(flowRun.created ?? "");
		return formatDate(date, "dateTime");
	}, [flowRun.created]);

	const flowRunUpdated = useMemo(() => {
		const date = new Date(flowRun.updated ?? "");
		return formatDate(date, "dateTime");
	}, [flowRun.updated]);

	const flowRunDuration = useMemo(() => {
		return humanizeDuration(Math.ceil(flowRun.estimated_run_time) * 1000);
	}, [flowRun.estimated_run_time]);
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
				className="text-muted-foreground mt-1 flex items-center"
			>
				<Icon id="Calendar" className="inline w-4 mr-2" />{" "}
				{flowRunStartTime ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Duration
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				<Icon id="Clock" className="inline w-4 mr-2" /> {flowRunDuration ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Created
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{flowRunCreated ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Last Updated
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{flowRunUpdated ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Tags
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{(flowRun.tags?.length ?? 0 > 0)
					? flowRun.tags?.map((tag) => (
							<span key={tag} className="bg-gray-100 p-1 mx-1 mt-1 rounded">
								{tag}
							</span>
						))
					: "None"}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				State Message
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{flowRun.state?.message ?? "None"}
			</Typography>
			{showHr && <hr className="mt-4" />}
		</div>
	);
};
