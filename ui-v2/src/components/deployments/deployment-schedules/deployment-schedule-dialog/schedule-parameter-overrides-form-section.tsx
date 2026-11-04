import { LazySchemaForm } from "@/components/schemas";
import { isEmptyObject } from "@/components/schemas/utilities/guards";
import type { ScheduleParameterOverrides } from "./use-schedule-parameter-overrides";

export const ScheduleParameterOverridesFormSection = ({
	schema,
	values,
	errors,
	setValues,
}: ScheduleParameterOverrides) => {
	if (!schema?.properties || isEmptyObject(schema.properties)) {
		return null;
	}

	return (
		<div className="pt-4 border-t">
			<h3 className="text-lg mb-4">Parameter Overrides</h3>
			<LazySchemaForm
				schema={schema}
				errors={errors}
				values={values}
				onValuesChange={setValues}
				kinds={["json"]}
				skipDefaultValueInitialization
			/>
		</div>
	);
};
