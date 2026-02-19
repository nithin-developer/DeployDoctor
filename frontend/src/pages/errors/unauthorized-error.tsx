import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export default function UnauthorizedError() {
  const navigate = useNavigate()

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] font-bold leading-tight'>401</h1>
        <span className='font-medium'>Unauthorized Access!</span>
        <p className='text-center text-muted-foreground'>
          You don't have permission to access this resource.
          <br />
          Please check with your administrator.
        </p>
        <div className='mt-6 flex gap-4'>
          <Button onClick={() => navigate('/')}>Back to Home</Button>
          {/* <Button variant="outline" onClick={() => navigate('/sign-in')}>
            Sign In
          </Button> */}
        </div>
      </div>
    </div>
  )
}
