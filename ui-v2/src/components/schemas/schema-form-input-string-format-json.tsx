import { JsonInput } from "../ui/json-input";

export type SchemaFormInputStringFormatJsonProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	id: string;
};

export function SchemaFormInputStringFormatJson({
	value,
	onValueChange,
	id,
}: SchemaFormInputStringFormatJsonProps) {
	// the JsonInput's types for onChange are probably wrong but this makes it work
	const onChange: React.FormEventHandler<HTMLDivElement> &
		((value: string) => void) = (value) => {
		if (typeof value === "string" || value === undefined) {
			onValueChange(value || undefined);
		}
	};

	return <JsonInput value={value} onChange={onChange} id={id} />;
}
