import { useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'
// Note: This demo form validates a static token without store calls

interface TwoFAFormProps {
  email: string
  onBack: () => void
}

const formSchema = z.object({
  token: z.string().min(6, 'Verification code must be 6 digits').max(6),
})

export function TwoFAForm({ email: _email, onBack }: TwoFAFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      token: '',
    },
  })

  async function onSubmit(data: z.infer<typeof formSchema>) {
    setIsLoading(true)
    
    try {
      // Simple demo: accept only 123456
      if (data.token === '123456') {
        toast.success('Verification successful!')
        const redirectTo = searchParams.get('redirect') || '/'
        navigate(redirectTo)
      } else {
        toast.error('Invalid verification code')
      }
    } catch (error) {
      console.error('2FA verification error:', error)
      toast.error('An unexpected error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight">Two-Factor Authentication</h2>
        <p className="text-muted-foreground text-sm">
          Enter the 6-digit code from your authenticator app
        </p>
        <div className="bg-muted p-3 rounded-md text-sm">
          <p className="text-muted-foreground">Demo: Use code <strong>123456</strong></p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="token"
            render={({ field }) => (
              <FormItem className="flex flex-col items-center">
                <FormLabel>Verification Code</FormLabel>
                <FormControl>
                  <InputOTP maxLength={6} {...field}>
                    <InputOTPGroup>
                      <InputOTPSlot index={0} />
                      <InputOTPSlot index={1} />
                      <InputOTPSlot index={2} />
                      <InputOTPSlot index={3} />
                      <InputOTPSlot index={4} />
                      <InputOTPSlot index={5} />
                    </InputOTPGroup>
                  </InputOTP>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={onBack} className="flex-1">
              Back
            </Button>
            <Button type="submit" disabled={isLoading} className="flex-1">
              Verify
            </Button>
          </div>
        </form>
      </Form>
    </div>
  )
}
