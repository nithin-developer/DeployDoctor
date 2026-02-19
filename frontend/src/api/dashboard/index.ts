import { apiClient } from '../http';

export interface DashboardStats {
  total_batches: number;
  total_trainers: number;
  total_students: number;
  events_this_month: number;
  sessions_today: number;
  sessions_completed_today: number;
  sessions_upcoming: number;
  sessions_past_no_attendance: number;
  attendance_completion_rate: number;
}

export interface RecentEvent {
  id: string;
  name: string;
  batch_name: string | null;
  start_date: string;
  end_date: string;
  total_sessions: number;
  completed_sessions: number;
  created_at: string;
}

export interface UserDashboard {
  stats: DashboardStats;
  recent_events: RecentEvent[];
}

export const dashboardApi = {
  async getDashboard(): Promise<UserDashboard> {
    const response = await apiClient.get('/api/dashboard/super-admin');
    return response.data;
  },
};

