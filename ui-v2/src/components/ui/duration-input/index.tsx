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

	const quantity = useMemo(() => {
		return value / unit;
	}, [value, unit]);
	const [quantityInput, setQuantityInput] = useState(String(quantity));

	useEffect(() => {
		setQuantityInput(String(quantity));
	}, [quantity]);

	const handleQuantityChange = useCallback(
		(newQuantity: string) => {
			setQuantityInput(newQuantity);
			const newValue = Number(newQuantity) * unit;
			if (
				newQuantity !== "" &&
				newValue >= min &&
				(max === undefined || newValue <= max)
			) {
				onChange(newValue);
			}
		},
		[onChange, unit, min, max],
	);

	const handleQuantityBlur = useCallback(() => {
		const parsedQuantity = Number(quantityInput);
		let newValue = Math.max(
			(Number.isFinite(parsedQuantity) ? parsedQuantity : 0) * unit,
			min,
		);
		if (max !== undefined && newValue > max) {
			newValue = max;
		}
		setQuantityInput(String(newValue / unit));
		if (newValue !== value) {
			onChange(newValue);
		}
	}, [quantityInput, unit, min, max, value, onChange]);

	const handleUnitChange = useCallback(
		(newUnitValue: string) => {
			const newUnit = Number(newUnitValue);
			const oldUnit = unit;
			setUnit(newUnit);
			let newValue = Math.max((value / oldUnit) * newUnit, min);
			if (max !== undefined && newValue > max) {
				newValue = max;
			}
			onChange(newValue);
		},
		[onChange, unit, value, min, max],
	);

	return (
		<div className={cn("grid grid-cols-[1fr_7rem] gap-2 w-full", className)}>
			<Input
				type="number"
				min={min / unit}
				step="any"
				value={quantityInput}
				onChange={(e) => handleQuantityChange(e.target.value)}
				onBlur={handleQuantityBlur}
				onKeyDown={(e) => {
					if (e.key === "Enter") {
						handleQuantityBlur();
					}
				}}
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
					{DURATION_UNITS.map((u) => (
						<SelectItem key={u.value} value={String(u.value)}>
							{u.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}
