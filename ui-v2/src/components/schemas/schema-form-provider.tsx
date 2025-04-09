import type { ReactNode } from "react";
import { SchemaFormContext } from "./use-schema-form-context";

type SchemaFormProviderProps = SchemaFormContext & {
	children: ReactNode;
};

export const SchemaFormProvider = ({
	children,
	...context
}: SchemaFormProviderProps) => {
	return (
		<SchemaFormContext.Provider value={context}>
			{children}
		</SchemaFormContext.Provider>
	);
};
