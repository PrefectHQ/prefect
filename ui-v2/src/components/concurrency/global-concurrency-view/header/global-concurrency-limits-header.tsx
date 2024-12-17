import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type Props = {
	onAdd: () => void;
};

export const GlobalConcurrencyLimitsHeader = ({ onAdd }: Props) => {
	return (
		<div className="flex gap-2 items-center">
			<Typography variant="h4">Global Concurrency Limits</Typography>
			<Button
				onClick={onAdd}
				size="icon"
				aria-label="add global concurrency limit"
			>
				<Icon id="Plus" className="h-4 w-4" />
			</Button>
		</div>
	);
};
