import { Trash2, AlertTriangle } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface DeleteConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  itemName?: string
  isLoading?: boolean
  onConfirm: () => void | Promise<void>
  warningText?: string
  confirmText?: string
  consequences?: string[]
}

export function DeleteConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  itemName,
  isLoading = false,
  onConfirm,
  warningText,
  confirmText = 'Delete',
  consequences = []
}: DeleteConfirmDialogProps) {
  const handleConfirm = async () => {
    try {
      await onConfirm()
      onOpenChange(false)
    } catch (error) {
      // Error handling is done by the API client
      console.error('Delete operation failed:', error)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-3">
            <p>{description}</p>
            
            {itemName && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Item:</span>
                <Badge variant="outline" className="font-mono">
                  {itemName}
                </Badge>
              </div>
            )}

            {consequences.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-orange-600 dark:text-orange-400">
                  This action will also:
                </p>
                <ul className="text-sm space-y-1 pl-4">
                  {consequences.map((consequence, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <span className="text-orange-500 mt-1">•</span>
                      <span>{consequence}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {warningText && (
              <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-md">
                <p className="text-sm text-red-800 dark:text-red-200 font-medium">
                  ⚠️ {warningText}
                </p>
              </div>
            )}

            <p className="text-sm text-muted-foreground font-medium">
              This action cannot be undone.
            </p>
          </AlertDialogDescription>
        </AlertDialogHeader>
        
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>
            Cancel
          </AlertDialogCancel>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isLoading}
            className="min-w-[100px]"
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Deleting...
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Trash2 className="h-4 w-4" />
                {confirmText}
              </div>
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// Specialized delete dialogs for different entity types
export function DeletePatientDialog({
  open,
  onOpenChange,
  patient,
  isLoading,
  onConfirm
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  patient?: { id: string; first_name: string; last_name: string; patient_id: string }
  isLoading: boolean
  onConfirm: () => void | Promise<void>
}) {
  return (
    <DeleteConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Delete Patient Record"
      description="Are you sure you want to delete this patient record? This will permanently remove all patient data including medical history, appointments, and related information."
      itemName={patient ? `${patient.first_name} ${patient.last_name} (${patient.patient_id})` : ''}
      isLoading={isLoading}
      onConfirm={onConfirm}
      warningText="This will delete all associated appointments, medical records, and audit logs for this patient."
      consequences={[
        'Delete all appointment records',
        'Remove medical history and notes',
        'Clear emergency contact information',
        'Remove from all statistics and reports'
      ]}
    />
  )
}

export function DeleteAppointmentDialog({
  open,
  onOpenChange,
  appointment,
  isLoading,
  onConfirm
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment?: { id: string; appointment_id: string; date: string; time: string; reason: string }
  isLoading: boolean
  onConfirm: () => void | Promise<void>
}) {
  return (
    <DeleteConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Cancel Appointment"
      description="Are you sure you want to cancel this appointment? The patient and doctor will need to be notified of the cancellation."
      itemName={appointment ? `${appointment.appointment_id} - ${appointment.date} ${appointment.time}` : ''}
      isLoading={isLoading}
      onConfirm={onConfirm}
      confirmText="Cancel Appointment"
      consequences={[
        'Free up the time slot for other patients',
        'Update appointment statistics',
        'Create audit log entry'
      ]}
    />
  )
}

export function DeleteUserDialog({
  open,
  onOpenChange,
  user,
  isLoading,
  onConfirm
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: { id: string; username: string; email: string; role: string }
  isLoading: boolean
  onConfirm: () => void | Promise<void>
}) {
  return (
    <DeleteConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Deactivate User Account"
      description="Are you sure you want to deactivate this user account? The user will no longer be able to access the system."
      itemName={user ? `${user.username} (${user.email})` : ''}
      isLoading={isLoading}
      onConfirm={onConfirm}
      confirmText="Deactivate User"
      warningText="User accounts are deactivated rather than deleted to maintain audit trail integrity."
      consequences={[
        'Revoke all access permissions',
        'Invalidate current sessions',
        'Preserve audit history',
        'Maintain referential integrity'
      ]}
    />
  )
}
