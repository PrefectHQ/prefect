import { DateTimePicker } from "@/components/ui/date-time-picker";

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
	return <DateTimePicker value={value} onValueChange={onValueChange} id={id} />;
}
