import { NullSubtype, SchemaObject } from "openapi-typescript";

type SchemaFormInputNullProps = {
	value: null;
	onValueChange: (value: null) => void;
	property: SchemaObject & NullSubtype;
	errors: unknown;
};

export function SchemaFormInputNull({
	value,
	onValueChange,
	property,
	errors,
}: SchemaFormInputNullProps) {
	return (
		<p className="text-subdued text-sm">Property is type &quot;None&quot;</p>
	);
}
