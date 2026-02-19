import { Activity, Users, Calendar, Layers3, Clock, CheckCircle2, AlertTriangle, GraduationCap, RefreshCw, BarChart3 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { dashboardApi } from '@/api/dashboard/index';
import type { UserDashboard as UserDashboardData } from '@/api/dashboard/index';
import { Link } from 'react-router-dom';

import { Header } from '@/components/layout/header';
import { Main } from '@/components/layout/main';
import { Search } from '@/components/search';
import { ThemeSwitch } from '@/components/theme-switch';
import { ProfileDropdown } from '@/components/profile-dropdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { format, parseISO } from 'date-fns';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: number | string;
  sub: string;
}

function StatCard({ icon: Icon, label, value, sub }: StatCardProps) {
  return (
    <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
      <CardContent className="relative p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{sub}</p>
          </div>
          <div className="h-12 w-12 rounded-xl bg-primary/10 ring-1 ring-primary/20 flex items-center justify-center">
            <Icon className="h-6 w-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<UserDashboardData | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const result = await dashboardApi.getDashboard();
      setData(result);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <Header>
        <Search />
        <div className="ml-auto flex items-center space-x-4">
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className="space-y-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
              <p className="text-sm text-muted-foreground mt-1">Overview of your platform activity.</p>
            </div>
            <div className="flex gap-2 items-center">
              <Badge variant="outline" className="flex items-center">
                <Activity className="h-4 w-4 mr-1" />
                Overview
              </Badge>
              <Button variant="outline" size="icon" onClick={load} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {loading && (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-32 w-full" />
                ))}
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <Skeleton className="h-96 lg:col-span-2" />
                <Skeleton className="h-96" />
              </div>
            </>
          )}

          {!loading && data && (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard icon={Layers3} label="Total Batches" value={data.stats.total_batches} sub="Active batches" />
                <StatCard icon={Users} label="Active Trainers" value={data.stats.total_trainers} sub="Registered trainers" />
                <StatCard icon={GraduationCap} label="Total Students" value={data.stats.total_students} sub="Enrolled students" />
                <StatCard icon={Calendar} label="Events This Month" value={data.stats.events_this_month} sub="Active events" />
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard icon={Clock} label="Sessions Today" value={data.stats.sessions_today} sub="Scheduled for today" />
                <StatCard icon={CheckCircle2} label="Completed Today" value={data.stats.sessions_completed_today} sub="Attendance taken" />
                <StatCard icon={Calendar} label="Upcoming (7 days)" value={data.stats.sessions_upcoming} sub="Next week sessions" />
                <StatCard icon={AlertTriangle} label="Missing Attendance" value={data.stats.sessions_past_no_attendance} sub="Last 30 days" />
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2 relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
                  <CardHeader className="relative">
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5 text-primary" />
                      Recent Events Activity
                    </CardTitle>
                    <CardDescription>Latest events with session completion status</CardDescription>
                  </CardHeader>
                  <CardContent className="relative">
                    {data.recent_events.length === 0 ? (
                      <div className="text-sm text-muted-foreground py-8 text-center border border-dashed rounded-md">
                        No recent events
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {data.recent_events.map((ev) => (
                          <Link key={ev.id} to={`/events/${ev.id}`}>
                            <div className="flex items-center justify-between p-3 rounded-lg border border-border/60 hover:border-border hover:bg-accent/50 transition-all">
                              <div className="flex-1 min-w-0">
                                <div className="font-medium truncate">{ev.name}</div>
                                <div className="text-xs text-muted-foreground">
                                  {ev.batch_name} • {format(parseISO(ev.start_date), 'MMM d')} - {format(parseISO(ev.end_date), 'MMM d, yyyy')}
                                </div>
                              </div>
                              <div className="flex items-center gap-3 ml-4">
                                <Badge variant="outline" className="text-xs">
                                  {ev.completed_sessions}/{ev.total_sessions} Sessions
                                </Badge>
                              </div>
                            </div>
                          </Link>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="relative overflow-hidden border border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/50">
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/10 opacity-100" />
                  <CardHeader className="relative">
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5 text-primary" />
                      Attendance Summary
                    </CardTitle>
                    <CardDescription>Attendance completion metrics</CardDescription>
                  </CardHeader>
                  <CardContent className="relative space-y-4">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        Completion Rate
                      </span>
                      <span className="text-lg font-bold text-green-600">{data.stats.attendance_completion_rate}%</span>
                    </div>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-blue-500" />
                          Today&apos;s Sessions
                        </span>
                        <span className="font-medium">{data.stats.sessions_today}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                          Completed Today
                        </span>
                        <span className="font-medium">{data.stats.sessions_completed_today}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-purple-500" />
                          Upcoming
                        </span>
                        <span className="font-medium">{data.stats.sessions_upcoming}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                          Missing Records
                        </span>
                        <span className="font-medium">{data.stats.sessions_past_no_attendance}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </div>
      </Main>
    </>
  );
}
