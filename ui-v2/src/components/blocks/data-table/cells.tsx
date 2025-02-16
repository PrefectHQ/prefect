import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { useToast } from "@/hooks/use-toast";
import type { CellContext, HeaderContext } from "@tanstack/react-table";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { buildDeleteBlockDocumentQuery } from "@/api/block-documents";

type BlockDocument = components["schemas"]["BlockDocument"];

export const SelectHeaderCell = ({ table }: HeaderContext<BlockDocument, unknown>) => {
  return (
    <Checkbox
      checked={table.getIsAllPageRowsSelected()}
      onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
      aria-label="Select all"
    />
  );
};

export const SelectCell = ({ row }: CellContext<BlockDocument, unknown>) => {
  return (
    <Checkbox
      checked={row.getIsSelected()}
      onCheckedChange={(value) => row.toggleSelected(!!value)}
      aria-label="Select row"
    />
  );
};

export const NameCell = ({ row }: CellContext<BlockDocument, unknown>) => {
  return <div className="font-medium">{row.original.name}</div>;
};

export const TypeCell = ({ row }: CellContext<BlockDocument, unknown>) => {
  return <div>{row.original.block_type_name}</div>;
};

export const ActionsCell = ({ row }: CellContext<BlockDocument, unknown>) => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const id = row.original.id;
  const deleteMutation = useMutation({
    mutationFn: buildDeleteBlockDocumentQuery(id).queryFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["block-documents"] });
      toast({
        title: "Block document deleted",
      });
    },
    onError: () => {
      toast({
        title: "Failed to delete block document",
        variant: "destructive",
      });
    },
  });

  if (!id) return null;

  return (
    <div className="flex flex-row justify-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="h-8 w-8 p-0">
            <span className="sr-only">Open menu</span>
            <Icon id="MoreVertical" className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Actions</DropdownMenuLabel>
          <DropdownMenuItem
            onClick={() => {
              void navigator.clipboard.writeText(id);
              toast({
                title: "ID copied",
              });
            }}
          >
            Copy ID
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              void navigator.clipboard.writeText(row.original.name ?? "");
              toast({
                title: "Name copied",
              });
            }}
          >
            Copy Name
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              deleteMutation.mutate();
            }}
            className="text-destructive"
          >
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
