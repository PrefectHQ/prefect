import { useMemo } from "react";
import { isSchemaValueError, type SchemaFormErrors } from "./types/errors";

export type SchemaFormPropertyErrorsProps = {
	errors: SchemaFormErrors;
};

export function SchemaFormPropertyErrors({
	errors,
}: SchemaFormPropertyErrorsProps) {
	const propertyErrors = useMemo(() => {
		return errors.filter((error) => isSchemaValueError(error));
	}, [errors]);

	if (propertyErrors.length === 0) {
		return null;
	}

	if (propertyErrors.length === 1) {
		return <p className="text-red-500 text-sm">{propertyErrors[0]}</p>;
	}

	return (
		<ul className="list-disc text-red-500 text-sm pl-4">
			{propertyErrors.map((error) => (
				<li key={error}>{error}</li>
			))}
		</ul>
	);
}
