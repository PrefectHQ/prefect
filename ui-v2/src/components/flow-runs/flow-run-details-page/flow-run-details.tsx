import type { FlowRun } from "@/api/flow-runs";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { KeyValue } from "@/components/ui/key-value";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";

type FlowRunDetailsProps = {
	flowRun: FlowRun | null | undefined;
};

export function FlowRunDetails({ flowRun }: FlowRunDetailsProps) {
	if (!flowRun) {
		return (
			<div className="flex flex-col gap-2 bg-gray-100 p-4 rounded-md">
				<span className="text-gray-500">No flow run details available</span>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<KeyValue label="Run Count" value={flowRun.run_count} />

			<KeyValue
				label="Created"
				value={<FormattedDate date={flowRun.created} />}
			/>

			{flowRun.created_by?.display_value && (
				<KeyValue label="Created By" value={flowRun.created_by.display_value} />
			)}

			<KeyValue
				label="Last Updated"
				value={<FormattedDate date={flowRun.updated} />}
			/>

			{flowRun.idempotency_key && (
				<KeyValue label="Idempotency Key" value={flowRun.idempotency_key} />
			)}

			{flowRun.tags && flowRun.tags.length > 0 && (
				<KeyValue label="Tags" value={<TagBadgeGroup tags={flowRun.tags} />} />
			)}

			<KeyValue label="Flow Run ID" value={flowRun.id} copyable />

			{flowRun.state?.message && (
				<KeyValue label="State Message" value={flowRun.state.message} />
			)}

			{flowRun.flow_version && (
				<KeyValue label="Flow Version" value={flowRun.flow_version} />
			)}

			{flowRun.empirical_policy?.retries != null && (
				<>
					<KeyValue label="Retries" value={flowRun.empirical_policy.retries} />
					<KeyValue
						label="Retry Delay"
						value={flowRun.empirical_policy.retry_delay}
					/>
				</>
			)}
		</div>
	);
}
