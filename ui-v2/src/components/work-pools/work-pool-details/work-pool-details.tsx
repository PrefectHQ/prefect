import { Suspense } from "react";
import { PollStatus } from "@/components/work-pools/poll-status";
import { cn } from "@/lib/utils";

import { BasicInfoSection } from "./components/basic-info-section";
import { JobTemplateSection } from "./components/job-template-section";
import type { WorkPoolDetailsProps } from "./types";

export function WorkPoolDetails({
	workPool,
	alternate = false,
	className,
}: WorkPoolDetailsProps) {
	const spacing = alternate ? "space-y-4" : "space-y-6";

	return (
		<div className={cn(spacing, className)}>
			<BasicInfoSection workPool={workPool} />

			<Suspense
				fallback={
					<div className="text-muted-foreground">Loading poll status...</div>
				}
			>
				<PollStatus workPoolName={workPool.name} />
			</Suspense>

			{workPool.base_job_template?.job_configuration && (
				<JobTemplateSection workPool={workPool} />
			)}
		</div>
	);
}
