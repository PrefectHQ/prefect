import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateTaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
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
	tag: z.string().min(1),
	/** Coerce to solve common issue of transforming a string number to a number type */
	concurrency_limit: z
		.number()
		.default(0)
		.or(z.string())
		.pipe(z.coerce.number()),
});

const DEFAULT_VALUES = {
	tag: "",
	concurrency_limit: 0,
} as const;

type TaskRunConcurrencyLimitsCreateDialogProps = {
	onOpenChange: (open: boolean) => void;
	onSubmit: () => void;
};

export const TaskRunConcurrencyLimitsCreateDialog = ({
	onOpenChange,
	onSubmit,
}: TaskRunConcurrencyLimitsCreateDialogProps) => {
	const { createTaskRunConcurrencyLimit, isPending } =
		useCreateTaskRunConcurrencyLimit();

	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});

	const handleAddLimit = (values: z.infer<typeof formSchema>) => {
		createTaskRunConcurrencyLimit(values, {
			onSuccess: () => {
				toast.success("Concurrency limit added");
			},
			onError: (error) => {
				const message = error.message || "Unknown error while updating limit.";
				form.setError("root", { message });
			},
			onSettled: () => {
				form.reset(DEFAULT_VALUES);
				onSubmit();
			},
		});
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>Add Task Run Concurrency Limit</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(handleAddLimit)(e)}
						className="space-y-4"
					>
						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						<FormField
							control={form.control}
							name="tag"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Tag</FormLabel>
									<FormControl>
										<Input type="text" autoComplete="off" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="concurrency_limit"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Concurrency Limit</FormLabel>
									<FormControl>
										<Input type="number" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<DialogFooter>
							<DialogTrigger asChild>
								<Button variant="outline">Close</Button>
							</DialogTrigger>
							<Button type="submit" loading={isPending}>
								Add
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
