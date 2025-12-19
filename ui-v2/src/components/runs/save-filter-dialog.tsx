import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const formSchema = z.object({
	name: z
		.string()
		.min(1, { message: "Name is required" })
		.max(100, { message: "Name must be 100 characters or less" }),
});

type FormValues = z.infer<typeof formSchema>;

export type SaveFilterDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSave: (name: string) => void;
};

export const SaveFilterDialog = ({
	open,
	onOpenChange,
	onSave,
}: SaveFilterDialogProps) => {
	const form = useForm<FormValues>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			name: "",
		},
	});

	useEffect(() => {
		if (open) {
			form.reset({ name: "" });
		}
	}, [open, form]);

	const onSubmit = (values: FormValues) => {
		onSave(values.name);
		onOpenChange(false);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Save Filter</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					Save your current filter configuration for quick access later.
				</DialogDescription>
				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}
						className="space-y-4"
					>
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Filter Name</FormLabel>
									<FormControl>
										<Input
											autoComplete="off"
											placeholder="e.g., Failed runs this week"
											{...field}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<DialogFooter>
							<Button
								type="button"
								variant="outline"
								onClick={() => onOpenChange(false)}
							>
								Cancel
							</Button>
							<Button type="submit">Save</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
