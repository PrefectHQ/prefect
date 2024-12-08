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
	useUpdateGlobalConcurrencyLimit,
} from "@/hooks/global-concurrency-limits";
import { useToast } from "@/hooks/use-toast";

type Props = {
	limit: GlobalConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onReset: () => void;
};

export const ResetLimitDialog = ({ limit, onOpenChange, onReset }: Props) => {
	const { toast } = useToast();
	const { updateGlobalConcurrencyLimit, isPending } =
		useUpdateGlobalConcurrencyLimit();

	const handleOnClick = (id: string | undefined) => {
		if (!id) {
			throw new Error("'id' field expected in GlobalConcurrencyLimit");
		}

		updateGlobalConcurrencyLimit(
			{
				id_or_name: id,
				active_slots: 0,
			},
			{
				onSuccess: () => {
					toast({ description: "Concurrency limit reset" });
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while resetting concurrency limit.";
					console.error(message);
				},
				onSettled: onReset,
			},
		);
	};

	return (
		<Dialog open onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Reset concurrency limit my second limit?</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					This will reset the active slots count to 0.
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
