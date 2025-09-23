import { CalendarIcon } from "@radix-ui/react-icons";
import { format, formatISO, parseISO } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils";

export type DateRangeIso = {
	from?: string;
	to?: string;
};

export type DateRangePickerProps = {
	/** ISO strings for from/to; undefined to clear */
	value: DateRangeIso | undefined;
	onValueChange: (value: DateRangeIso | undefined) => void;
	defaultMonth?: Date;
	/** Used for schema form */
	id?: string;
	placeholder?: string;
};

function toDateRange(value: DateRangeIso | undefined): DateRange | undefined {
	if (!value) return undefined;
	const from = value.from ? parseISO(value.from) : undefined;
	const to = value.to ? parseISO(value.to) : undefined;
	if (!from && !to) return undefined;
	return { from, to };
}

function toIsoRange(range: DateRange | undefined): DateRangeIso | undefined {
	if (!range || (!range.from && !range.to)) return undefined;
	return {
		from: range.from ? formatISO(range.from) : undefined,
		to: range.to ? formatISO(range.to) : undefined,
	};
}

export function DateRangePicker({
	value,
	onValueChange,
	id,
	defaultMonth,
	placeholder = "Pick a date range",
}: DateRangePickerProps) {
	const initial = useMemo(() => toDateRange(value), [value]);
	const [range, setRange] = useState<DateRange | undefined>(initial);

	// Keep internal state in sync when the external value changes
	useEffect(() => {
		setRange(toDateRange(value));
	}, [value]);

	function handleChange(next: DateRange | undefined) {
		setRange(next);
		onValueChange(toIsoRange(next));
	}

	const label = useMemo(() => {
		if (range?.from && range.to) {
			return `${format(range.from, "MM/dd/yyyy")} - ${format(range.to, "MM/dd/yyyy")}`;
		}
		if (range?.from && !range.to) {
			return `${format(range.from, "MM/dd/yyyy")} - …`;
		}
		return undefined;
	}, [range]);

	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					className={cn(
						"w-full justify-start text-left font-normal",
						!label && "text-muted-foreground",
					)}
					id={id}
				>
					<CalendarIcon className="mr-2 h-4 w-4" />
					{label ?? <span>{placeholder}</span>}
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-auto p-0">
				<Calendar
					mode="range"
					selected={range}
					onSelect={handleChange}
					defaultMonth={defaultMonth}
					initialFocus
				/>
			</PopoverContent>
		</Popover>
	);
}

DateRangePicker.displayName = "DateRangePicker";
