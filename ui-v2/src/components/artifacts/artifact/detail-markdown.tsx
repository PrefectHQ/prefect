import { LazyMarkdown } from "@/components/ui/lazy-markdown";

export type DetailMarkdownProps = {
	markdown: string;
};

export const DetailMarkdown = ({ markdown }: DetailMarkdownProps) => {
	return (
		<div data-testid="markdown-display" className="mt-4 prose">
			<LazyMarkdown>{markdown}</LazyMarkdown>
		</div>
	);
};
