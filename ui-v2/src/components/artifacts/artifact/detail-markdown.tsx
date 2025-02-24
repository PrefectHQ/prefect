import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type DetailMarkdownProps = {
	markdown: string;
};

export const DetailMarkdown = ({ markdown }: DetailMarkdownProps) => {
	return (
		<div data-testid="markdown-display" className="mt-4 prose">
			<Markdown remarkPlugins={[remarkGfm]}>{markdown}</Markdown>
		</div>
	);
};
