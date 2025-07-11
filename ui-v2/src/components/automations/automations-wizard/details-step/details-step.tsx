import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

export const DetailsStep = () => {
	const form = useFormContext<AutomationWizardSchema>();

	return (
		<div className="flex flex-col gap-4">
			<FormField
				control={form.control}
				name="name"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Automation Name</FormLabel>
						<FormControl>
							<Input type="text" {...field} value={field.value ?? ""} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>

			<FormField
				control={form.control}
				name="description"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Description (Optional)</FormLabel>
						<FormControl>
							<Input type="text" {...field} value={field.value ?? ""} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
};
