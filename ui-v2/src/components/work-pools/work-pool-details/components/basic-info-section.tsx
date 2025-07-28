import type { WorkPool } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { KeyValueDisplay } from "@/components/ui/key-value-display";
import { WorkPoolStatusBadge } from "@/components/work-pools/work-pool-status-badge";
import { toTitleCase } from "@/lib/schema-utils";

interface BasicInfoSectionProps {
	workPool: WorkPool;
}

export function BasicInfoSection({ workPool }: BasicInfoSectionProps) {
	const items = [
		{
			key: "Status",
			value: <WorkPoolStatusBadge status={workPool.status || "NOT_READY"} />,
		},
		{
			key: "Description",
			value: workPool.description || "—",
			hidden: !workPool.description,
		},
		{
			key: "Type",
			value: workPool.type ? toTitleCase(workPool.type) : "—",
		},
		{
			key: "Concurrency Limit",
			value: workPool.concurrency_limit
				? String(workPool.concurrency_limit)
				: "Unlimited",
		},
		{
			key: "Created",
			value: workPool.created ? <FormattedDate date={workPool.created} /> : "—",
		},
		{
			key: "Last Updated",
			value: workPool.updated ? <FormattedDate date={workPool.updated} /> : "—",
		},
	];

	return (
		<div>
			<h3 className="mb-4 text-lg font-semibold">Basic Information</h3>
			<KeyValueDisplay items={items} />
		</div>
	);
}
