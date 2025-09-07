import { useEffect } from "react";
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
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";

import {
	DEFAULT_VALUES,
	useCreateWorkPoolQueueForm,
} from "./use-create-work-pool-queue-form";

type WorkPoolQueueCreateDialogProps = {
	workPoolName: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSubmit: () => void;
};

export const WorkPoolQueueCreateDialog = ({
	workPoolName,
	open,
	onOpenChange,
	onSubmit,
}: WorkPoolQueueCreateDialogProps) => {
	const { form, isLoading, create } = useCreateWorkPoolQueueForm({
		workPoolName,
		onSubmit,
	});

	useEffect(() => {
		if (open) {
			form.reset(DEFAULT_VALUES);
		}
	}, [open, form]);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>Create Work Queue</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(create)(e)}
						className="space-y-4"
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
												<button type="button" className="cursor-help">
													<Icon id="Info" className="size-4" />
												</button>
											</TooltipTrigger>
											<TooltipContent>
												<p className="text-xs">
													Work on higher priority queues is executed first.
													Lower numbers have higher priority.
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
						<DialogFooter>
							<DialogTrigger asChild>
								<Button variant="outline">Cancel</Button>
							</DialogTrigger>
							<Button type="submit" loading={isLoading}>
								Create Work Queue
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
