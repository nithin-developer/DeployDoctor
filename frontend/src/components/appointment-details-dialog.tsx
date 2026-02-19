import { format } from 'date-fns'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { 
  Calendar, 
  Clock, 
  User, 
  Stethoscope, 
  FileText, 
  Edit, 
  Trash2, 
  Phone, 
  Mail 
} from 'lucide-react'
import type { Appointment, User as UserType, Patient } from '@/lib/api/types'

interface AppointmentDetailsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment: Appointment | null
  patient: Patient | null
  doctor: UserType | null
  onEdit?: (appointmentId: string) => void
  onDelete?: (appointmentId: string) => void
  canEdit?: boolean
}

export function AppointmentDetailsDialog({
  open,
  onOpenChange,
  appointment,
  patient,
  doctor,
  onEdit,
  onDelete,
  canEdit = false
}: AppointmentDetailsDialogProps) {
  if (!appointment) return null

  const appointmentDate = new Date(appointment.appointment_time)
  
  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'scheduled':
        return 'default'
      case 'completed':
        return 'secondary'
      case 'cancelled':
        return 'destructive'
      case 'no-show':
        return 'outline'
      default:
        return 'secondary'
    }
  }

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'emergency':
        return 'destructive'
      case 'consultation':
        return 'default'
      case 'follow-up':
        return 'secondary'
      case 'procedure':
        return 'outline'
      default:
        return 'secondary'
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Appointment Details
          </DialogTitle>
          <DialogDescription>
            Appointment ID: {appointment.appointment_id}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Status and Type */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Status:</span>
              <Badge variant={getStatusBadgeVariant(appointment.status)}>
                {appointment.status}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Type:</span>
              <Badge variant={getTypeBadgeVariant(appointment.appointment_type)}>
                {appointment.appointment_type}
              </Badge>
            </div>
          </div>

          <Separator />

          {/* Date and Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Date</p>
                <p className="text-sm text-muted-foreground">
                  {format(appointmentDate, 'EEEE, MMMM d, yyyy')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Time</p>
                <p className="text-sm text-muted-foreground">
                  {format(appointmentDate, 'h:mm a')}
                </p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Patient Information */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-sm font-semibold">Patient Information</h4>
            </div>
            {patient ? (
              <div className="ml-6 space-y-2">
                <p className="text-sm">
                  <span className="font-medium">Name:</span> {patient.first_name} {patient.last_name}
                </p>
                <p className="text-sm">
                  <span className="font-medium">Patient ID:</span> {patient.patient_id}
                </p>
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
                  {patient.email && (
                    <div className="flex items-center gap-1 text-sm">
                      <Mail className="h-3 w-3" />
                      {patient.email}
                    </div>
                  )}
                  {patient.phone && (
                    <div className="flex items-center gap-1 text-sm">
                      <Phone className="h-3 w-3" />
                      {patient.phone}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="ml-6 text-sm text-muted-foreground">Patient information not available</p>
            )}
          </div>

          <Separator />

          {/* Doctor Information */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Stethoscope className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-sm font-semibold">Doctor Information</h4>
            </div>
            {doctor ? (
              <div className="ml-6 space-y-2">
                <p className="text-sm">
                  <span className="font-medium">Name:</span> Dr. {doctor.first_name} {doctor.last_name}
                </p>
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
                  <div className="flex items-center gap-1 text-sm">
                    <Mail className="h-3 w-3" />
                    {doctor.email}
                  </div>
                </div>
              </div>
            ) : (
              <p className="ml-6 text-sm text-muted-foreground">Doctor information not available</p>
            )}
          </div>

          <Separator />

          {/* Reason and Notes */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-sm font-semibold">Appointment Details</h4>
            </div>
            <div className="ml-6 space-y-3">
              <div>
                <p className="text-sm font-medium mb-1">Reason for Visit:</p>
                <p className="text-sm text-muted-foreground bg-muted p-3 rounded-md">
                  {appointment.reason || 'No reason provided'}
                </p>
              </div>
              {appointment.notes && (
                <div>
                  <p className="text-sm font-medium mb-1">Additional Notes:</p>
                  <p className="text-sm text-muted-foreground bg-muted p-3 rounded-md">
                    {appointment.notes}
                  </p>
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Appointment Info */}
          <div className="text-xs text-muted-foreground space-y-1">
            <p>Created: {format(new Date(appointment.created_at), 'PPpp')}</p>
            <p>Last Updated: {format(new Date(appointment.updated_at), 'PPpp')}</p>
          </div>

          {/* Action Buttons */}
          {canEdit && (
            <div className="flex flex-col sm:flex-row justify-end gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onEdit?.(appointment.id)}
                className="flex items-center gap-2 w-full sm:w-auto"
              >
                <Edit className="h-4 w-4" />
                Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => onDelete?.(appointment.id)}
                className="flex items-center gap-2 w-full sm:w-auto"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
