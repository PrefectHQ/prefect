# Schema Forms
Prefect uses schema generated forms for several features:

- Deployment parameters
- Work Pool configuration
- Automation actions (for deployment parameters)

## Example form

```tsx
import { SchemaForm, useSchemaFormValues, useSchemaFormErrors } from "@/components/schemas";

const [values, setValues] = useSchemaFormValues();
const [errors, setErrors] = useSchemaFormErrors();

const schema = {
  type: "object",
  properties: {
    name: { type: "string", title: "Name" },
  },
};

<SchemaForm
  schema={schema}
  values={values}
  errors={errors}
  onValuesChange={setValues}
  kinds={["json"]}
/>
```

## Validation
Validation of values is done on the server side. The form will return errors that can be displayed to the user. To validate the values, use the `validateSchemaValues` function.

```ts
import { validateSchemaValues } from "@/components/schemas";

const errors = await validateSchemaValues(schema, values);
```

## Types

The schema form uses the `PrefectSchemaObject` type to define the schema.

## Prefect Kind Values
A value can dictate the type of input that is rendered by using the `__prefect_kind` property. Using this property, the form will know how to render the value. For this example a json input will be rendered rather than the default object input.

```tsx
import { SchemaForm, useSchemaForm, type PrefectSchemaObject } from "@/components/schemas";

const schema = {
	type: "object",
	properties: {
		name: { type: "string", title: "Name" },
	},
} satisfies PrefectSchemaObject;

const App = () => {
	const { setValues, values, errors, validateForm } = useSchemaForm();

	const handleValidateForm = () => validateForm({ schema });

	return (
		<div>
			<SchemaForm
				schema={schema}
				values={values}
				errors={errors}
				onValuesChange={setValues}
				kinds={["json"]}
			/>
			<button onClick={handleValidateForm}>Validate</button>
		</div>
	);
};
```

## Default Values
By default, the form will use the `default` property to set the initial value of all fields when the form is rendered. In this example, the name field will be pre-filled with "John Doe" because the values object has no name property.

```ts
const schema: PrefectSchemaObject = {
  type: "object",
  properties: {
    name: { type: "string", title: "Name", default: "John Doe" },
  },
};

const values = {}

<SchemaForm
  schema={schema}
  values={values}
  errors={errors}
  onValuesChange={setValues}
  kinds={["json"]}
/>
```

> **Note**
> This can be disabled by setting the `skipDefaultValueInitialization` prop to `true`.

