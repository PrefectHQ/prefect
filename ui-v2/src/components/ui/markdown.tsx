import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownProps = {
	text: string;
};

export const Markdown = ({ text }: MarkdownProps) => (
	<div className="prose max-w-none">
		<ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
	</div>
);
