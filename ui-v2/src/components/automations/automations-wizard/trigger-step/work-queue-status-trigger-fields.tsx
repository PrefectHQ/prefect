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
import { PostureSelect } from "./posture-select";
import { WorkPoolsCombobox } from "./work-pools-combobox";
import { WorkQueuesCombobox } from "./work-queues-combobox";

const WORK_QUEUE_STATUSES = [
	{ value: "prefect.work-queue.ready", label: "Ready" },
	{ value: "prefect.work-queue.not-ready", label: "Not Ready" },
	{ value: "prefect.work-queue.paused", label: "Paused" },
];

type MatchRelated = Record<string, string | string[]> | undefined;
type Match = Record<string, string | string[]> | undefined;

function extractWorkPoolIdsFromMatchRelated(
	matchRelated: MatchRelated,
): string[] {
	if (!matchRelated) return [];

	const resourceIds = matchRelated["prefect.resource.id"];
	if (!resourceIds) return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	return ids
		.filter((id) => id.startsWith("prefect.work-pool."))
		.map((id) => id.replace("prefect.work-pool.", ""));
}

function extractWorkQueueIdsFromMatch(match: Match): string[] {
	if (!match) return [];

	const resourceIds = match["prefect.resource.id"];
	if (!resourceIds) return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];

	if (ids.includes("prefect.work-queue.*")) {
		return [];
	}

	return ids
		.filter((id) => id.startsWith("prefect.work-queue."))
		.map((id) => id.replace("prefect.work-queue.", ""));
}

function buildMatchRelated(workPoolIds: string[]): MatchRelated {
	if (workPoolIds.length === 0) {
		return {};
	}

	const resourceIds = workPoolIds.map((id) => `prefect.work-pool.${id}`);

	return {
		"prefect.resource.role": "work-pool",
		"prefect.resource.id": resourceIds,
	};
}

function buildMatch(workQueueIds: string[]): Match {
	if (workQueueIds.length === 0) {
		return { "prefect.resource.id": "prefect.work-queue.*" };
	}

	const resourceIds = workQueueIds.map((id) => `prefect.work-queue.${id}`);

	return {
		"prefect.resource.id": resourceIds,
	};
}

export const WorkQueueStatusTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	const matchRelated = useWatch<AutomationWizardSchema>({
		name: "trigger.match_related",
	}) as MatchRelated;

	const match = useWatch<AutomationWizardSchema>({
		name: "trigger.match",
	}) as Match;

	const selectedWorkPoolIds = extractWorkPoolIdsFromMatchRelated(matchRelated);
	const selectedWorkQueueIds = extractWorkQueueIdsFromMatch(match);

	const handleWorkPoolToggle = (workPoolId: string) => {
		const currentWorkPoolIds = selectedWorkPoolIds;
		const newWorkPoolIds = currentWorkPoolIds.includes(workPoolId)
			? currentWorkPoolIds.filter((id) => id !== workPoolId)
			: [...currentWorkPoolIds, workPoolId];

		form.setValue("trigger.match_related", buildMatchRelated(newWorkPoolIds));
	};

	const handleWorkQueueToggle = (workQueueId: string) => {
		const currentWorkQueueIds = selectedWorkQueueIds;
		const newWorkQueueIds = currentWorkQueueIds.includes(workQueueId)
			? currentWorkQueueIds.filter((id) => id !== workQueueId)
			: [...currentWorkQueueIds, workQueueId];

		form.setValue("trigger.match", buildMatch(newWorkQueueIds));
	};

	return (
		<div className="space-y-4">
			<FormItem>
				<FormLabel>Work Pools</FormLabel>
				<FormControl>
					<WorkPoolsCombobox
						selectedWorkPoolIds={selectedWorkPoolIds}
						onToggleWorkPool={handleWorkPoolToggle}
						emptyMessage="All work pools"
					/>
				</FormControl>
			</FormItem>

			<FormItem>
				<FormLabel>Work Queues</FormLabel>
				<FormControl>
					<WorkQueuesCombobox
						selectedWorkQueueIds={selectedWorkQueueIds}
						onToggleWorkQueue={handleWorkQueueToggle}
						workPoolIds={selectedWorkPoolIds}
						emptyMessage="All work queues"
					/>
				</FormControl>
			</FormItem>

			<FormItem>
				<FormLabel>Work Queue</FormLabel>
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
										<SelectTrigger className="w-full">
											<SelectValue placeholder="Select status" />
										</SelectTrigger>
										<SelectContent>
											{WORK_QUEUE_STATUSES.map((status) => (
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
									value={field.value ?? 0}
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
