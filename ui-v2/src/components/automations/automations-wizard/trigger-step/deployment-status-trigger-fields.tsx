import { useCallback, useMemo } from "react";
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
import { AutomationDeploymentCombobox } from "./automation-deployment-combobox";
import { PostureSelect } from "./posture-select";

const SECONDS_IN_DAY = 86400;
const MAX_WITHIN_SECONDS = 30 * SECONDS_IN_DAY;

const DEPLOYMENT_STATUSES = [
	{ value: "prefect.deployment.ready", label: "Ready" },
	{ value: "prefect.deployment.not-ready", label: "Not Ready" },
	{ value: "prefect.deployment.disabled", label: "Disabled" },
];

const DEPLOYMENT_RESOURCE_PREFIX = "prefect.deployment.";
const ALL_DEPLOYMENTS_PATTERN = "prefect.deployment.*";

const extractDeploymentIds = (
	matchValue: string | string[] | undefined,
): string[] => {
	if (!matchValue) return [];
	const values = Array.isArray(matchValue) ? matchValue : [matchValue];
	return values
		.filter((v) => v !== ALL_DEPLOYMENTS_PATTERN)
		.map((v) => v.replace(DEPLOYMENT_RESOURCE_PREFIX, ""));
};

const buildMatchPattern = (deploymentIds: string[]): string | string[] => {
	if (deploymentIds.length === 0) {
		return ALL_DEPLOYMENTS_PATTERN;
	}
	return deploymentIds.map((id) => `${DEPLOYMENT_RESOURCE_PREFIX}${id}`);
};

export const DeploymentStatusTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });
	const matchValue = useWatch<AutomationWizardSchema>({
		name: "trigger.match",
	});

	const selectedDeploymentIds = useMemo(() => {
		const match = matchValue as Record<string, string | string[]> | undefined;
		const resourceId = match?.["prefect.resource.id"];
		return extractDeploymentIds(resourceId);
	}, [matchValue]);

	const handleDeploymentIdsChange = useCallback(
		(deploymentIds: string[]) => {
			const currentMatch = form.getValues("trigger.match") ?? {};
			form.setValue("trigger.match", {
				...currentMatch,
				"prefect.resource.id": buildMatchPattern(deploymentIds),
			});
		},
		[form],
	);

	return (
		<div className="space-y-4">
			<FormItem>
				<FormLabel>Deployments</FormLabel>
				<FormControl>
					<AutomationDeploymentCombobox
						selectedDeploymentIds={selectedDeploymentIds}
						onSelectDeploymentIds={handleDeploymentIdsChange}
					/>
				</FormControl>
			</FormItem>

			<FormItem>
				<FormLabel>Deployment</FormLabel>
				<div
					className="grid gap-2"
					style={{ gridTemplateColumns: "10rem 1fr" }}
				>
					<PostureSelect />
					<FormField
						control={form.control}
						name="trigger.expect"
						render={({ field }) => {
							const selectedStatus = field.value?.[0];
							return (
								<Select
									value={selectedStatus ?? ""}
									onValueChange={(value) => field.onChange([value])}
								>
									<SelectTrigger className="w-full">
										<SelectValue placeholder="Select status" />
									</SelectTrigger>
									<SelectContent>
										{DEPLOYMENT_STATUSES.map((status) => (
											<SelectItem key={status.value} value={status.value}>
												{status.label}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
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
							<FormLabel>Within</FormLabel>
							<FormControl>
								<DurationInput
									value={field.value ?? 0}
									onChange={field.onChange}
									min={10}
									max={MAX_WITHIN_SECONDS}
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
