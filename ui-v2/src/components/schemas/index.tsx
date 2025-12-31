import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { SchemaFormProps } from "./schema-form";

export { useSchemaForm } from "./hooks/useSchemaForm";
export { useSchemaFormErrors } from "./hooks/useSchemaFormErrors";
export { useSchemaFormValues } from "./hooks/useSchemaValues";
export { SchemaForm } from "./schema-form";
export type { PrefectSchemaObject } from "./types/schemas";
export { useSchemaFormContext } from "./use-schema-form-context";
export { validateSchemaValues } from "./utilities/validate";

const SchemaFormLazy = lazy(() =>
	import("./schema-form").then((mod) => ({ default: mod.SchemaForm })),
);

export function LazySchemaForm(props: SchemaFormProps) {
	return (
		<Suspense fallback={<Skeleton className="min-h-[300px] w-full" />}>
			<SchemaFormLazy {...props} />
		</Suspense>
	);
}
