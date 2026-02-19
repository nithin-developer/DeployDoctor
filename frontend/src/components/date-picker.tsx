import { format } from 'date-fns'
import { Calendar as CalendarIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface Props {
  selected: Date | undefined
  onSelect: (date: Date | undefined) => void
  placeholder?: string
  disablePast?: boolean
  disableFuture?: boolean // New prop to disable future dates
}

export function DatePicker({
  selected,
  onSelect,
  placeholder = 'Pick a date',
  disablePast = false,
  disableFuture = false, // New prop to disable future dates
}: Props) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='outline'
          data-empty={!selected}
          className='data-[empty=true]:text-muted-foreground w-full justify-start text-left font-normal'
        >
          {selected ? (
            format(selected, 'MMM d, yyyy')
          ) : (
            <span>{placeholder}</span>
          )}
          <CalendarIcon className='ml-auto h-4 w-4 opacity-50' />
        </Button>
      </PopoverTrigger>
      <PopoverContent className='w-auto p-0'>
        <Calendar
          mode='single'
          captionLayout='dropdown'
          selected={selected}
          onSelect={onSelect}
          disabled={(date: Date) => {
            if (disablePast) {
              return date < today
            }
            if (disableFuture) {
              return date > today
            }
            // For edit mode, allow all reasonable dates
            return date < new Date('1900-01-01') || date > new Date('2100-01-01')
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
