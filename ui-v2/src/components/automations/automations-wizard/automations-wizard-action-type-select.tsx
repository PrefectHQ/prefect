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
	FormMessage,
} from "@/components/ui/form";
import { useFormContext } from "react-hook-form";
import { ActionsSchema } from "./action-type-schemas";

type ActionType = ActionsSchema["type"];

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

export const AutomationsWizardActionTypeSelect = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="type"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Action Type</FormLabel>
					<FormControl>
						<Select {...field} onValueChange={field.onChange}>
							<SelectTrigger>
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
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
