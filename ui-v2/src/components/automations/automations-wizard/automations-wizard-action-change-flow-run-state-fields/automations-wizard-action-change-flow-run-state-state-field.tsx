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
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useFormContext } from "react-hook-form";

const FLOW_STATES = {
	COMPLETED: "Completed",
	RUNNING: "Running",
	SCHEDULED: "Scheduled",
	PENDING: "Pending",
	FAILED: "Failed",
	CANCELLED: "Cancelled",
	CANCELLING: "Cancelling",
	CRASHED: "Crashed",
	PAUSED: "Paused",
} as const;
type FlowStates = keyof typeof FLOW_STATES;

export const AutomationsWizardActionChangeFlowRunStateStateField = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="state"
			render={({ field }) => (
				<FormItem>
					<FormLabel>State</FormLabel>
					<FormControl>
						<Select {...field} onValueChange={field.onChange}>
							<SelectTrigger>
								<SelectValue placeholder="Select action" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectLabel>Actions</SelectLabel>
									{Object.keys(FLOW_STATES).map((key) => (
										<SelectItem key={key} value={key}>
											{FLOW_STATES[key as FlowStates]}
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
