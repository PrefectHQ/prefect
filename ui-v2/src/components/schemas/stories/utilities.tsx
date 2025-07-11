import { useState } from "react";
import { JsonInput } from "@/components/ui/json-input";
import { Typography } from "@/components/ui/typography";
import type { SchemaFormProps } from "../schema-form";
import { SchemaForm } from "../schema-form";
import type { PrefectSchemaObject } from "../types/schemas";

export function TestSchemaForm({
	schema,
	kinds = ["json"],
	errors = [],
	values: initialValues = {},
	onValuesChange = () => {},
}: Partial<SchemaFormProps> & {
	schema: PrefectSchemaObject;
}) {
	const [values, setValues] = useState<Record<string, unknown>>(initialValues);

	function handleValuesChange(values: Record<string, unknown>) {
		setValues(values);
		onValuesChange(values);
	}

	return (
		<div className="grid grid-cols-2 gap-4 p-4 size-full">
			<div className="flex flex-col gap-4">
				<Typography variant="h2">Form</Typography>
				<SchemaForm
					schema={schema}
					kinds={kinds}
					errors={errors}
					values={values}
					onValuesChange={handleValuesChange}
				/>
			</div>
			<div className="flex flex-col gap-4">
				<Typography variant="h2">Values</Typography>
				<JsonInput value={JSON.stringify(values, null, 2)} />
				<Typography variant="h2">Schema</Typography>
				<JsonInput value={JSON.stringify(schema, null, 2)} />
				{errors.length > 0 && (
					<>
						<Typography variant="h2">Errors</Typography>
						<JsonInput value={JSON.stringify(errors, null, 2)} />
					</>
				)}
			</div>
		</div>
	);
}
