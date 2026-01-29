import humanizeDuration from "humanize-duration";
import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";
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

			<div className="mt-3 flex flex-col gap-3">
				<KeyValue
					label="Start time"
					value={
						<span className="font-mono flex items-center">
							<Icon id="Calendar" className="inline w-4 mr-2" />
							{startTime ?? "None"}
						</span>
					}
				/>

				<KeyValue
					label="Duration"
					value={
						<span className="font-mono flex items-center">
							<Icon id="Clock" className="inline w-4 mr-2" />
							{duration ?? "None"}
						</span>
					}
				/>

				<KeyValue
					label="Created"
					value={<span className="font-mono">{createdDate ?? "None"}</span>}
				/>

				<KeyValue
					label="Last Updated"
					value={<span className="font-mono">{updatedDate ?? "None"}</span>}
				/>

				<KeyValue
					label="Tags"
					value={
						flowRun.tags && flowRun.tags.length > 0 ? (
							<div className="flex flex-wrap">
								{flowRun.tags.map((tag) => (
									<TagBadge key={tag} tag={tag} />
								))}
							</div>
						) : (
							<span className="font-mono">None</span>
						)
					}
				/>

				<KeyValue
					label="State Message"
					value={
						<span className="font-mono">
							{flowRun.state?.message ?? "None"}
						</span>
					}
				/>
			</div>
		</div>
	);
};
