import { JsonInput } from "../ui/json-input";

export type SchemaFormInputStringFormatJsonProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	errors: unknown;
};

export function SchemaFormInputStringFormatJson({
	value,
	onValueChange,
	errors,
}: SchemaFormInputStringFormatJsonProps) {

  function handleChange(value: string | undefined) {
    onValueChange(value || undefined);
  }

	return <JsonInput value={value} onChange={handleChange} />;
}
