import { JsonInput, JsonInputOnChange } from "../ui/json-input";
import { PrefectKindJson } from "./types/prefect-kind-value";

type SchemaFormInputPrefectKindJsonProps = {
	value: PrefectKindJson;
	onValueChange: (value: PrefectKindJson) => void;
	errors: unknown;
	id: string;
};

export function SchemaFormInputPrefectKindJson({
	value,
	onValueChange,
	errors,
	id,
}: SchemaFormInputPrefectKindJsonProps) {
	const onChange: JsonInputOnChange = (value) => {
		if (typeof value === "string" || value === undefined) {
			onValueChange({
				__prefect_kind: "json",
				value: value || undefined,
			});
		}
	};

	return <JsonInput value={value.value} onChange={onChange} id={id} />;
}
