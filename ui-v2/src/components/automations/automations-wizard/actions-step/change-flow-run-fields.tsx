import { useFormContext } from "react-hook-form";
import type { components } from "@/api/prefect";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

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
} as const satisfies Record<
	components["schemas"]["StateType"],
	Capitalize<Lowercase<components["schemas"]["StateType"]>>
>;
type FlowStates = keyof typeof FLOW_STATES;

type ChangeFlowRunStateFieldsProps = {
	index: number;
};

export const ChangeFlowRunStateFields = ({
	index,
}: ChangeFlowRunStateFieldsProps) => {
	const form = useFormContext<AutomationWizardSchema>();
	const stateField = form.watch(`actions.${index}.state`);

	return (
		<div>
			<FormField
				control={form.control}
				name={`actions.${index}.state`}
				render={({ field }) => (
					<FormItem>
						<FormLabel>State</FormLabel>
						<FormControl>
							<Select {...field} onValueChange={field.onChange}>
								<SelectTrigger aria-label="select state">
									<SelectValue placeholder="Select state" />
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
			<FormField
				control={form.control}
				name={`actions.${index}.name`}
				render={({ field }) => (
					<FormItem>
						<FormLabel>Name</FormLabel>
						<FormControl>
							<Input
								type="text"
								{...field}
								value={field.value ?? ""}
								placeholder={FLOW_STATES[stateField]}
							/>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
			<FormField
				control={form.control}
				name={`actions.${index}.message`}
				render={({ field }) => (
					<FormItem>
						<FormLabel>Message</FormLabel>
						<FormControl>
							<Textarea
								{...field}
								placeholder="State changed by Automation <id>"
							/>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
};
