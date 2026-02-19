import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Download, Loader } from "lucide-react";

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  exportType: "event" | "session";
  filter: "all" | "present" | "absent";
  onFilterChange: (filter: "all" | "present" | "absent") => void;
  onConfirm: () => void;
  downloading: boolean;
  title?: string;
  description?: string;
}

export function ExportDialog({
  open,
  onOpenChange,
  exportType,
  filter,
  onFilterChange,
  onConfirm,
  downloading,
  title,
  description,
}: ExportDialogProps) {
  const defaultTitle = `Export ${exportType === "event" ? "Event" : "Session"} Report`;
  const defaultDescription = "Generate a polished PDF attendance report with your preferred attendee filter.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-primary" />
            {title || defaultTitle}
          </DialogTitle>
          <DialogDescription>
            {description || defaultDescription}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
            <p className="text-sm font-medium">Filter Attendees</p>
            <Select
              value={filter}
              onValueChange={(value: "all" | "present" | "absent") =>
                onFilterChange(value)
              }
            >
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Choose which attendees to include" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Attendees</SelectItem>
                <SelectItem value="present">Present Only</SelectItem>
                <SelectItem value="absent">Absent Only</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {filter === "all" &&
                "Includes both present and absent attendees."}
              {filter === "present" &&
                "Includes only attendees marked present."}
              {filter === "absent" &&
                "Includes only attendees marked absent."}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-md border bg-background/60 px-3 py-2">
              <span className="block font-semibold">Scope</span>
              <span className="text-muted-foreground">
                {exportType === "event" ? "Entire Event" : "Single Session"}
              </span>
            </div>
            <div className="rounded-md border bg-background/60 px-3 py-2">
              <span className="block font-semibold">Format</span>
              <span className="text-muted-foreground">PDF</span>
            </div>
            <div className="rounded-md border bg-background/60 px-3 py-2">
              <span className="block font-semibold">Filter</span>
              <span className="text-muted-foreground capitalize">
                {filter}
              </span>
            </div>
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={downloading}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            className="gap-2"
            disabled={downloading}
          >
            {downloading ? (
              <>
                <Loader className="h-4 w-4 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Export as PDF
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}