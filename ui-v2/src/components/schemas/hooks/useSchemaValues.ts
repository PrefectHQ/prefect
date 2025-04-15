import { useState } from "react";
import type { SchemaFormValues } from "../types/values";

export function useSchemaFormValues(
	initialValues: SchemaFormValues = {},
): [SchemaFormValues, (values: SchemaFormValues) => void] {
	const [values, setValues] = useState<SchemaFormValues>(initialValues);

	return [values, setValues];
}
