import type { ComponentProps } from "react";
import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

const MarkdownInputLazy = lazy(() =>
	import("./markdown-input").then((mod) => ({ default: mod.MarkdownInput })),
);

type LazyMarkdownInputProps = ComponentProps<typeof MarkdownInputLazy>;

export function LazyMarkdownInput({
	className,
	...props
}: LazyMarkdownInputProps) {
	return (
		<Suspense
			fallback={<Skeleton className={`min-h-[200px] ${className ?? ""}`} />}
		>
			<MarkdownInputLazy className={className} {...props} />
		</Suspense>
	);
}
