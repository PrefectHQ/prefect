import { useState } from "react";
import { SchemaFormErrors } from "../types/errors";

export function useSchemaFormErrors(
	initialErrors: SchemaFormErrors = [],
): [SchemaFormErrors, (errors: SchemaFormErrors) => void] {
	const [errors, setErrors] = useState<SchemaFormErrors>(initialErrors);

	return [errors, setErrors];
}
