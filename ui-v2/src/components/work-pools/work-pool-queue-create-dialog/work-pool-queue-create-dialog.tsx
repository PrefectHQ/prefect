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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { useCreateWorkPoolQueueForm } from "./use-create-work-pool-queue-form";

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
										<Input
											type="text"
											autoComplete="off"
											placeholder="my-work-queue"
											{...field}
										/>
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
										<Textarea
											placeholder="Optional description for the work queue"
											{...field}
											value={field.value || ""}
										/>
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
										<Input
											type="number"
											placeholder="Leave empty for no limit"
											{...field}
											value={field.value || ""}
										/>
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
									<FormLabel>Priority</FormLabel>
									<FormControl>
										<Input
											type="number"
											placeholder="Lower values are higher priority"
											{...field}
											value={field.value || ""}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="is_paused"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Start Paused</FormLabel>
									<FormControl>
										<Switch
											className="block"
											checked={field.value}
											onCheckedChange={field.onChange}
										/>
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
