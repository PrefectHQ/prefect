import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type GlobalConcurrencyLimitsHeaderProps = {
	onAdd: () => void;
};

export const GlobalConcurrencyLimitsHeader = ({
	onAdd,
}: GlobalConcurrencyLimitsHeaderProps) => {
	return (
		<div className="flex gap-2 items-center">
			<Typography className="font-semibold">
				Global Concurrency Limits
			</Typography>
			<Button
				onClick={onAdd}
				size="icon"
				className="h-7 w-7"
				variant="outline"
				aria-label="add global concurrency limit"
			>
				<Icon id="Plus" className="h-4 w-4" />
			</Button>
		</div>
	);
};
