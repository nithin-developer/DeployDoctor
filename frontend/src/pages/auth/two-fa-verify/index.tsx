import { useState, useEffect } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { ArrowLeft, Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { Badge } from "@/components/ui/badge";
import Silk from "@/components/aurora";
import { verifyTwoFA } from "@/api/auth";

const formSchema = z.object({
  token: z
    .string()
    .min(6, "Verification code must be 6 digits")
    .max(6, "Verification code must be 6 digits")
    .regex(/^\d{6}$/, "Verification code must contain only numbers"),
});

type FormValues = z.infer<typeof formSchema>;

export default function TwoFAVerification() {
  const [isLoading, setIsLoading] = useState(false);
  const [timeLeft, setTimeLeft] = useState(300); // 5 minutes
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const email = searchParams.get("email");
  const password = searchParams.get("password");
  const redirect = searchParams.get("redirect") || "/";

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      token: "",
    },
  });

  // Redirect if no email or password in URL params (invalid access)
  useEffect(() => {
    if (!email || !password) {
      toast.error("Invalid access. Please login again.");
      navigate("/sign-in");
      return;
    }
  }, [email, password, navigate]);

  // Countdown timer for session timeout
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev < 1) {
          toast.error("2FA session expired. Please login again.");
          navigate("/sign-in");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  async function onSubmit(data: FormValues) {
    setIsLoading(true);
    try {
      const twofaToken = sessionStorage.getItem("twofa_token");
      if (!twofaToken) {
        toast.error("Session expired. Please login again.");
        navigate("/sign-in");
        return;
      }
      await verifyTwoFA(twofaToken, data.token);
      sessionStorage.removeItem("twofa_token");
      toast.success("2FA verified. Welcome!");
      const redirectTo = redirect || "/";
      navigate(redirectTo, { replace: true });
    } catch (error: any) {
      if (error.response?.data?.error === "invalid_code") {
        form.setError("token", { message: "Invalid verification code" });
        return;
      }
      if (
        ["twofa_token_expired", "invalid_twofa_token"].includes(
          error.response?.data?.error
        )
      ) {
        toast.error("2FA session expired. Please login again.");
        navigate("/sign-in");
        return;
      }
      toast.error("Verification failed");
    } finally {
      setIsLoading(false);
    }
  }

  const handleBackToLogin = () => {
    navigate("/sign-in");
  };

  if (!email || !password) {
    return null; // Will redirect in useEffect
  }

  return (
    <div className="relative container grid h-svh flex-col items-center justify-center lg:max-w-none lg:grid-cols-2 lg:px-0">
      <Silk
        speed={5}
        scale={1}
        color="#5227ff"
        noiseIntensity={1.5}
        rotation={0}
      />

      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[400px]">
          {/* Back button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBackToLogin}
            className="self-start -ml-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to login
          </Button>

          <div className="flex flex-col space-y-2 text-left mb-4">
            <h1 className="text-2xl font-semibold tracking-tight">
              Two-Factor Authentication
            </h1>
            <p className="text-muted-foreground text-sm">
              Verify your identity by entering the 6-digit code from your
              authenticator app
            </p>
          </div>

          {/* User info */}
          <div className="flex items-center justify-center space-x-2 text-sm text-muted-foreground">
            <span>Signing in as:</span>
            <Badge variant="outline">{email}</Badge>
          </div>

          {/* Timer */}
          <div
            className="flex items-center justify-center space-x-2 text-sm"
            style={{ marginTop: "-10px" }}
          >
            <span className="text-muted-foreground">Session expires in:</span>
            <Badge variant={timeLeft < 60 ? "destructive" : "secondary"}>
              {formatTime(timeLeft)}
            </Badge>
          </div>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="token"
                render={({ field }) => (
                  <FormItem>
                    {/* <FormLabel>Verification Code</FormLabel> */}
                    <FormControl>
                      <div className="flex justify-center">
                        <InputOTP maxLength={6} {...field}>
                          <InputOTPGroup>
                            <InputOTPSlot index={0} />
                            <InputOTPSlot index={1} />
                            <InputOTPSlot index={2} />
                          </InputOTPGroup>
                          <InputOTPSeparator />
                          <InputOTPGroup>
                            <InputOTPSlot index={3} />
                            <InputOTPSlot index={4} />
                            <InputOTPSlot index={5} />
                          </InputOTPGroup>
                        </InputOTP>
                      </div>
                    </FormControl>
                    <FormDescription className="text-center">
                      Enter the 6-digit verification code
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button
                type="submit"
                className="w-full h-11"
                disabled={isLoading || !form.formState.isValid}
              >
                {isLoading ? "Verifying..." : "Verify & Sign In"}
              </Button>
            </form>
          </Form>

          <div className="flex items-start space-x-2">
            <Smartphone className="w-5 h-5 text-muted-foreground mt-0.5" />
            <div className="space-y-2">
              <p className="text-sm font-medium">Having trouble?</p>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Make sure your device time is synchronized</li>
                <li>• Check that you're using the correct authenticator app</li>
                <li>• The code refreshes every 30 seconds</li>
              </ul>
            </div>
          </div>

          {/* Footer */}
          <p className="text-muted-foreground text-center text-sm">
            By continuing, you agree to our{" "}
            <Link
              to="/terms"
              className="hover:text-primary underline underline-offset-4"
            >
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link
              to="/privacy"
              className="hover:text-primary underline underline-offset-4"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
