import { toast } from "sonner";
import {
	type GlobalConcurrencyLimit,
	useResetGlobalConcurrencyLimit,
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

type GlobalConcurrencyLimitsResetDialogProps = {
	limit: GlobalConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onReset: () => void;
};

export const GlobalConcurrencyLimitsResetDialog = ({
	limit,
	onOpenChange,
	onReset,
}: GlobalConcurrencyLimitsResetDialogProps) => {
	const { resetGlobalConcurrencyLimit, isPending } =
		useResetGlobalConcurrencyLimit();

	const handleOnClick = (id: string) => {
		resetGlobalConcurrencyLimit(id, {
			onSuccess: () => {
				toast.success("Concurrency limit reset");
			},
			onError: (error) => {
				const message =
					error.message || "Unknown error while resetting concurrency limit.";
				console.error(message);
			},
			onSettled: onReset,
		});
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Reset concurrency limit for {limit.name}</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					This will reset the active slots to 0.
				</DialogDescription>
				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button onClick={() => handleOnClick(limit.id)} loading={isPending}>
						Reset
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
