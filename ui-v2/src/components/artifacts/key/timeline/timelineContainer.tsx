import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Typography } from "@/components/ui/typography";
import { TimelineRow } from "./timelineRow";

export type TimelineContainerProps = {
	artifacts: ArtifactWithFlowRunAndTaskRun[];
};

export const TimelineContainer = ({ artifacts }: TimelineContainerProps) => {
	return (
		<div>
			{artifacts.map((artifact) => (
				<TimelineRow key={artifact.id} artifact={artifact} />
			))}
			<div className="flex border-b">
				<div
					className="flex flex-col items-end justify-items-start pt-4"
					style={{ width: "128px", height: "88px" }}
				/>
				<div className="w-10 flex flex-col">
					<div className="w-5 h-full border-r border-gray-200 pt-3">
						<div
							className="size-8 rounded-full bg-white my-5 mx-auto border-2 flex justify-center items-center"
							style={{ margin: "20px calc(50% - 6px)" }}
						>
							<div className="size-4 rounded-full border-2 border-black relative" />
						</div>
					</div>
				</div>
				<div style={{ padding: "33px 0 0 5px" }}>
					<Typography variant="bodyLarge">
						Created <span className="font-bold">{artifacts[0].key}</span>
					</Typography>
				</div>
			</div>
		</div>
	);
};
