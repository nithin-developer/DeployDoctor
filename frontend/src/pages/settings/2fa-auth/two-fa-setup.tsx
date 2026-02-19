import { useState, useEffect } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Shield,
  ShieldCheck,
  QrCode,
  Smartphone,
  CheckCircle,
} from "lucide-react";
import { toast } from "sonner";
import QRCode from "qrcode";
import { useAuth } from "@/stores/authStore";
import * as authApi from "@/api/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const totpSchema = z.object({
  token: z
    .string()
    .min(6, "TOTP token must be 6 digits")
    .max(6, "TOTP token must be 6 digits")
    .regex(/^\d{6}$/, "TOTP token must contain only numbers"),
});

type TOTPFormValues = z.infer<typeof totpSchema>;

type SetupStep =
  | "confirmation"
  | "install-app"
  | "scan-qr"
  | "verify-token"
  | "complete";

interface TwoFASetupData {
  secret: string;
  qr_code_uri: string;
}

export function TwoFASetup() {
  const auth = useAuth();
  const [user, setUser] = useState<any>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState<SetupStep>("confirmation");
  const [isLoading, setIsLoading] = useState(false);
  const [setupData, setSetupData] = useState<TwoFASetupData | null>(null);
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);

  const form = useForm<TOTPFormValues>({
    resolver: zodResolver(totpSchema),
    defaultValues: {
      token: "",
    },
  });

  // check if user is already enabled for 2FA using authapi
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const check2FAStatus = await authApi.getCurrentUser();
        setUser(check2FAStatus);
      } catch (error) {
        console.error("Failed to fetch user status:", error);
      }
    };
    checkStatus();
  }, []);

  const resetSetup = () => {
    setCurrentStep("confirmation");
    setSetupData(null);
    setQrCodeUrl(null);
    form.reset();
    setIsLoading(false);
  };

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      // Reset everything when dialog closes
      setTimeout(() => resetSetup(), 200);
    }
  };

  const startSetup = async () => {
    setIsLoading(true);
    try {
      const data = await authApi.setupTwoFA();
      setSetupData(data);

      // Generate QR code image
      const qrDataURL = await QRCode.toDataURL(data.qr_code_uri);
      setQrCodeUrl(qrDataURL);

      setCurrentStep("install-app");
    } catch (error: any) {
      console.error("2FA setup error:", error);
      toast.error("Failed to start 2FA setup. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const verifyToken = async (data: TOTPFormValues) => {
    setIsLoading(true);
    try {
      await authApi.enableTwoFA(data.token);

      // Update user state
      if (auth.user) {
        auth.setSession({
          user: {
            ...auth.user,
            is_2fa_enabled: true,
          },
          accessToken: auth.accessToken!,
          refreshToken: auth.refreshToken!,
        });
      }

      setCurrentStep("complete");
      toast.success("2FA has been successfully enabled!");
    } catch (error: any) {
      console.error("2FA verification error:", error);
      if (error.response?.status === 400) {
        form.setError("token", {
          message: "Invalid TOTP token. Please try again.",
        });
      } else {
        toast.error("Failed to verify token. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleComplete = () => {
    setIsOpen(false);
    resetSetup();
  };

  const disableTwoFA = async () => {
    setIsLoading(true);
    try {
      await authApi.disableTwoFA();

      // Update user state
      if (auth.user) {
        auth.setSession({
          user: {
            ...auth.user,
            is_2fa_enabled: false,
          },
          accessToken: auth.accessToken!,
          refreshToken: auth.refreshToken!,
        });
      }

      toast.success("2FA has been disabled for your account");
    } catch (error: any) {
      console.error("2FA disable error:", error);
      toast.error("Failed to disable 2FA. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case "confirmation":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-blue-100 rounded-full">
              <Shield className="w-8 h-8 text-blue-600" />
            </div>
            <div className="text-center space-y-4">
              <h3 className="text-lg font-semibold">
                Enable Two-Factor Authentication
              </h3>
              <p className="text-muted-foreground">
                Two-factor authentication adds an extra layer of security to
                your account by requiring a code from your phone in addition to
                your password.
              </p>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <div className="text-sm text-amber-800">
                    <strong>Important:</strong> You'll need a smartphone with
                    Google Authenticator or similar TOTP app installed to
                    complete this setup.
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "install-app":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-green-100 rounded-full">
              <Smartphone className="w-8 h-8 text-green-600" />
            </div>
            <div className="text-center space-y-4">
              <h3 className="text-lg font-semibold">
                Install Authenticator App
              </h3>
              <p className="text-muted-foreground">
                You'll need an authenticator app to generate security codes. We
                recommend:
              </p>
              <div className="grid gap-3">
                <Card className="p-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                      <Shield className="w-5 h-5 text-blue-600" />
                    </div>
                    <div className="text-left">
                      <div className="font-medium">Google Authenticator</div>
                      <div className="text-sm text-muted-foreground">
                        Free for iOS and Android
                      </div>
                    </div>
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                      <Shield className="w-5 h-5 text-purple-600" />
                    </div>
                    <div className="text-left">
                      <div className="font-medium">Microsoft Authenticator</div>
                      <div className="text-sm text-muted-foreground">
                        Free for iOS and Android
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </div>
        );

      case "scan-qr":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-indigo-100 rounded-full">
              <QrCode className="w-8 h-8 text-indigo-600" />
            </div>
            <div className="text-center space-y-4">
              <h3 className="text-lg font-semibold">Scan QR Code</h3>
              <p className="text-muted-foreground">
                Open your authenticator app and scan this QR code, or manually
                enter the secret key.
              </p>

              {setupData && (
                <div className="space-y-4">
                  {/* QR Code Display */}
                  <div className="flex justify-center p-4 bg-white border rounded-lg">
                    <div className="text-center">
                      {qrCodeUrl ? (
                        <img
                          src={qrCodeUrl}
                          alt="2FA QR Code"
                          className="w-48 h-48 mx-auto"
                        />
                      ) : (
                        <div className="w-48 h-48 bg-gray-100 border border-dashed border-gray-300 rounded-lg flex items-center justify-center">
                          <div className="text-center space-y-2">
                            <QrCode className="w-12 h-12 text-gray-400 mx-auto" />
                            <p className="text-sm text-gray-500">
                              Loading QR Code...
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Manual Entry */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Manual Entry Key:
                    </label>
                    <div className="flex items-center space-x-2">
                      <Input
                        value={setupData.secret}
                        readOnly
                        className="font-mono text-sm"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          navigator.clipboard.writeText(setupData.secret);
                          toast.success("Secret key copied to clipboard");
                        }}
                      >
                        Copy
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        );

      case "verify-token":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-orange-100 rounded-full">
              <ShieldCheck className="w-8 h-8 text-orange-600" />
            </div>
            <div className="text-center space-y-4">
              <h3 className="text-lg font-semibold">Verify Setup</h3>
              <p className="text-muted-foreground">
                Enter the 6-digit code from your authenticator app to complete
                the setup.
              </p>

              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(verifyToken)}
                  className="space-y-4"
                >
                  <FormField
                    control={form.control}
                    name="token"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Authentication Code</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="000000"
                            maxLength={6}
                            className="text-center text-lg tracking-widest font-mono"
                            autoComplete="off"
                          />
                        </FormControl>
                        <FormDescription>
                          Enter the 6-digit code from your authenticator app
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </form>
              </Form>
            </div>
          </div>
        );

      case "complete":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-green-100 rounded-full">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <div className="text-center space-y-4">
              <h3 className="text-lg font-semibold">Setup Complete!</h3>
              <p className="text-muted-foreground">
                Two-factor authentication has been successfully enabled for your
                account.
              </p>
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center justify-center space-x-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-green-800 font-medium">
                    2FA is now active
                  </span>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const renderFooter = () => {
    switch (currentStep) {
      case "confirmation":
        return (
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            <Button onClick={startSetup} disabled={isLoading}>
              {isLoading ? "Setting up..." : "Start Setup"}
            </Button>
          </div>
        );

      case "install-app":
        return (
          <div className="flex gap-3 justify-between">
            <div>
              <Button
                variant="outline"
                onClick={() => setCurrentStep("confirmation")}
              >
                Back
              </Button>
            </div>
            <div>
              <Button onClick={() => setCurrentStep("scan-qr")}>
                I have the app installed
              </Button>
            </div>
          </div>
        );

      case "scan-qr":
        return (
          <div className="flex gap-3 justify-between">
            <Button
              variant="outline"
              onClick={() => setCurrentStep("install-app")}
            >
              Back
            </Button>
            <Button onClick={() => setCurrentStep("verify-token")}>
              I've scanned the code
            </Button>
          </div>
        );

      case "verify-token":
        return (
          <div className="flex gap-3 justify-between">
            <Button variant="outline" onClick={() => setCurrentStep("scan-qr")}>
              Back
            </Button>
            <Button
              onClick={form.handleSubmit(verifyToken)}
              disabled={isLoading || !form.formState.isValid}
            >
              {isLoading ? "Verifying..." : "Verify & Enable"}
            </Button>
          </div>
        );

      case "complete":
        return (
          <div className="flex justify-end">
            <Button onClick={handleComplete}>Done</Button>
          </div>
        );

      default:
        return null;
    }
  };

  if (user?.is_2fa_enabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-green-600" />
            <span>Two-Factor Authentication</span>
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Enabled
            </Badge>
          </CardTitle>
          <CardDescription>
            Your account is protected with two-factor authentication.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center space-x-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="text-green-800">2FA is currently active</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={disableTwoFA}
              disabled={isLoading}
            >
              {isLoading ? "Disabling..." : "Disable 2FA"}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Shield className="w-5 h-5" />
          <span>Two-Factor Authentication</span>
          <Badge variant="outline">Disabled</Badge>
        </CardTitle>
        <CardDescription>
          Add an extra layer of security to your account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Two-factor authentication helps protect your account by requiring
            both your password and a code from your phone when signing in.
          </p>

          <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>
              <Button>
                <Shield className="w-4 h-4" />
                Enable 2FA
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Setup Two-Factor Authentication</DialogTitle>
                <DialogDescription>
                  Step{" "}
                  {currentStep === "confirmation"
                    ? "1"
                    : currentStep === "install-app"
                      ? "2"
                      : currentStep === "scan-qr"
                        ? "3"
                        : currentStep === "verify-token"
                          ? "4"
                          : "5"}{" "}
                  of 5
                </DialogDescription>
              </DialogHeader>

              {renderStepContent()}

              <Separator />

              <DialogFooter className="sm:justify-between">
                {renderFooter()}
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardContent>
    </Card>
  );
}
