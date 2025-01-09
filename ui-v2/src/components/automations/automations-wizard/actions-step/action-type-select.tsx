import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
} from "@/components/ui/form";
import { useFormContext } from "react-hook-form";
import {
	type ActionType,
	type ActionsSchema,
	UNASSIGNED,
} from "./action-type-schemas";

const AUTOMATION_ACTION_TYPES: Record<ActionType, string> = {
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
	const form = useFormContext<ActionsSchema>();
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
							onValueChange={(type) => {
								field.onChange(type);
								// Set default values based on the type selected
								switch (type) {
									case "run-deployment":
									case "pause-deployment":
									case "resume-deployment":
										form.setValue(`actions.${index}.deployment_id`, UNASSIGNED);
										break;
									case "pause-work-queue":
									case "resume-work-queue":
										form.setValue(`actions.${index}.work_queue_id`, UNASSIGNED);
										break;
									case "pause-work-pool":
									case "resume-work-pool":
										form.setValue(`actions.${index}.work_pool_id`, UNASSIGNED);
										break;
									case "pause-automation":
									case "resume-automation":
										form.setValue(`actions.${index}.automation_id`, UNASSIGNED);
										break;
									case "send-notification":
									case "cancel-flow-run":
									case "suspend-flow-run":
									case "resume-flow-run":
									case "change-flow-run-state":
									default:
										break;
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
