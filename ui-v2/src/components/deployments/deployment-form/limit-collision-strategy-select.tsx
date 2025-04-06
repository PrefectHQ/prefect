import type { components } from "@/api/prefect";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

type LimitCollissionStrategy =
	components["schemas"]["ConcurrencyLimitStrategy"];

const LIMIT_COLLISSION_STRATEGIES = {
	ENQUEUE: "ENQUEUE",
	CANCEL_NEW: "CANCEL_NEW",
} satisfies Record<LimitCollissionStrategy, LimitCollissionStrategy>;

type LimitCollissionStrategySelectProps = {
	onValueChange: (value: LimitCollissionStrategy | undefined) => void;
	value: LimitCollissionStrategy | undefined;
};

export const LimitCollissionStrategySelect = ({
	onValueChange,
	value,
}: LimitCollissionStrategySelectProps) => {
	return (
		<Select
			value={value}
			onValueChange={(value) => {
				if (value === "") {
					onValueChange(undefined);
				} else {
					onValueChange(value as LimitCollissionStrategy);
				}
			}}
		>
			<SelectTrigger>
				<SelectValue placeholder={LIMIT_COLLISSION_STRATEGIES.ENQUEUE} />
			</SelectTrigger>
			<SelectContent>
				<SelectGroup>
					<SelectItem value={LIMIT_COLLISSION_STRATEGIES.ENQUEUE}>
						{LIMIT_COLLISSION_STRATEGIES.ENQUEUE}
					</SelectItem>
					<SelectItem value={LIMIT_COLLISSION_STRATEGIES.CANCEL_NEW}>
						{LIMIT_COLLISSION_STRATEGIES.CANCEL_NEW}
					</SelectItem>
				</SelectGroup>
			</SelectContent>
		</Select>
	);
};
