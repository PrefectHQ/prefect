import { parseISO } from "date-fns";
import { formatInTimeZone, toZonedTime } from "date-fns-tz";
import { useState } from "react";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import { TimezoneSelect } from "@/components/ui/timezone-select";

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

type SchemaFormInputStringFormatDateTimeProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	id: string;
};

export function SchemaFormInputStringFormatDateTime({
	value,
	onValueChange,
	id,
}: SchemaFormInputStringFormatDateTimeProps) {
	const [timezone, setTimezone] = useState<string>(localTimezone);

	function handleDateTimeChange(isoString: string | undefined) {
		if (!isoString) {
			onValueChange(undefined);
			return;
		}

		const date = parseISO(isoString);
		const formattedWithTimezone = formatInTimeZone(
			date,
			timezone,
			"yyyy-MM-dd'T'HH:mm:ssXXX",
		);
		onValueChange(formattedWithTimezone);
	}

	function handleTimezoneChange(newTimezone: string) {
		setTimezone(newTimezone);

		if (value) {
			const date = parseISO(value);
			const zonedDate = toZonedTime(date, newTimezone);
			const formattedWithTimezone = formatInTimeZone(
				zonedDate,
				newTimezone,
				"yyyy-MM-dd'T'HH:mm:ssXXX",
			);
			onValueChange(formattedWithTimezone);
		}
	}

	return (
		<div className="flex flex-col gap-2">
			<DateTimePicker
				value={value}
				onValueChange={handleDateTimeChange}
				id={id}
			/>
			<TimezoneSelect
				selectedValue={timezone}
				onSelect={handleTimezoneChange}
			/>
		</div>
	);
}
