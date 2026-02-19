import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useAuth } from "@/stores/authStore";
import * as authApi from "@/api/auth";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const accountFormSchema = z.object({
  full_name: z
    .string()
    .min(1, "Please enter your full name.")
    .min(2, "Full name must be at least 2 characters.")
    .max(60, "Full name must not be longer than 60 characters."),
  email: z
    .string()
    .email("Please enter a valid email address."),
});

type AccountFormValues = z.infer<typeof accountFormSchema>;

export function AccountForm() {
  const auth = useAuth();
  const user = auth.user;
  const [isLoading, setIsLoading] = useState(false);

  // Only include editable fields in form
  const defaultValues: Partial<AccountFormValues> = {
    full_name: user?.full_name || "",
    email: user?.email || "",
  };

  const form = useForm<AccountFormValues>({
    resolver: zodResolver(accountFormSchema),
    defaultValues,
  });

  // Update form when user data changes (e.g., after page refresh)
  useEffect(() => {
    if (user) {
      form.reset({
        full_name: user.full_name || "",
        email: user.email || "",
      });
    }
  }, [user, form]);

  async function onSubmit(data: AccountFormValues) {
    setIsLoading(true);
    try {
      // Call the backend API to update account
      const response = await authApi.updateAccount({
        full_name: data.full_name,
      });
      
      // Update the auth store with the new user data
      if (response.user && auth.user) {
        auth.setSession({
          user: response.user,
          accessToken: auth.accessToken!,
          refreshToken: auth.refreshToken!,
        });
      }
      
      toast.success("Account updated successfully!");
    } catch (error: any) {
      console.error("Account update error:", error);
      const errorMessage = error?.response?.data?.error || "Failed to update account information. Please try again.";
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">

        <FormField
          control={form.control}
          name="full_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Full Name</FormLabel>
              <FormControl>
                <Input placeholder="John Doe" {...field} />
              </FormControl>
              <FormDescription>
                Your full name as it appears in the system.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="john.doe@example.com" {...field} disabled />
              </FormControl>
              <FormDescription>
                Your email address (read-only).
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Updating..." : "Update account"}
        </Button>
      </form>
    </Form>
  );
}
