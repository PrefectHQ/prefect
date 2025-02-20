import { JsonInput, JsonInputOnChange } from "../ui/json-input";
import { PrefectKindValueJson } from "./types/prefect-kind-value";

type SchemaFormInputPrefectKindJsonProps = {
	value: PrefectKindValueJson;
	onValueChange: (value: PrefectKindValueJson) => void;
	id: string;
};

export function SchemaFormInputPrefectKindJson({
	value,
	onValueChange,
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
