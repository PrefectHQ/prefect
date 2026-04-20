import { VariableCombobox } from "@/components/variables/variable-combobox";
import type { PrefectKindValueWorkspaceVariable } from "./types/prefect-kind-value";

type SchemaFormInputPrefectKindWorkspaceVariableProps = {
	value: PrefectKindValueWorkspaceVariable;
	onValueChange: (value: PrefectKindValueWorkspaceVariable) => void;
	id: string;
};

export function SchemaFormInputPrefectKindWorkspaceVariable({
	value,
	onValueChange,
	id,
}: SchemaFormInputPrefectKindWorkspaceVariableProps) {
	const handleSelect = (variableName: string | undefined) => {
		onValueChange({
			__prefect_kind: "workspace_variable",
			variable_name: variableName,
		});
	};

	return (
		<div id={id}>
			<VariableCombobox
				selectedVariableName={value.variable_name}
				onSelect={handleSelect}
			/>
		</div>
	);
}
