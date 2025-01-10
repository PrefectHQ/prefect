import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

const DetailsSchema = z
	.object({
		name: z.string(),
		description: z.string().optional(),
	})
	.strict();
type DetailsSchema = z.infer<typeof DetailsSchema>;

type DetailsStepProps = {
	onPrevious: () => void;
	onSave: (values: DetailsSchema) => void;
};

export const DetailsStep = ({ onPrevious, onSave }: DetailsStepProps) => {
	const form = useForm<DetailsSchema>({
		resolver: zodResolver(DetailsSchema),
		defaultValues: {
			name: "",
		},
	});

	const onSubmit = (values: DetailsSchema) => {
		onSave(values);
	};

	return (
		<Card className="p-4 pt-8">
			<Form {...form}>
				<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
					<div className="flex flex-col gap-4">
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Automation Name</FormLabel>
									<FormControl>
										<Input type="text" {...field} />
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
										<Input type="text" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
					</div>

					<div className="mt-6 flex gap-2 justify-end">
						<Button type="button" variant="outline">
							Cancel
						</Button>
						<Button type="button" variant="outline" onClick={onPrevious}>
							Previous
						</Button>
						<Button type="submit" disabled={!form.formState.isValid}>
							Save
						</Button>
					</div>
				</form>
			</Form>
		</Card>
	);
};
