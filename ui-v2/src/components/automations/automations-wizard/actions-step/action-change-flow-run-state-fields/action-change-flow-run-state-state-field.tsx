import { type ActionsSchema } from "@/components/automations/automations-wizard/actions-step/action-type-schemas";
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
import { FLOW_STATES, type FlowStates } from "./flow-states";

type ActionChangeFlowRunStateStateFieldProps = {
	index: number;
};

export const ActionChangeFlowRunStateStateField = ({
	index,
}: ActionChangeFlowRunStateStateFieldProps) => {
	const form = useFormContext<ActionsSchema>();
	return (
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
	);
};
