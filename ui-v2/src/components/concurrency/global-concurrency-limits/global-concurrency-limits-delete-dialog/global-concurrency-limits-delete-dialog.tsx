import { toast } from "sonner";
import {
	type GlobalConcurrencyLimit,
	useDeleteGlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";

type GlobalConcurrencyLimitsDeleteDialogProps = {
	limit: GlobalConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onDelete: () => void;
};

export const GlobalConcurrencyLimitsDeleteDialog = ({
	limit,
	onOpenChange,
	onDelete,
}: GlobalConcurrencyLimitsDeleteDialogProps) => {
	const { deleteGlobalConcurrencyLimit, isPending } =
		useDeleteGlobalConcurrencyLimit();

	const handleOnClick = (id: string) => {
		deleteGlobalConcurrencyLimit(id, {
			onSuccess: () => {
				toast.success("Concurrency limit deleted");
			},
			onError: (error) => {
				const message =
					error.message || "Unknown error while deleting concurrency limit.";
				console.error(message);
			},
			onSettled: onDelete,
		});
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Delete Concurrency Limit</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					Are you sure you want to delete {limit.name}
				</DialogDescription>
				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button
						variant="destructive"
						onClick={() => handleOnClick(limit.id)}
						loading={isPending}
					>
						Delete
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
