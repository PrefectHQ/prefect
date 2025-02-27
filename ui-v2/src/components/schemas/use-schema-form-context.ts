import { createContext, useContext } from "react";
import { PrefectKind } from "./types/prefect-kind";
import { PrefectSchemaObject } from "./types/schemas";

export type SchemaFormContext = {
	schema: PrefectSchemaObject;
	kinds: PrefectKind[];
	skipDefaultValueInitialization?: boolean;
};

export const SchemaFormContext = createContext<SchemaFormContext | null>(null);

export function useSchemaFormContext() {
	const context = useContext(SchemaFormContext);

	if (!context) {
		throw new Error(
			"useSchemaFormContext must be used within a SchemaFormProvider",
		);
	}

	return context;
}
