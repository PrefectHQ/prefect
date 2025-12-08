import { zodResolver } from "@hookform/resolvers/zod";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import {
	buildListSavedSearchesQuery,
	useCreateSavedSearch,
} from "@/api/saved-searches";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
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
import type { SavedFlowRunsSearch } from "./saved-filters";
import { convertSavedFiltersFilterToApiFilters } from "./saved-filters";
import { SYSTEM_SAVED_SEARCHES } from "./saved-filters-utils";

type SaveFilterModalProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	savedSearch: SavedFlowRunsSearch;
	onSaved?: (savedSearch: SavedFlowRunsSearch) => void;
};

export function SaveFilterModal({
	open,
	onOpenChange,
	savedSearch,
	onSaved,
}: SaveFilterModalProps) {
	const { data: existingSavedSearches } = useSuspenseQuery(
		buildListSavedSearchesQuery(),
	);

	const { createSavedSearch, isPending } = useCreateSavedSearch();

	const existingNames = [
		...SYSTEM_SAVED_SEARCHES.map((s) => s.name),
		...existingSavedSearches.map((s) => s.name),
	];

	const formSchema = z.object({
		name: z
			.string()
			.min(1, "Name is required")
			.refine((name) => !existingNames.includes(name), {
				message: "Name must be unique",
			}),
	});

	type FormValues = z.infer<typeof formSchema>;

	const form = useForm<FormValues>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			name: "",
		},
	});

	const handleSubmit = (values: FormValues) => {
		const apiFilters = convertSavedFiltersFilterToApiFilters(
			savedSearch.filters,
		);

		createSavedSearch(
			{
				name: values.name,
				filters: apiFilters,
			},
			{
				onSuccess: (data) => {
					toast.success("View saved successfully");
					form.reset();
					onOpenChange(false);
					onSaved?.({
						id: data.id,
						name: data.name,
						filters: savedSearch.filters,
						isDefault: false,
					});
				},
				onError: (error) => {
					toast.error(
						error instanceof Error ? error.message : "Failed to save view",
					);
				},
			},
		);
	};

	const handleOpenChange = (newOpen: boolean) => {
		if (!newOpen) {
			form.reset();
		}
		onOpenChange(newOpen);
	};

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Save View</DialogTitle>
				</DialogHeader>
				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(handleSubmit)(e)}
						className="space-y-4"
					>
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel>View Name</FormLabel>
									<FormControl>
										<Input
											placeholder="Enter a name for this view"
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
								onClick={() => handleOpenChange(false)}
							>
								Cancel
							</Button>
							<Button type="submit" disabled={isPending}>
								{isPending ? "Saving..." : "Save"}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
}
