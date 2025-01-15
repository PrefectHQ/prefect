import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type TaskRunConcurrencyLimitsHeaderProps = {
	onAdd: () => void;
};

export const TaskRunConcurrencyLimitsHeader = ({
	onAdd,
}: TaskRunConcurrencyLimitsHeaderProps) => {
	return (
		<div className="flex gap-2 items-center">
			<Typography className="font-semibold">
				Task Run Concurrency Limits
			</Typography>
			<Button
				onClick={onAdd}
				size="icon"
				className="h-7 w-7"
				variant="outline"
				aria-label="add task run concurrency limit"
			>
				<Icon id="Plus" className="h-4 w-4" />
			</Button>
		</div>
	);
};
