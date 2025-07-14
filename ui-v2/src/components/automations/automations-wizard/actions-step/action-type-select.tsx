import { useFormContext } from "react-hook-form";

import {
	type ActionType,
	type AutomationWizardSchema,
	UNASSIGNED,
} from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
} from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const AUTOMATION_ACTION_TYPES: Partial<Record<ActionType, string>> = {
	"cancel-flow-run": "Cancel a flow run",
	"suspend-flow-run": "Suspend a flow run",
	"resume-flow-run": "Resume a flow run",
	"change-flow-run-state": "Change flow run's state",
	"run-deployment": "Run a deployment",
	"pause-deployment": "Pause a deployment",
	"resume-deployment": "Resume a deployment",
	"pause-work-queue": "Pause a work queue",
	"resume-work-queue": "Resume a work queue",
	"pause-work-pool": "Pause a work pool",
	"resume-work-pool": "Resume a work pool",
	"pause-automation": "Pause an automation",
	"resume-automation": "Resume an automation",
	"send-notification": "Send a notification",
};

export const ActionTypeSelect = ({ index }: { index: number }) => {
	const form = useFormContext<AutomationWizardSchema>();
	return (
		<FormField
			control={form.control}
			name={`actions.${index}.type`}
			render={({ field }) => (
				<FormItem>
					<FormLabel>Action Type</FormLabel>
					<FormControl>
						<Select
							{...field}
							onValueChange={(type: ActionType) => {
								field.onChange(type);
								const defaultActionField = getDefaultActionField({
									index,
									type,
								});
								if (defaultActionField) {
									form.setValue(defaultActionField, UNASSIGNED);
								}
							}}
						>
							<SelectTrigger aria-label="select action">
								<SelectValue placeholder="Select action" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectLabel>Actions</SelectLabel>
									{Object.keys(AUTOMATION_ACTION_TYPES).map((key) => (
										<SelectItem key={key} value={key}>
											{AUTOMATION_ACTION_TYPES[key as ActionType]}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					</FormControl>
				</FormItem>
			)}
		/>
	);
};

/**
 * @returns form field name to be set that is associated with the passed `type` arg
 */
function getDefaultActionField({
	index,
	type,
}: {
	index: number;
	type: ActionType;
}) {
	switch (type) {
		case "run-deployment":
		case "pause-deployment":
		case "resume-deployment":
			return `actions.${index}.deployment_id` as const;
		case "pause-work-queue":
		case "resume-work-queue":
			return `actions.${index}.work_queue_id` as const;
		case "pause-work-pool":
		case "resume-work-pool":
			return `actions.${index}.work_pool_id` as const;
		case "pause-automation":
		case "resume-automation":
			return `actions.${index}.automation_id` as const;
		// TODO: add these back in once we have field names for them
		// case "send-notification":
		// case "cancel-flow-run":
		// case "suspend-flow-run":
		// case "resume-flow-run":
		// case "change-flow-run-state":
		default:
			return null;
	}
}
