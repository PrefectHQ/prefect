import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { SchemaFormProps } from "./schema-form";

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
