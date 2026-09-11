import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import {
	useCallback,
	useEffect,
	useId,
	useMemo,
	useRef,
	useState,
} from "react";
import { DropdownMenuItem } from "../ui/dropdown-menu";
import { SchemaFormInput } from "./schema-form-input";
import { SchemaFormPropertyDescription } from "./schema-form-property-description";
import { SchemaFormPropertyErrors } from "./schema-form-property-errors";
import { SchemaFormPropertyLabel } from "./schema-form-property-label";
import { SchemaFormPropertyMenu } from "./schema-form-property-menu";
import {
	isSchemaValueIndexError,
	isSchemaValuePropertyError,
	type SchemaFormErrors,
	type SchemaValueIndexError,
	type SchemaValuePropertyError,
} from "./types/errors";
import { useSchemaFormContext } from "./use-schema-form-context";
import { getIndexForAnyOfPropertyValue } from "./utilities/getIndexForAnyOfPropertyValue";
import { isArray, isDefined } from "./utilities/guards";
import { mergeSchemaPropertyDefinition } from "./utilities/mergeSchemaPropertyDefinition";

export type SchemaFormPropertyProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject | ReferenceObject;
	required: boolean;
	errors: SchemaFormErrors;
	showLabel?: boolean;
	nested?: boolean;
};

export function SchemaFormProperty({
	property: propertyDefinition,
	value,
	onValueChange,
	required,
	errors,
	showLabel = true,
	nested = true,
}: SchemaFormPropertyProps) {
	const { schema, skipDefaultValueInitialization } = useSchemaFormContext();

	const property = useMemo(() => {
		return mergeSchemaPropertyDefinition(propertyDefinition, schema);
	}, [propertyDefinition, schema]);

	const unknownPropertyType = useMemo(() => {
		return !isDefined(property.type);
	}, [property.type]);

	const nestedErrors = useMemo(() => {
		return errors.filter(
			(error): error is SchemaValuePropertyError | SchemaValueIndexError =>
				isSchemaValuePropertyError(error) || isSchemaValueIndexError(error),
		);
	}, [errors]);

	const [initialized, setInitialized] = useState(false);
	const [internalValue, setInternalValue] = useState(getInitialValue);
	const [omitted, setOmitted] = useState(false);
	const emittedValue = useRef<{ value: unknown } | null>(null);
	const id = useId();

	const shouldOmitRequiredArray = useCallback(
		(value: unknown) => {
			if (!required || !isArray(value)) {
				return false;
			}

			const anyOfIndex = getIndexForAnyOfPropertyValue({
				value,
				property,
				schema,
			});
			const arrayProperty = property.anyOf?.[anyOfIndex]
				? mergeSchemaPropertyDefinition(property.anyOf[anyOfIndex], schema)
				: property;
			const minItems =
				"minItems" in arrayProperty &&
				typeof arrayProperty.minItems === "number"
					? arrayProperty.minItems
					: 1;

			return value.length < minItems;
		},
		[property, required, schema],
	);

	const handleValueChange = useCallback(
		(value: unknown) => {
			setInternalValue(value);

			if (shouldOmitRequiredArray(value)) {
				emittedValue.current = { value: undefined };
				onValueChange(undefined);
				return;
			}

			emittedValue.current = { value };
			onValueChange(value);
		},
		[onValueChange, shouldOmitRequiredArray],
	);

	const handleOmittedChange = useCallback(() => {
		const isOmitted = !omitted;

		setOmitted(isOmitted);

		if (isOmitted) {
			onValueChange(undefined);
			return;
		}

		handleValueChange(internalValue);
	}, [omitted, onValueChange, handleValueChange, internalValue]);

	useEffect(() => {
		if (initialized || skipDefaultValueInitialization) {
			return;
		}

		if (isDefined(property.default) && !isDefined(value)) {
			onValueChange(property.default);
		}

		setInitialized(true);
	}, [
		initialized,
		skipDefaultValueInitialization,
		onValueChange,
		property.default,
		value,
	]);

	// The parent propagates values asynchronously, so it can echo back a value that
	// is older than what the user has already typed. Only accept a value from the
	// parent once it has caught up with the last value emitted from this property,
	// otherwise in-flight edits get overwritten.
	useEffect(() => {
		if (emittedValue.current) {
			if (Object.is(emittedValue.current.value, value)) {
				emittedValue.current = null;
			}

			return;
		}

		if (isDefined(value)) {
			setInternalValue(value);

			if (shouldOmitRequiredArray(value)) {
				onValueChange(undefined);
			}
		}
	}, [onValueChange, shouldOmitRequiredArray, value]);

	function getInitialValue() {
		if (isDefined(value)) {
			return value;
		}

		if (isDefined(property.default) && !skipDefaultValueInitialization) {
			return property.default;
		}

		return undefined;
	}

	return (
		<div className="flex flex-col gap-2 group">
			{showLabel && (
				<div className="grid grid-cols-[1fr_auto] items-center gap-2">
					<div className="flex flex-col gap-1">
						<SchemaFormPropertyLabel
							property={property}
							required={required}
							id={id}
						/>
						<SchemaFormPropertyDescription property={property} />
					</div>
					<div className="ml-auto">
						<SchemaFormPropertyMenu
							value={value}
							onValueChange={handleValueChange}
							property={property}
							disableKinds={unknownPropertyType}
							defaultValue={property.default}
							hasDefaultValue={isDefined(property.default)}
						>
							<DropdownMenuItem onClick={handleOmittedChange}>
								{omitted ? "Include value" : "Omit value"}
							</DropdownMenuItem>
						</SchemaFormPropertyMenu>
					</div>
				</div>
			)}

			{!showLabel && <SchemaFormPropertyDescription property={property} />}

			<fieldset disabled={omitted}>
				<SchemaFormInput
					property={property}
					value={internalValue}
					onValueChange={handleValueChange}
					errors={nestedErrors}
					id={id}
					nested={nested}
				/>
			</fieldset>

			<SchemaFormPropertyErrors errors={errors} />
		</div>
	);
}
