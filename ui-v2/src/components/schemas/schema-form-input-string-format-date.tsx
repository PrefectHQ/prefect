import { format, isValid, parse, startOfToday } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
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
	const [inputValue, setInputValue] = useState(value ?? "");
	const inputRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		if (document.activeElement !== inputRef.current) {
			setInputValue(value ?? "");
		}
	}, [value]);

	function handleDateChange(nextDate: Date | undefined) {
		setDate(nextDate);
		setInputValue(nextDate ? format(nextDate, dateFormat) : "");
		onValueChange(nextDate ? format(nextDate, dateFormat) : undefined);
	}

	function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
		const text = event.target.value;
		setInputValue(text);

		if (text.trim() === "") {
			handleDateChange(undefined);
			return;
		}

		const parsed = parse(text, dateFormat, startOfToday());
		if (isValid(parsed)) {
			setDate(parsed);
			onValueChange(format(parsed, dateFormat));
		}
	}

	function handleInputBlur() {
		setInputValue(value ?? "");
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
				<div className="p-3 space-y-2">
					<Input
						ref={inputRef}
						type="text"
						placeholder={dateFormat}
						value={inputValue}
						onChange={handleInputChange}
						onBlur={handleInputBlur}
						aria-label="Date (yyyy-MM-dd)"
					/>
					<Calendar
						className="p-0"
						mode="single"
						selected={date}
						onSelect={handleDateChange}
						required={true}
						autoFocus
					/>
				</div>
			</PopoverContent>
		</Popover>
	);
}
