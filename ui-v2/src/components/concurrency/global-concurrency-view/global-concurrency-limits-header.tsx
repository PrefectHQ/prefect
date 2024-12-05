import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type Props = {
	onAdd: () => void;
};

export const GlobalConcurrencyLimitsHeader = ({ onAdd }: Props) => {
	return (
		<div className="flex flex-row items-center gap-2">
			<Typography variant="h4">Global Concurrency Limits</Typography>
			<Button onClick={onAdd} size="icon">
				<Icon id="Plus" />
			</Button>
		</div>
	);
};
