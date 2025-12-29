import { useFormContext } from "react-hook-form";
import { RUN_STATES } from "@/api/flow-runs/constants";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { StateSelect } from "@/components/ui/state-select";
import { Textarea } from "@/components/ui/textarea";

type ChangeFlowRunStateFieldsProps = {
	index: number;
};

export const ChangeFlowRunStateFields = ({
	index,
}: ChangeFlowRunStateFieldsProps) => {
	const form = useFormContext<AutomationWizardSchema>();
	const stateField = form.watch(`actions.${index}.state`);

	return (
		<>
			<FormField
				control={form.control}
				name={`actions.${index}.state`}
				render={({ field }) => (
					<FormItem>
						<FormLabel>State</FormLabel>
						<FormControl>
							<StateSelect value={field.value} onValueChange={field.onChange} />
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
								placeholder={stateField ? RUN_STATES[stateField] : undefined}
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
		</>
	);
};
