import { useCallback, useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { cn } from "@/utils";

const SECONDS_IN_MINUTE = 60;
const SECONDS_IN_HOUR = 3600;
const SECONDS_IN_DAY = 86400;

type DurationUnit = {
	label: string;
	value: number;
};

const DURATION_UNITS: DurationUnit[] = [
	{ label: "Seconds", value: 1 },
	{ label: "Minutes", value: SECONDS_IN_MINUTE },
	{ label: "Hours", value: SECONDS_IN_HOUR },
	{ label: "Days", value: SECONDS_IN_DAY },
];

function getDefaultUnitForValue(value: number): number {
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

export type DurationInputProps = {
	value: number;
	onChange: (seconds: number) => void;
	min?: number;
	max?: number;
	className?: string;
	disabled?: boolean;
};

export function DurationInput({
	value,
	onChange,
	min = 0,
	max,
	className,
	disabled = false,
}: DurationInputProps) {
	const [unit, setUnit] = useState<number>(() => getDefaultUnitForValue(value));

	const availableUnits = useMemo(() => {
		return DURATION_UNITS.filter((u) => u.value >= min);
	}, [min]);

	const quantity = useMemo(() => {
		return value / unit;
	}, [value, unit]);

	const handleQuantityChange = useCallback(
		(newQuantity: number) => {
			let newValue = newQuantity * unit;
			if (max !== undefined && newValue > max) {
				newValue = max;
			}
			onChange(newValue);
		},
		[onChange, unit, max],
	);

	const handleUnitChange = useCallback(
		(newUnitValue: string) => {
			const newUnit = Number(newUnitValue);
			const oldUnit = unit;
			setUnit(newUnit);
			let newValue = (value / oldUnit) * newUnit;
			if (max !== undefined && newValue > max) {
				newValue = max;
			}
			onChange(newValue);
		},
		[onChange, unit, value, max],
	);

	useEffect(() => {
		if (!availableUnits.some((u) => u.value === unit)) {
			const firstAvailable = availableUnits[0];
			if (firstAvailable) {
				setUnit(firstAvailable.value);
			}
		}
	}, [availableUnits, unit]);

	return (
		<div className={cn("grid grid-cols-[1fr_7rem] gap-2 w-full", className)}>
			<Input
				type="number"
				min={0}
				value={quantity}
				onChange={(e) => handleQuantityChange(Number(e.target.value))}
				disabled={disabled}
				aria-label="Duration quantity"
			/>
			<Select
				value={String(unit)}
				onValueChange={handleUnitChange}
				disabled={disabled}
			>
				<SelectTrigger aria-label="Duration unit">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					{availableUnits.map((u) => (
						<SelectItem key={u.value} value={String(u.value)}>
							{u.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}
