import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";
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

import { useCreateOrEditGlobalConcurrencyLimitForm } from "./use-create-or-edit-global-concurrency-limit-form";

type GlobalConcurrencyLimitsCreateOrEditDialogProps = {
	limitToUpdate?: GlobalConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onSubmit: () => void;
};

export const GlobalConcurrencyLimitsCreateOrEditDialog = ({
	limitToUpdate,
	onOpenChange,
	onSubmit,
}: GlobalConcurrencyLimitsCreateOrEditDialogProps) => {
	const { form, isLoading, saveOrUpdate } =
		useCreateOrEditGlobalConcurrencyLimitForm({
			limitToUpdate,
			onSubmit,
		});

	const dialogTitle = limitToUpdate
		? `Update ${limitToUpdate.name}`
		: "Add Concurrency Limit";

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>{dialogTitle}</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(saveOrUpdate)(e)}
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
							name="limit"
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
						<FormField
							control={form.control}
							name="slot_decay_per_second"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Slot Decay Per Second</FormLabel>
									<FormControl>
										<Input type="number" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						{limitToUpdate && (
							<FormField
								control={form.control}
								name="active_slots"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Active Slots</FormLabel>
										<FormControl>
											<Input type="number" {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						)}
						<FormField
							control={form.control}
							name="active"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Active</FormLabel>
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
								<Button variant="outline">Close</Button>
							</DialogTrigger>
							<Button type="submit" loading={isLoading}>
								{limitToUpdate ? "Update" : "Save"}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
