import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { CopyBlock, nord } from "react-code-blocks";

type ArtifactDataDisplayProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

export const ArtifactDataDisplay = ({ artifact }: ArtifactDataDisplayProps) => {
	const [showData, setShowData] = useState(false);

	const toggleShowData = () => {
		setShowData((val) => !val);
	};

	return (
		<div className="mt-4 flex flex-col justify-center items-center">
			<Button
				data-testid="show-raw-data-button"
				variant={"outline"}
				onClick={toggleShowData}
			>
				{showData ? "Hide" : "Show"} Raw Data
			</Button>
			{showData && (
				<div className="mt-4 max-w-5xl overflow-x-scroll">
					<CopyBlock
						text={artifact.data as string}
						language="text"
						theme={nord}
						showLineNumbers
					/>
				</div>
			)}
		</div>
	);
};
