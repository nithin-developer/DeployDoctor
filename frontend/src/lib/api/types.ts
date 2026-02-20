export interface Appointment {
  id: string;
  appointment_id: string;
  appointment_time: string;
  appointment_type: string;
  status: string;
  reason?: string;
  notes?: string;
  patient_id?: string;
  doctor_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Patient {
  patient_id: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
}

export interface User {
  id?: string;
  first_name: string;
  last_name: string;
  email: string;
}
