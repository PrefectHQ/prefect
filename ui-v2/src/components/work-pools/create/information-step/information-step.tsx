import { useFormContext } from "react-hook-form";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { WorkPoolInformationFormValues } from "./schema";

export function InformationStep() {
	const form = useFormContext<WorkPoolInformationFormValues>();

	return (
		<>
			<FormField
				control={form.control}
				name="name"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Name</FormLabel>
						<FormControl>
							<Input {...field} />
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
							<Textarea
								{...field}
								value={field.value ?? ""}
								rows={7}
								placeholder="Enter a description for your work pool"
							/>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>

			<FormField
				control={form.control}
				name="concurrencyLimit"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Flow Run Concurrency (Optional)</FormLabel>
						<FormControl>
							<Input
								{...field}
								type="number"
								min={0}
								placeholder="Unlimited"
								value={field.value ?? ""}
								onChange={(e) => {
									const value = e.target.value;
									field.onChange(value === "" ? null : Number(value));
								}}
							/>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</>
	);
}
