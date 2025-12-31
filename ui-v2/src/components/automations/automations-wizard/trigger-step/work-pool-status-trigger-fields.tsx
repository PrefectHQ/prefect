import { useFormContext, useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { DurationInput } from "@/components/ui/duration-input";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { WorkPoolMultiSelect } from "@/components/work-pools/work-pool-multi-select";
import { PostureSelect } from "./posture-select";

const WORK_POOL_STATUSES = [
	{ value: "prefect.work-pool.ready", label: "Ready" },
	{ value: "prefect.work-pool.not-ready", label: "Not Ready" },
	{ value: "prefect.work-pool.paused", label: "Paused" },
];

type Match = Record<string, string | string[]> | undefined;

// Extract work pool IDs from match['prefect.resource.id']
function extractWorkPoolIdsFromMatch(match: Match): string[] {
	if (!match) return [];

	const resourceIds = match["prefect.resource.id"];
	if (!resourceIds) return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	return ids
		.filter((id) => id.startsWith("prefect.work-pool."))
		.map((id) => id.replace("prefect.work-pool.", ""));
}

// Build match object with work pool IDs
function buildMatch(workPoolIds: string[]): Match {
	if (workPoolIds.length === 0) {
		return {
			"prefect.resource.id": "prefect.work-pool.*",
		};
	}

	return {
		"prefect.resource.id": workPoolIds.map((id) => `prefect.work-pool.${id}`),
	};
}

export const WorkPoolStatusTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	const match = useWatch<AutomationWizardSchema>({
		name: "trigger.match",
	}) as Match;

	const selectedWorkPoolIds = extractWorkPoolIdsFromMatch(match);

	const handleWorkPoolToggle = (workPoolId: string) => {
		const currentWorkPoolIds = selectedWorkPoolIds;
		const newWorkPoolIds = currentWorkPoolIds.includes(workPoolId)
			? currentWorkPoolIds.filter((id) => id !== workPoolId)
			: [...currentWorkPoolIds, workPoolId];

		form.setValue("trigger.match", buildMatch(newWorkPoolIds));
	};

	return (
		<div className="space-y-4">
			<FormItem>
				<FormLabel>Work Pools</FormLabel>
				<FormControl>
					<WorkPoolMultiSelect
						selectedWorkPoolIds={selectedWorkPoolIds}
						onToggleWorkPool={handleWorkPoolToggle}
						emptyMessage="All work pools"
					/>
				</FormControl>
			</FormItem>

			<FormItem>
				<FormLabel>Work Pool</FormLabel>
				<div className="grid grid-cols-[10rem_1fr] gap-2">
					<PostureSelect />
					<FormField
						control={form.control}
						name="trigger.expect"
						render={({ field }) => {
							const selectedStatus = field.value?.[0];
							return (
								<FormControl>
									<Select
										value={selectedStatus ?? ""}
										onValueChange={(value) => field.onChange([value])}
									>
										<SelectTrigger aria-label="select status">
											<SelectValue placeholder="Select status" />
										</SelectTrigger>
										<SelectContent>
											{WORK_POOL_STATUSES.map((status) => (
												<SelectItem key={status.value} value={status.value}>
													{status.label}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</FormControl>
							);
						}}
					/>
				</div>
			</FormItem>

			{posture === "Proactive" && (
				<FormField
					control={form.control}
					name="trigger.within"
					render={({ field }) => (
						<FormItem>
							<FormLabel>For</FormLabel>
							<FormControl>
								<DurationInput
									value={field.value ?? 30}
									onChange={field.onChange}
									min={0}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			)}
		</div>
	);
};
