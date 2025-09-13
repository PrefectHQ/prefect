import { format } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type DateRangeValue =
	| { type: "span"; seconds: number }
	| { type: "range"; startDate: Date; endDate: Date }
	| null;

export type DateRangeSelectProps = {
	value?: DateRangeValue;
	onChange?: (value: DateRangeValue) => void;
	placeholder?: string;
};

const PRESET_RANGES = [
	{ label: "Last 1 day", value: { type: "span" as const, seconds: -86400 } },
	{ label: "Last 7 days", value: { type: "span" as const, seconds: -604800 } },
	{
		label: "Last 30 days",
		value: { type: "span" as const, seconds: -2592000 },
	},
];

function getDateRangeLabel(value: DateRangeValue): string {
	if (!value) return "Select date range";

	if (value.type === "span") {
		const preset = PRESET_RANGES.find((p) => p.value.seconds === value.seconds);
		if (preset) return preset.label;

		const days = Math.abs(value.seconds) / 86400;
		if (days === 1) return "Last 1 day";
		return `Last ${Math.floor(days)} days`;
	}

	if (value.type === "range") {
		return `${format(value.startDate, "MMM dd")} - ${format(value.endDate, "MMM dd")}`;
	}

	return "Select date range";
}

export const DateRangeSelect = ({
	value,
	onChange,
	placeholder = "Select date range",
}: DateRangeSelectProps) => {
	const [open, setOpen] = useState(false);
	const [customRange, setCustomRange] = useState<{
		startDate?: Date;
		endDate?: Date;
	}>({});

	const handlePresetSelect = (presetValue: DateRangeValue) => {
		onChange?.(presetValue);
		setOpen(false);
	};

	const handleCustomRangeSelect = (date: Date | undefined) => {
		if (!date) return;

		if (
			!customRange.startDate ||
			(customRange.startDate && customRange.endDate)
		) {
			// Start new range
			setCustomRange({ startDate: date, endDate: undefined });
		} else if (customRange.startDate && !customRange.endDate) {
			// Complete the range
			const startDate = customRange.startDate;
			const endDate = date;

			// Ensure startDate is before endDate
			const finalStartDate = startDate <= endDate ? startDate : endDate;
			const finalEndDate = startDate <= endDate ? endDate : startDate;

			const rangeValue: DateRangeValue = {
				type: "range",
				startDate: finalStartDate,
				endDate: finalEndDate,
			};

			onChange?.(rangeValue);
			setCustomRange({});
			setOpen(false);
		}
	};

	const displayValue = getDateRangeLabel(value ?? null) || placeholder;

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					className={cn(
						"w-[280px] justify-start text-left font-normal",
						!value && "text-muted-foreground",
					)}
				>
					<CalendarIcon className="mr-2 h-4 w-4" />
					{displayValue}
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-auto p-0" align="start">
				<div className="p-3">
					<div className="space-y-2">
						<p className="text-sm font-medium">Quick ranges</p>
						{PRESET_RANGES.map((preset) => (
							<Button
								key={preset.label}
								variant="ghost"
								className="w-full justify-start font-normal"
								onClick={() => handlePresetSelect(preset.value)}
							>
								{preset.label}
							</Button>
						))}
					</div>
					<div className="pt-4 border-t">
						<p className="text-sm font-medium mb-3">Custom range</p>
						<Calendar
							mode="single"
							selected={customRange.startDate}
							onSelect={handleCustomRangeSelect}
							className="rounded-md border"
						/>
						{customRange.startDate && (
							<p className="text-xs text-muted-foreground mt-2">
								Select end date to complete range
							</p>
						)}
					</div>
				</div>
			</PopoverContent>
		</Popover>
	);
};
