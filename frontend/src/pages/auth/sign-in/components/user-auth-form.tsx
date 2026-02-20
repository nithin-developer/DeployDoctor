import { HTMLAttributes, useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";
import { login } from "@/api/auth";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/password-input";

type UserAuthFormProps = HTMLAttributes<HTMLFormElement>;

const formSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Please enter your password"),
});

export function UserAuthForm({ className, ...props }: UserAuthFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const search = searchParams;

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  async function onSubmit(data: z.infer<typeof formSchema>) {
    setIsLoading(true);
    try {
      const res = await login(data.email, data.password);
      if (res.twofa_required) {
        // Redirect to 2FA page with necessary params & twofa token stored in sessionStorage (safer than query)
        sessionStorage.setItem("twofa_token", res.twofa_token || "");
        navigate(
          `/two-fa-verify?email=${encodeURIComponent(data.email)}&password=__hidden`
        ); // password not needed further
        return;
      }
      toast.success("Logged in successfully");
      const redirectTo = search.get("redirect") || "/";
      navigate(redirectTo, { replace: true });
    } catch (error: any) {
      if (error.response?.status === 401) {
        toast.error("Invalid credentials");
      } else {
        toast.error("Login failed");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className={cn("grid gap-4", className)}
        {...props}
      >
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input
                  placeholder="name@example.com"
                  type="email"
                  autoComplete="email"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem className="relative">
              <FormLabel>Password</FormLabel>
              <FormControl>
                <PasswordInput
                  placeholder="********"
                  autoComplete="current-password"
                  {...field}
                />
              </FormControl>
              <FormMessage />
              {/* <Link
                to="/forgot-password"
                className="text-muted-foreground absolute -top-0.5 right-0 text-sm font-medium hover:opacity-75"
              >
                Forgot password?
              </Link> */}
            </FormItem>
          )}
        />

        <Button type="submit" className="mt-2" disabled={isLoading}>
          {isLoading ? "Signing in..." : "Sign In"}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          Don't have an account?{" "}
          <Link
            to="/sign-up"
            className="text-primary hover:underline underline-offset-4"
          >
            Sign up
          </Link>
        </p>
      </form>
    </Form>
  );
}
