import clsx from "clsx";
import { Fragment, useMemo } from "react";

type BlockDocumentSchemaProperties = {
	data: { [key: string]: unknown };
	fields: { [key: string]: unknown };
};
export function BlockDocumentSchemaProperties({
	data,
	fields,
}: BlockDocumentSchemaProperties) {
	const fieldValues = useMemo(() => {
		let properties: { [key: string]: unknown } = {};
		if ("properties" in fields) {
			properties = fields.properties as { [key: string]: unknown };
		}

		return Object.keys(properties).map((property) => {
			let label = property;
			// nb: expect this type from Prefect Schema
			const field = properties[property] as {
				[key: string]: unknown;
				title: string;
			};
			if (field.title) {
				label = field.title;
			}

			return {
				label,
				value: data[property] ? JSON.stringify(data[property], null, 2) : null,
			};
		});
	}, [data, fields]);

	return (
		<dl className="flex flex-col gap-2 p-2 text-xs">
			{fieldValues.map(({ label, value }) => (
				<Fragment key={label}>
					<dt className="text-gray-500 text-sm">{label}</dt>
					<dd className={clsx("text-base", !value && "text-gray-500 ")}>
						{value ?? "None"}
					</dd>
				</Fragment>
			))}
		</dl>
	);
}
