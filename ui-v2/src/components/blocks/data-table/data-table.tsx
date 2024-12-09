import { DataTable } from "@/components/ui/data-table";
import {
  useReactTable,
  getCoreRowModel,
  type ColumnDef,
  type PaginationState,
  type OnChangeFn,
} from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { BlocksTableActions } from "@/components/blocks/data-table/actions";
import { BlockNameCell, BlockTypeCell } from "@/components/blocks/data-table/cells";
import { useCallback, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";


type BlockDocument = components["schemas"]["BlockDocument"];

const columns: ColumnDef<BlockDocument>[] = [

  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "name", 
    header: "Block",
    cell: BlockNameCell,
    enableSorting: true,
    enableColumnFilter: true,
  },
  {
    accessorKey: "block_type",
    header: "Type", 
    cell: BlockTypeCell,
    enableSorting: false,
  },
  {
    id: "actions",
    cell: BlocksTableActions,
    enableSorting: false,
    enableHiding: false,
  },
];

interface BlocksDataTableProps {
  blocks: BlockDocument[];
  currentBlockCount: number;
  pagination: PaginationState;
  onPaginationChange: (newPagination: PaginationState) => void;
}

export function BlocksDataTable({
  blocks,
  currentBlockCount,
  pagination,
  onPaginationChange,
}: BlocksDataTableProps) {
  const [rowSelection, setRowSelection] = useState({});

  const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
    (updater) => {
      let newPagination = pagination;
      if (typeof updater === "function") {
        newPagination = updater(pagination);
      } else {
        newPagination = updater;
      }
      onPaginationChange(newPagination);
    },
    [pagination, onPaginationChange]
  );

  const table = useReactTable({
    data: blocks,
    columns,
    state: {
      pagination,
      rowSelection,
    },
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    onPaginationChange: handlePaginationChange,
    rowCount: currentBlockCount,
    defaultColumn: {
      maxSize: 300,
    },
  });

  return <DataTable table={table} />;
}