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
	type TaskRunConcurrencyLimit,
	useResetTaskRunConcurrencyLimitTag,
} from "@/hooks/task-run-concurrency-limits";
import { useToast } from "@/hooks/use-toast";

type Props = {
	data: TaskRunConcurrencyLimit;
	onOpenChange: (open: boolean) => void;
	onReset: () => void;
};

export const TaskRunConcurrencyLimitsResetDialog = ({
	data,
	onOpenChange,
	onReset,
}: Props) => {
	const { toast } = useToast();
	const { resetTaskRunConcurrencyLimitTag, isPending } =
		useResetTaskRunConcurrencyLimitTag();

	const handleOnClick = (tag: string) => {
		resetTaskRunConcurrencyLimitTag(tag, {
			onSuccess: () => {
				toast({ description: "Concurrency limit reset" });
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
					<DialogTitle>Reset concurrency limit for tag {data.tag}</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					This will reset the active task run count to 0.
				</DialogDescription>
				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button onClick={() => handleOnClick(data.tag)} loading={isPending}>
						Reset
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};
