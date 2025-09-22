import { CalendarIcon } from "@radix-ui/react-icons";
import { format, formatISO, parseISO } from "date-fns";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { cn } from "@/utils";

const getInitialDate = (value: string | undefined) =>
	value ? parseISO(value) : undefined;

export type DateTimePickerProps = {
	/** Expected as an ISO string */
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	defaultMonth?: Date;
	/** Used for schema form */
	id?: string;
};

export function DateTimePicker({
	value,
	onValueChange,
	id,
	defaultMonth,
}: DateTimePickerProps) {
	const [date, setDate] = useState<Date | undefined>(getInitialDate(value));

	function handleDateChange(date: Date | undefined) {
		setDate(date);
		onValueChange(date ? formatISO(date) : undefined);
	}

	const hours = Array.from({ length: 12 }, (_, i) => i + 1);

	const handleTimeChange = (
		type: "hour" | "minute" | "ampm",
		value: string,
	) => {
		if (date) {
			const newDate = new Date(date);
			if (type === "hour") {
				newDate.setHours(
					(Number.parseInt(value) % 12) + (newDate.getHours() >= 12 ? 12 : 0),
				);
			} else if (type === "minute") {
				newDate.setMinutes(Number.parseInt(value));
			} else if (type === "ampm") {
				const currentHours = newDate.getHours();
				newDate.setHours(
					value === "PM" ? currentHours + 12 : currentHours - 12,
				);
			}

			handleDateChange(newDate);
		}
	};

	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button
					variant="outline"
					className={cn(
						"w-full justify-start text-left font-normal",
						!date && "text-muted-foreground",
					)}
					id={id}
				>
					<CalendarIcon className="mr-2 h-4 w-4" />
					{date ? (
						format(date, "MM/dd/yyyy hh:mm aa")
					) : (
						<span>MM/DD/YYYY hh:mm aa</span>
					)}
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-auto p-0">
				<div className="sm:flex">
					<Calendar
						mode="single"
						selected={date}
						onSelect={handleDateChange}
						defaultMonth={defaultMonth}
						initialFocus
					/>
					<div className="flex flex-col sm:flex-row sm:h-[300px] divide-y sm:divide-y-0 sm:divide-x">
						<ScrollArea className="w-64 sm:w-auto">
							<div className="flex sm:flex-col p-2">
								{hours.reverse().map((hour) => (
									<Button
										key={hour}
										size="icon"
										variant={
											date && date.getHours() % 12 === hour % 12
												? "default"
												: "ghost"
										}
										className="sm:w-full shrink-0 aspect-square"
										onClick={() => handleTimeChange("hour", hour.toString())}
									>
										{hour}
									</Button>
								))}
							</div>
							<ScrollBar orientation="horizontal" className="sm:hidden" />
						</ScrollArea>
						<ScrollArea className="w-64 sm:w-auto">
							<div className="flex sm:flex-col p-2">
								{Array.from({ length: 12 }, (_, i) => i * 5).map((minute) => (
									<Button
										key={minute}
										size="icon"
										variant={
											date && date.getMinutes() === minute ? "default" : "ghost"
										}
										className="sm:w-full shrink-0 aspect-square"
										onClick={() =>
											handleTimeChange("minute", minute.toString())
										}
									>
										{minute}
									</Button>
								))}
							</div>
							<ScrollBar orientation="horizontal" className="sm:hidden" />
						</ScrollArea>
						<ScrollArea className="">
							<div className="flex sm:flex-col p-2">
								{["AM", "PM"].map((ampm) => (
									<Button
										key={ampm}
										size="icon"
										variant={
											date &&
											((ampm === "AM" && date.getHours() < 12) ||
												(ampm === "PM" && date.getHours() >= 12))
												? "default"
												: "ghost"
										}
										className="sm:w-full shrink-0 aspect-square"
										onClick={() => handleTimeChange("ampm", ampm)}
									>
										{ampm}
									</Button>
								))}
							</div>
						</ScrollArea>
					</div>
				</div>
			</PopoverContent>
		</Popover>
	);
}
