import { Button } from "@/components/ui/button";
import { Flex } from "@/components/ui/flex";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type Props = {
	onAdd: () => void;
};

export const GlobalConcurrencyLimitsHeader = ({ onAdd }: Props) => {
	return (
		<Flex flexDirection="row" gap={2} alignItems="center">
			<Typography variant="h4">Global Concurrency Limits</Typography>
			<Button onClick={onAdd} size="icon">
				<Icon id="Plus" />
			</Button>
		</Flex>
	);
};
