import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { Link } from "@tanstack/react-router";
import type { components } from "@/api/prefect";

type BlockDocument = components["schemas"]["BlockDocument"];

export function BlocksTableActions({ row }: { row: { original: BlockDocument } }) {
  const copyNameToClipboard = () => {
    void navigator.clipboard.writeText(row.original.name);
  };

  return (
    <div className="flex justify-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="h-8 w-8 p-0">
            <Icon id="MoreHorizontal" className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link
              to="/blocks/block/$blockDocumentId/edit"
              params={{ blockDocumentId: row.original.id }}
            >
              Edit
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={copyNameToClipboard}>Copy Name</DropdownMenuItem>
          <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}