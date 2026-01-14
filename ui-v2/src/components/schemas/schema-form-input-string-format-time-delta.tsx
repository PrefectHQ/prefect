import { Input } from "@/components/ui/input";

type SchemaFormInputStringFormatTimeDeltaProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	id: string;
};

export function SchemaFormInputStringFormatTimeDelta({
	value,
	onValueChange,
	id,
}: SchemaFormInputStringFormatTimeDeltaProps) {
	function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
		const inputValue = e.target.value;
		if (inputValue === "") {
			onValueChange(undefined);
			return;
		}
		const numericValue = Number(inputValue);
		if (!Number.isNaN(numericValue)) {
			onValueChange(String(numericValue));
		}
	}

	return (
		<Input
			type="number"
			value={value ?? ""}
			onChange={handleChange}
			id={id}
			placeholder="Duration in seconds"
			min={0}
		/>
	);
}
