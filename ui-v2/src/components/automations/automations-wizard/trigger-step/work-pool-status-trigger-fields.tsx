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

// Status options with their corresponding event arrays (matching Vue implementation)
// "not_ready" maps to two events for backwards compatibility
const WORK_POOL_STATUSES = [
	{ value: "ready", label: "Ready", events: ["prefect.work-pool.ready"] },
	{
		value: "not_ready",
		label: "Not Ready",
		events: ["prefect.work-pool.not-ready", "prefect.work-pool.not_ready"],
	},
	{ value: "paused", label: "Paused", events: ["prefect.work-pool.paused"] },
] as const;

// Get status value from events array (for reading from form state)
function getStatusFromEvents(events: string[] | undefined): string {
	if (!events || events.length === 0) return "not_ready";

	for (const status of WORK_POOL_STATUSES) {
		if (status.events.some((e) => events.includes(e))) {
			return status.value;
		}
	}
	return "not_ready";
}

// Get events for a status value
function getEventsForStatus(statusValue: string): string[] {
	const status = WORK_POOL_STATUSES.find((s) => s.value === statusValue);
	return status ? [...status.events] : [];
}

// Get events for all statuses EXCEPT the given one (for Proactive expect)
function getEventsExceptStatus(statusValue: string): string[] {
	return WORK_POOL_STATUSES.filter((s) => s.value !== statusValue).flatMap(
		(s) => [...s.events],
	);
}

type Match = Record<string, string | string[]> | undefined;

// Extract work pool IDs from match['prefect.resource.id']
// Returns empty array for wildcard "prefect.work-pool.*" (meaning "all work pools")
function extractWorkPoolIdsFromMatch(match: Match): string[] {
	if (!match) return [];

	const resourceIds = match["prefect.resource.id"];
	if (!resourceIds) return [];

	// Handle wildcard case - "all work pools" means no specific pools selected
	if (resourceIds === "prefect.work-pool.*") return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	return ids
		.filter(
			(id) =>
				id.startsWith("prefect.work-pool.") && id !== "prefect.work-pool.*",
		)
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

// Status select component that handles posture-dependent behavior
const StatusSelect = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });
	const expect = useWatch<AutomationWizardSchema>({ name: "trigger.expect" }) as
		| string[]
		| undefined;
	const after = useWatch<AutomationWizardSchema>({ name: "trigger.after" }) as
		| string[]
		| undefined;

	// Get current status based on posture
	// Reactive: status is in expect, Proactive: status is in after
	const currentStatus =
		posture === "Proactive"
			? getStatusFromEvents(after)
			: getStatusFromEvents(expect);

	const handleStatusChange = (statusValue: string) => {
		const statusEvents = getEventsForStatus(statusValue);
		const otherStatusEvents = getEventsExceptStatus(statusValue);

		if (posture === "Proactive") {
			// Proactive: selected status goes to "after", other statuses go to "expect"
			form.setValue("trigger.after", statusEvents);
			form.setValue("trigger.expect", otherStatusEvents);
		} else {
			// Reactive: selected status goes to "expect", "after" is empty
			form.setValue("trigger.expect", statusEvents);
			form.setValue("trigger.after", []);
		}
	};

	return (
		<Select value={currentStatus} onValueChange={handleStatusChange}>
			<SelectTrigger aria-label="select status" className="min-w-0 flex-1">
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
	);
};

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
				<div className="flex gap-2">
					<PostureSelect />
					<StatusSelect />
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
