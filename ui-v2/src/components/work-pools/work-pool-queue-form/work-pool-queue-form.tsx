import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { useCreateOrEditWorkPoolQueueForm } from "@/components/work-pools/work-pool-queue-create-dialog";

type WorkPoolQueueFormProps = {
	workPoolName: string;
	queueToEdit?: WorkPoolQueue;
	onSubmit: () => void;
	onCancel: () => void;
};

export const WorkPoolQueueForm = ({
	workPoolName,
	queueToEdit,
	onSubmit,
	onCancel,
}: WorkPoolQueueFormProps) => {
	const { form, isLoading, saveOrUpdate } = useCreateOrEditWorkPoolQueueForm({
		workPoolName,
		queueToEdit,
		onSubmit,
	});

	const isEditMode = !!queueToEdit;
	const submitButtonText = isEditMode ? "Save" : "Create";

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => void form.handleSubmit(saveOrUpdate)(e)}
				className="space-y-6"
			>
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				<FormField
					control={form.control}
					name="name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Name</FormLabel>
							<FormControl>
								<Input type="text" autoComplete="off" {...field} />
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
							<FormLabel>Description</FormLabel>
							<FormControl>
								<Textarea {...field} value={field.value || ""} />
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
							<FormLabel>Flow Run Concurrency</FormLabel>
							<FormControl>
								<Input type="number" {...field} value={field.value || ""} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<FormField
					control={form.control}
					name="priority"
					render={({ field }) => (
						<FormItem>
							<FormLabel className="flex items-center gap-2">
								Priority
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											type="button"
											variant="ghost"
											size="icon"
											className="size-5 cursor-help"
										>
											<Icon id="Info" className="size-3.5" />
										</Button>
									</TooltipTrigger>
									<TooltipContent>
										<p className="text-xs">
											Work on higher priority queues is executed first. Lower
											numbers have higher priority.
										</p>
									</TooltipContent>
								</Tooltip>
							</FormLabel>
							<FormControl>
								<Input type="number" {...field} value={field.value || ""} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<div className="flex justify-end gap-2">
					<Button
						type="button"
						variant="outline"
						onClick={onCancel}
						disabled={isLoading}
					>
						Cancel
					</Button>
					<Button type="submit" loading={isLoading}>
						{submitButtonText}
					</Button>
				</div>
			</form>
		</Form>
	);
};
