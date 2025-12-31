import { useMemo } from "react";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const SECONDS_IN_MINUTE = 60;
const SECONDS_IN_HOUR = 3600;
const SECONDS_IN_DAY = 86400;

type DurationUnit = 1 | 60 | 3600 | 86400;

const UNIT_OPTIONS: { label: string; value: DurationUnit }[] = [
	{ label: "Seconds", value: 1 },
	{ label: "Minutes", value: SECONDS_IN_MINUTE },
	{ label: "Hours", value: SECONDS_IN_HOUR },
	{ label: "Days", value: SECONDS_IN_DAY },
];

function getDefaultUnitForValue(value: number): DurationUnit {
	if (value > 0 && value % SECONDS_IN_DAY === 0) {
		return SECONDS_IN_DAY;
	}
	if (value > 0 && value % SECONDS_IN_HOUR === 0) {
		return SECONDS_IN_HOUR;
	}
	if (value > 0 && value % SECONDS_IN_MINUTE === 0) {
		return SECONDS_IN_MINUTE;
	}
	return 1;
}

type DurationInputProps = {
	value: number;
	onChange: (value: number) => void;
	min?: number;
	id?: string;
	disabled?: boolean;
};

export function DurationInput({
	value,
	onChange,
	min = 0,
	id,
	disabled = false,
}: DurationInputProps) {
	const unit = useMemo(() => getDefaultUnitForValue(value), [value]);

	const quantity = value / unit;

	const availableUnits = useMemo(() => {
		return UNIT_OPTIONS.filter((option) => option.value >= min);
	}, [min]);

	const handleQuantityChange = (newQuantity: number) => {
		onChange(newQuantity * unit);
	};

	const handleUnitChange = (newUnitStr: string) => {
		const newUnit = Number(newUnitStr) as DurationUnit;
		const newValue = (value / unit) * newUnit;
		onChange(newValue);
	};

	return (
		<div className="flex gap-2">
			<Input
				id={id}
				type="number"
				min={0}
				value={quantity}
				onChange={(e) => handleQuantityChange(Number(e.target.value))}
				className="w-24"
				disabled={disabled}
			/>
			<Select
				value={String(unit)}
				onValueChange={handleUnitChange}
				disabled={disabled}
			>
				<SelectTrigger className="w-28" aria-label="Duration unit">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					{availableUnits.map((option) => (
						<SelectItem key={option.value} value={String(option.value)}>
							{option.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}
