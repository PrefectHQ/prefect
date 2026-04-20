import type { JsonInputOnChange } from "../ui/json-input";
import { LazyJsonInput as JsonInput } from "../ui/json-input-lazy";
import type { PrefectKindValueJinja } from "./types/prefect-kind-value";

type SchemaFormInputPrefectKindJinjaProps = {
	value: PrefectKindValueJinja;
	onValueChange: (value: PrefectKindValueJinja) => void;
	id: string;
};

export function SchemaFormInputPrefectKindJinja({
	value,
	onValueChange,
	id,
}: SchemaFormInputPrefectKindJinjaProps) {
	const onChange: JsonInputOnChange = (newValue) => {
		if (typeof newValue === "string" || newValue === undefined) {
			onValueChange({
				__prefect_kind: "jinja",
				template: newValue || undefined,
			});
		}
	};

	return <JsonInput value={value.template} onChange={onChange} id={id} />;
}
