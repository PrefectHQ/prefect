import { ChevronLeftIcon, ChevronRightIcon } from "@radix-ui/react-icons";
import { addMonths, format, subMonths } from "date-fns";
import { DayPicker, type DayPickerProps } from "react-day-picker";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useState } from "react";

type CalendarProps = DayPickerProps & {
	className?: string;
	classNames?: Record<string, string>;
	showOutsideDays?: boolean;
	mode?: "default" | "single" | "multiple" | "range" | undefined;
};

function Calendar({
	className,
	classNames,
	showOutsideDays = true,
	defaultMonth,
	...props
}: CalendarProps) {
	const [month, setMonth] = useState(defaultMonth ?? new Date());

	return (
		<DayPicker
			month={month}
			onMonthChange={setMonth}
			showOutsideDays={showOutsideDays}
			className={className}
			classNames={{
				months: "flex flex-col sm:flex-row space-y-4 sm:space-y-0",
				month: "space-y-4",
				month_caption: "flex justify-between pt-1 items-center",
				month_grid: "w-full border-collapse space-y-1",
				weekday:
					"text-muted-foreground rounded-md w-8 font-normal text-[0.8rem]",
				day: cn(
					"size-10 text-center text-sm focus-within:relative focus-within:z-20 [&:has([aria-selected])]:bg-accent [&:has([aria-selected].day-outside)]:bg-accent/50 [&:has([aria-selected].day-range-end)]:rounded-r-md",
					props.mode === "range"
						? "[&:has(>.day-range-end)]:rounded-r-md [&:has(>.day-range-start)]:rounded-l-md first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md"
						: "[&:has([aria-selected])]:rounded-md",
				),
				button: cn(
					buttonVariants({ variant: "ghost" }),
					"size-8 p-0 font-normal aria-selected:opacity-100",
				),
				range_start: "day-range-start",
				range_end: "day-range-end",
				selected:
					"bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
				today: "bg-accent text-accent-foreground rounded",
				outside:
					"day-outside text-muted-foreground opacity-50  aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30",
				disabled: "text-muted-foreground opacity-50",
				day_range_middle:
					"aria-selected:bg-accent aria-selected:text-accent-foreground",
				hidden: "invisible",
				...classNames,
			}}
			components={{
				CaptionLabel: () => (
					<nav className="flex items-center justify-between grow">
						<Button
							aria-label="Go to the Previous Month"
							onClick={() => setMonth((curr) => subMonths(curr, 1))}
							variant="outline"
							className={cn(
								"size-7 bg-transparent p-0 opacity-50 hover:opacity-100",
							)}
						>
							<ChevronLeftIcon className="size-4" />
						</Button>
						<p className="text-sm font-medium">{format(month, "MMMM yyyy")}</p>
						<Button
							aria-label="Go to the Next Month"
							onClick={() => setMonth((curr) => addMonths(curr, 1))}
							variant="outline"
							className={cn(
								"size-7 bg-transparent p-0 opacity-50 hover:opacity-100 ",
							)}
						>
							<ChevronRightIcon className="size-4" />
						</Button>
					</nav>
				),
				// Navigation is handled in CaptionLabel component
				Nav: () => <></>,
			}}
			{...props}
		/>
	);
}
Calendar.displayName = "Calendar";

export { Calendar };
