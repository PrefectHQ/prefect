import { EditorView, useCodeMirror } from "@uiw/react-codemirror";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type ArtifactDataDisplayProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDataDisplay = ({ artifact }: ArtifactDataDisplayProps) => {
	const [showData, setShowData] = useState(false);

	const toggleShowData = () => {
		setShowData((val) => !val);
	};

	const editor = useRef<HTMLDivElement | null>(null);
	const basicSetup = {
		highlightActiveLine: false,
		foldGutter: false,
		highlightActiveLineGutter: false,
	};
	const { setContainer } = useCodeMirror({
		container: editor.current,
		extensions: [EditorView.lineWrapping],
		value: String(artifact.data),
		indentWithTab: false,
		editable: true,
		basicSetup,
	});

	useEffect(() => {
		if (editor.current) {
			setContainer(editor.current);
		}
	}, [setContainer]);

	const handleCopy = (_value: string) => {
		toast.success("Copied to clipboard");
		void navigator.clipboard.writeText(_value);
	};

	return (
		<div className="flex flex-col justify-center items-center">
			<Button
				data-testid="show-raw-data-button"
				variant={"outline"}
				onClick={toggleShowData}
				className="my-4"
			>
				{showData ? "Hide" : "Show"} Raw Data
			</Button>

			<div
				className="rounded-md border shadow-xs focus-within:outline-hidden focus-within:ring-1 focus-within:ring-ring relative"
				style={{
					display: showData ? "block" : "none",
				}}
				ref={(node) => {
					editor.current = node;
				}}
				data-testid="raw-data-display"
			>
				<Button
					onClick={() => handleCopy(artifact.data as string)}
					variant="ghost"
					size="icon"
					className="absolute top-0 right-0 z-10"
					aria-label="copy"
				>
					<Icon id="Copy" className="size-2" />
				</Button>
			</div>
		</div>
	);
};
