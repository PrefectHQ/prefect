import { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { createContext, useContext } from "react";
import { PrefectKind } from "./types/prefect-kind";

export type SchemaFormContext = {
	schema: SchemaObject & ObjectSubtype;
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
