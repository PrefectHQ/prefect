import {
	CalendarIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
	XIcon,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { DateRangeSelectValue } from "./types";
import {
	getDateRangeLabel,
	isValidDateRange,
	mapDateRangeToDateRange,
	PRESET_RANGES,
} from "./utilities";

type DateRangeMode = "presets" | "custom" | null;

export type DateRangeSelectProps = {
	value?: DateRangeSelectValue;
	onValueChange: (value: DateRangeSelectValue) => void;
	placeholder?: string;
	clearable?: boolean;
	disabled?: boolean;
	min?: Date;
	max?: Date;
	className?: string;
};

export function DateRangeSelect({
	value,
	onValueChange,
	placeholder = "Select a time range",
	clearable = true,
	disabled = false,
	min,
	max,
	className,
}: DateRangeSelectProps) {
	const [open, setOpen] = useState(false);
	const [mode, setMode] = useState<DateRangeMode>(null);
	const [customRange, setCustomRange] = useState<{
		from?: Date;
		to?: Date;
	}>({});

	const label = getDateRangeLabel(value) || placeholder;
	const isPlaceholder = !value || !getDateRangeLabel(value);

	const canNavigate = value && ["span", "range"].includes(value.type);
	const range = canNavigate ? mapDateRangeToDateRange(value) : null;

	const handlePresetSelect = (presetValue: DateRangeSelectValue) => {
		onValueChange(presetValue);
		setOpen(false);
	};

	const handleCustomRangeSelect = () => {
		if (customRange.from && customRange.to) {
			const rangeValue: DateRangeSelectValue = {
				type: "range",
				startDate: customRange.from,
				endDate: customRange.to,
			};

			const validation = isValidDateRange(rangeValue, min, max);
			if (validation.valid) {
				onValueChange(rangeValue);
				setOpen(false);
				setMode(null);
				setCustomRange({});
			}
		}
	};

	const handleClear = () => {
		onValueChange(null);
	};

	const navigateRange = (direction: "previous" | "next") => {
		if (!range) return;

		const { timeSpanInSeconds } = range;
		const multiplier = direction === "previous" ? -1 : 1;
		const seconds = timeSpanInSeconds * multiplier;

		if (value?.type === "span") {
			// For span values, just shift the time window
			const newValue: DateRangeSelectValue = {
				type: "span",
				seconds: value.seconds + seconds,
			};

			const validation = isValidDateRange(newValue, min, max);
			if (validation.valid) {
				onValueChange(newValue);
			}
		} else if (value?.type === "range") {
			// For range values, shift both start and end dates
			const newStartDate = new Date(value.startDate.getTime() + seconds * 1000);
			const newEndDate = new Date(value.endDate.getTime() + seconds * 1000);

			const newValue: DateRangeSelectValue = {
				type: "range",
				startDate: newStartDate,
				endDate: newEndDate,
			};

			const validation = isValidDateRange(newValue, min, max);
			if (validation.valid) {
				onValueChange(newValue);
			}
		}
	};

	const canNavigatePrevious =
		range &&
		isValidDateRange(
			{
				type: "range",
				startDate: new Date(
					range.startDate.getTime() - range.timeSpanInSeconds * 1000,
				),
				endDate: new Date(
					range.endDate.getTime() - range.timeSpanInSeconds * 1000,
				),
			},
			min,
			max,
		).valid;

	const canNavigateNext =
		range &&
		isValidDateRange(
			{
				type: "range",
				startDate: new Date(
					range.startDate.getTime() + range.timeSpanInSeconds * 1000,
				),
				endDate: new Date(
					range.endDate.getTime() + range.timeSpanInSeconds * 1000,
				),
			},
			min,
			max,
		).valid;

	return (
		<div className={cn("flex items-center", className)}>
			{canNavigate && (
				<Button
					variant="outline"
					size="icon"
					className="rounded-r-none border-r-0"
					disabled={disabled || !canNavigatePrevious}
					onClick={() => navigateRange("previous")}
				>
					<ChevronLeftIcon className="h-4 w-4" />
				</Button>
			)}

			<Popover open={open} onOpenChange={setOpen}>
				<PopoverTrigger asChild>
					<Button
						variant="outline"
						className={cn(
							"justify-start text-left font-normal",
							canNavigate && "rounded-none",
							!canNavigate && clearable && value && "rounded-r-none",
							isPlaceholder && "text-muted-foreground",
						)}
						disabled={disabled}
					>
						<CalendarIcon className="mr-2 h-4 w-4" />
						{label}
					</Button>
				</PopoverTrigger>
				<PopoverContent className="w-auto p-0" align="start">
					<div className="p-3">
						{mode === null && (
							<div className="space-y-2">
								<div className="grid gap-1">
									{PRESET_RANGES.map((preset) => (
										<Button
											key={preset.label}
											variant="ghost"
											className="justify-start"
											onClick={() => handlePresetSelect(preset.value)}
										>
											{preset.label}
										</Button>
									))}
								</div>
								<Separator />
								<Button
									variant="ghost"
									className="w-full justify-start"
									onClick={() => setMode("custom")}
								>
									Custom range
								</Button>
							</div>
						)}

						{mode === "custom" && (
							<div className="space-y-3">
								<div className="flex items-center justify-between">
									<h4 className="text-sm font-medium">Select custom range</h4>
									<Button
										variant="ghost"
										size="sm"
										onClick={() => {
											setMode(null);
											setCustomRange({});
										}}
									>
										Back
									</Button>
								</div>
								<Calendar
									initialFocus
									mode="range"
									defaultMonth={customRange.from}
									selected={customRange}
									onSelect={setCustomRange}
									numberOfMonths={1}
									disabled={(date) => {
										if (min && date < min) return true;
										if (max && date > max) return true;
										return false;
									}}
								/>
								<div className="flex justify-end space-x-2">
									<Button
										variant="outline"
										size="sm"
										onClick={() => {
											setMode(null);
											setCustomRange({});
										}}
									>
										Cancel
									</Button>
									<Button
										size="sm"
										disabled={!customRange.from || !customRange.to}
										onClick={handleCustomRangeSelect}
									>
										Apply
									</Button>
								</div>
							</div>
						)}
					</div>
				</PopoverContent>
			</Popover>

			{clearable && value && (
				<Button
					variant="outline"
					size="icon"
					className="rounded-l-none border-l-0"
					disabled={disabled}
					onClick={handleClear}
				>
					<XIcon className="h-4 w-4" />
				</Button>
			)}

			{canNavigate && (
				<Button
					variant="outline"
					size="icon"
					className={cn(
						"rounded-l-none",
						!clearable || !value ? "border-l-0" : "border-l-0 -ml-px",
					)}
					disabled={disabled || !canNavigateNext}
					onClick={() => navigateRange("next")}
				>
					<ChevronRightIcon className="h-4 w-4" />
				</Button>
			)}
		</div>
	);
}
