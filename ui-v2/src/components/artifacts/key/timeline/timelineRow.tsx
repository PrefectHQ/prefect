import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";
import { ArtifactTimelineCard } from "./timelineCard";

export type TimelineRowProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const TimelineRow = ({ artifact }: TimelineRowProps) => {
	const [date, time] = formatDate(artifact.created ?? "", "dateTime").split(
		" at ",
	);
	return (
		<div data-testid={`timeline-row-${artifact.id}`} className="flex">
			<div
				className="flex flex-col items-end justify-items-start pt-4"
				style={{ width: "128px" }}
			>
				<Typography variant="body">{time}</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					{date}
				</Typography>
			</div>
			<div className="w-10 flex flex-col">
				<div className="w-5 h-full border-r border-gray-200">
					<div
						className="size-4 rounded-full bg-white my-5 mx-auto border-2"
						style={{ margin: "20px calc(50% + 2px)" }}
					/>
				</div>
			</div>
			<div className="grow mt-1">
				<ArtifactTimelineCard artifact={artifact} />
			</div>
		</div>
	);
};
