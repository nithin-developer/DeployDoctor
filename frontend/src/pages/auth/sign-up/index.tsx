import { UserSignupForm } from "./components/user-signup-form";
import Silk from "@/components/Silk";
import CircularText from "@/components/CircularText";

export default function SignUp() {
  return (
    <div className="relative container grid h-svh flex-col items-center justify-center lg:max-w-none lg:grid-cols-2 lg:px-0">
      <div className="bg-muted relative hidden h-full flex-col p-10 text-white lg:flex dark:border-r">
        <div className="absolute inset-0">
          <Silk
            speed={5}
            scale={1}
            color="#d33157"
            noiseIntensity={1.5}
            rotation={0}
          />
        </div>

        <div className="relative z-20 mt-auto flex flex-col items-center space-y-4">
          <CircularText
            text="AUTONOMOUS☆DEVOPS☆AGENT☆"
            onHover="speedUp"
            spinDuration={20}
            className="custom-class"
          />
        </div>

        <div className="relative z-20 mt-auto">
          <div className="bg-black/20 backdrop-blur-sm p-8 rounded-xl border border-white/10 shadow-xl space-y-3">
            <div className="flex items-center gap-3">
              <div className="text-center mx-auto">
                <h2 className="text-3xl font-bold text-white leading-tight">
                  DeployDoctor
                </h2>
                <p className="text-sm text-white/80">An Autonomous DevOps Agent</p>
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-white">Join Us Today,</h3>
              <p className="text-base text-white/90 leading-relaxed">
                Create your account and experience the future of software delivery with DeployDoctor, your trusted autonomous DevOps agent.
              </p>
            </div>

            <div className="pt-4 border-t border-white/10">
              <p className="text-sm text-white font-bold">
                &copy; Designed & Developed by Bit Brains, All Rights Reserved
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-2 sm:w-[350px]">
          <div className="flex flex-col space-y-2 text-left mb-4">
            <h1 className="text-2xl font-semibold tracking-tight">Create Account</h1>
            <p className="text-muted-foreground text-sm">
              Enter your details below <br />
              to create your account
            </p>
          </div>
          <UserSignupForm />
          <p className="text-muted-foreground px-8 text-center text-sm mt-4">
            By clicking sign up, you agree to our{" "}
            <a
              href="/terms"
              className="hover:text-primary underline underline-offset-4"
            >
              Terms of Service
            </a>{" "}
            and{" "}
            <a
              href="/privacy"
              className="hover:text-primary underline underline-offset-4"
            >
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
