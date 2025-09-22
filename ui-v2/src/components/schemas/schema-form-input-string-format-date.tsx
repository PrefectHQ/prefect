import { format, parse, startOfToday } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils";

type SchemaFormInputStringFormatDateProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	id: string;
};

const dateFormat = "yyyy-MM-dd";

export function SchemaFormInputStringFormatDate({
	value,
	onValueChange,
	id,
}: SchemaFormInputStringFormatDateProps) {
	const initialDate = value
		? parse(value, dateFormat, startOfToday())
		: undefined;
	const [date, setDate] = useState<Date | undefined>(initialDate);

	function handleDateChange(date: Date | undefined) {
		setDate(date);
		onValueChange(date ? format(date, dateFormat) : undefined);
	}

	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button
					variant={"outline"}
					className={cn(
						"justify-start text-left font-normal w-full",
						!date && "text-muted-foreground",
					)}
					id={id}
				>
					<CalendarIcon className="mr-2 h-4 w-4" />
					{date ? format(date, "PPP") : <span>Pick a date</span>}
				</Button>
			</PopoverTrigger>
			<PopoverContent className="w-auto p-0">
				<Calendar
					mode="single"
					selected={date}
					onSelect={handleDateChange}
					required={true}
					autoFocus
				/>
			</PopoverContent>
		</Popover>
	);
}
