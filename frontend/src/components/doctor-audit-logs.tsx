import { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { useUserAuditLogs } from '../hooks/use-api'
import {
  Activity,
  Search as SearchIcon,
  Download,
  Filter,
  Eye,
  Edit,
  Trash,
  Plus,
  User,
  Calendar,
  Loader2
} from 'lucide-react'

interface DoctorAuditLogsProps {
  className?: string
}

interface AuditLogRow {
  id: string
  action?: string
  details?: string
  entityId?: string
  entityType?: string
  timestamp: string
  ipAddress?: string
}

export function DoctorAuditLogs({ className }: DoctorAuditLogsProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [actionFilter, setActionFilter] = useState<string>('all')
  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Fetch audit logs from API with pagination
  const { 
    data: auditLogsResponse, 
    isLoading, 
    error 
  } = useUserAuditLogs({
    page: currentPage,
    size: pageSize,
    ...(actionFilter !== 'all' && { action: actionFilter }),
    ...(entityFilter !== 'all' && { entity: entityFilter })  // Use 'entity' instead of 'entity_type'
  })

  const auditLogs: AuditLogRow[] = (auditLogsResponse?.items || []) as AuditLogRow[]
  const totalItems = auditLogsResponse?.total || 0

  // Filter audit logs based on search term (client-side filtering for current page)
  const filteredLogs: AuditLogRow[] = useMemo(() => {
    if (!searchTerm) return auditLogs

    const searchLower = searchTerm.toLowerCase()
    
    return auditLogs.filter((log: AuditLogRow) => 
      (log.action && log.action.toLowerCase().includes(searchLower)) ||
      (log.details && log.details.toLowerCase().includes(searchLower)) ||
      (log.entityId && log.entityId.toLowerCase().includes(searchLower)) ||
      (log.entityType && log.entityType.toLowerCase().includes(searchLower))
    )
  }, [auditLogs, searchTerm])

  // Reset to first page when filters change
  const handleFilterChange = (filterType: 'action' | 'entity', value: string) => {
    setCurrentPage(1)
    if (filterType === 'action') {
      setActionFilter(value)
    } else {
      setEntityFilter(value)
    }
  }

  // Handle page size change
  const handlePageSizeChange = (newPageSize: string) => {
    setPageSize(parseInt(newPageSize))
    setCurrentPage(1)
  }

  // Handle search change
  const handleSearchChange = (value: string) => {
    setSearchTerm(value)
    // Don't reset page for client-side search to allow searching within current page
  }

  const formatDateTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
  }

  const getActionBadgeVariant = (action?: string) => {
    if (!action) return 'outline'
    
    switch (action.toLowerCase()) {
      case 'create':
        return 'default'
      case 'update':
        return 'secondary'
      case 'delete':
        return 'destructive'
      case 'view':
        return 'outline'
      case 'login':
        return 'default'
      case 'logout':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  const getActionIcon = (action?: string) => {
    if (!action) return <Activity className="h-3 w-3" />
    
    switch (action.toLowerCase()) {
      case 'create':
        return <Plus className="h-3 w-3" />
      case 'update':
        return <Edit className="h-3 w-3" />
      case 'delete':
        return <Trash className="h-3 w-3" />
      case 'view':
        return <Eye className="h-3 w-3" />
      case 'login':
      case 'logout':
        return <User className="h-3 w-3" />
      default:
        return <Activity className="h-3 w-3" />
    }
  }

  const getEntityIcon = (entityType?: string) => {
    if (!entityType) return <Activity className="h-3 w-3" />
    
    switch (entityType.toLowerCase()) {
      case 'patient':
        return <User className="h-3 w-3" />
      case 'appointment':
        return <Calendar className="h-3 w-3" />
      case 'user':
        return <User className="h-3 w-3" />
      default:
        return <Activity className="h-3 w-3" />
    }
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          My Activity History
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          View your recent actions and system activity
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search and Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search actions, entities, or details..."
              value={searchTerm}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={actionFilter} onValueChange={(value) => handleFilterChange('action', value)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Actions</SelectItem>
              <SelectItem value="CREATE">Create</SelectItem>
              <SelectItem value="UPDATE">Update</SelectItem>
              <SelectItem value="DELETE">Delete</SelectItem>
              <SelectItem value="VIEW">View</SelectItem>
              <SelectItem value="LOGIN">Login</SelectItem>
              <SelectItem value="LOGOUT">Logout</SelectItem>
            </SelectContent>
          </Select>
          <Select value={entityFilter} onValueChange={(value) => handleFilterChange('entity', value)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Entity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="patient">Patient</SelectItem>
              <SelectItem value="appointment">Appointment</SelectItem>
              <SelectItem value="user">User</SelectItem>
              <SelectItem value="system">System</SelectItem>
            </SelectContent>
          </Select>
          <Select value={pageSize.toString()} onValueChange={handlePageSizeChange}>
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="5">5 per page</SelectItem>
              <SelectItem value="10">10 per page</SelectItem>
              <SelectItem value="20">20 per page</SelectItem>
              <SelectItem value="50">50 per page</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            <span className="text-muted-foreground">Loading audit logs...</span>
          </div>
        )}

        {/* Error State */}
        {!!error && (
          <div className="flex items-center justify-center h-32 text-red-600">
            <p>Failed to load audit logs. Please try again.</p>
          </div>
        )}

        {/* Results Summary */}
        {!isLoading && !error && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {filteredLogs.length} of {totalItems} {totalItems === 1 ? 'record' : 'records'}
              {searchTerm && ` (filtered on current page)`}
            </p>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  {actionFilter !== 'all' || entityFilter !== 'all' || searchTerm ? 'Filtered' : 'All records'}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                Page {currentPage} of {Math.ceil(totalItems / pageSize)}
              </div>
            </div>
          </div>
        )}

        {/* Audit Logs Table */}
        {!isLoading && !error && (
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Action</TableHead>
                  <TableHead className="w-[120px]">Entity</TableHead>
                  <TableHead className="w-[100px]">Entity ID</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead className="w-[150px]">Timestamp</TableHead>
                  <TableHead className="w-[120px]">IP Address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Activity className="h-8 w-8 text-muted-foreground" />
                        <p className="text-muted-foreground">No activity records found</p>
                        <p className="text-sm text-muted-foreground">
                          {searchTerm || actionFilter !== 'all' || entityFilter !== 'all'
                            ? 'Try adjusting your search or filters'
                            : 'Your activity will appear here as you use the system'
                          }
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredLogs.map((log: AuditLogRow) => (
                    <TableRow key={log.id} className="hover:bg-muted/50">
                      <TableCell>
                        <Badge
                          variant={getActionBadgeVariant(log.action)}
                          className="flex items-center gap-1 w-fit"
                        >
                          {getActionIcon(log.action)}
                          {log.action || 'Unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getEntityIcon(log.entityType)}
                          <span className="capitalize">{log.entityType || 'Unknown'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {log.entityId ? (
                          <code className="text-xs bg-muted px-1 py-0.5 rounded">
                            {log.entityId}
                          </code>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <p className="text-sm max-w-md truncate" title={log.details}>
                          {log.details}
                        </p>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDateTime(log.timestamp)}
                      </TableCell>
                      <TableCell>
                        {log.ipAddress ? (
                          <code className="text-xs bg-muted px-1 py-0.5 rounded">
                            {log.ipAddress}
                          </code>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Pagination */}
        {!isLoading && !error && totalItems > pageSize && (
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalItems)} of {totalItems} entries
            </div>
            
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious 
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage > 1) {
                        setCurrentPage(currentPage - 1)
                      }
                    }}
                    className={currentPage <= 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                  />
                </PaginationItem>
                
                {/* First page */}
                {currentPage > 3 && (
                  <>
                    <PaginationItem>
                      <PaginationLink 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          setCurrentPage(1)
                        }}
                        className="cursor-pointer"
                      >
                        1
                      </PaginationLink>
                    </PaginationItem>
                    {currentPage > 4 && (
                      <PaginationItem>
                        <PaginationEllipsis />
                      </PaginationItem>
                    )}
                  </>
                )}
                
                {/* Pages around current page */}
                {Array.from({ length: Math.ceil(totalItems / pageSize) }, (_, i) => i + 1)
                  .filter(page => page >= Math.max(1, currentPage - 2) && page <= Math.min(Math.ceil(totalItems / pageSize), currentPage + 2))
                  .map((page) => (
                    <PaginationItem key={page}>
                      <PaginationLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          setCurrentPage(page)
                        }}
                        isActive={page === currentPage}
                        className="cursor-pointer"
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  ))
                }
                
                {/* Last page */}
                {currentPage < Math.ceil(totalItems / pageSize) - 2 && (
                  <>
                    {currentPage < Math.ceil(totalItems / pageSize) - 3 && (
                      <PaginationItem>
                        <PaginationEllipsis />
                      </PaginationItem>
                    )}
                    <PaginationItem>
                      <PaginationLink 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          setCurrentPage(Math.ceil(totalItems / pageSize))
                        }}
                        className="cursor-pointer"
                      >
                        {Math.ceil(totalItems / pageSize)}
                      </PaginationLink>
                    </PaginationItem>
                  </>
                )}
                
                <PaginationItem>
                  <PaginationNext 
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage < Math.ceil(totalItems / pageSize)) {
                        setCurrentPage(currentPage + 1)
                      }
                    }}
                    className={currentPage >= Math.ceil(totalItems / pageSize) ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
