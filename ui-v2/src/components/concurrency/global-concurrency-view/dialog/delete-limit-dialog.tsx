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
import {
	GlobalConcurrencyLimit,
	useDeleteGlobalConcurrencyLimit,
} from "@/hooks/global-concurrency-limits";
import { useToast } from "@/hooks/use-toast";

type Props = {
	limit: GlobalConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onDelete: () => void;
};

export const DeleteLimitDialog = ({ limit, onOpenChange, onDelete }: Props) => {
	const { toast } = useToast();
	const { deleteGlobalConcurrencyLimit, isPending } =
		useDeleteGlobalConcurrencyLimit();

	const handleOnClick = (id: string | undefined) => {
		if (!id) {
			throw new Error("'id' field expected in GlobalConcurrencyLimit");
		}
		deleteGlobalConcurrencyLimit(id, {
			onSuccess: () => {
				toast({ description: "Concurrency limit deleted" });
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
						onClick={() => handleOnClick(limit?.id)}
						loading={isPending}
					>
						Delete
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
