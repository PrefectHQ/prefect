import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useFormContext } from "react-hook-form";

export const AutomationsWizardActionChangeFlowRunStateNameField = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="name"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Name</FormLabel>
					<FormControl>
						<Input type="text" {...field} />
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
