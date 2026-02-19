import { UserAuthForm } from "./components/user-auth-form";
import Silk from "@/components/Silk";
import  CircularText from "@/components/CircularText";

export default function SignIn2() {
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
        {/* <div className="relative z-20 flex items-center text-lg font-medium">
          <IconReportMedical className="mr-2 h-6 w-6" />
          Vidyavardhaka College of Engineering
        </div> */}

        {/* <img
          src="https://scontent.cdninstagram.com/v/t51.75761-15/496315625_18321321124206827_7057253329842421035_n.webp?_nc_cat=103&ig_cache_key=MzYyOTI4NTQ2NjIxMzIxNzE5Mw%3D%3D.3-ccb1-7&ccb=1-7&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6InhwaWRzLjE0NDB4MTgwMC5zZHIuQzMifQ%3D%3D&_nc_ohc=ajzeOQRm60sQ7kNvwHExQrI&_nc_oc=AdmC4x91wSyTr1KFd2kcxGPml9q5o6K_SVKi41HZJbnYmp7loayeFdKKXoHH5wxuCf_puoSIkD2qM_Z58eujKb5v&_nc_ad=z-m&_nc_cid=1174&_nc_zt=23&_nc_ht=scontent.cdninstagram.com&_nc_gid=YO7sDBLF5VYY7JLQ_UJMjw&oh=00_AfhVXF3ijSlGQHNdVrUw9LIvgZhu_-Ibd4y1fxEElSH3SA&oe=690D6030"
          className="relative m-auto"
          width={301}
          height={60}
          alt="Vite"
        /> */}

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
              {/* <img src={Logo} alt="Logo" className="h-auto w-30 object-contain" /> */}
              <div className="text-center mx-auto">
                <h2 className="text-3xl font-bold text-white leading-tight">
                  DeployDoctor
                </h2>
                <p className="text-sm text-white/80">An Autonomous DevOps Agent</p>
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-white">Welcome Back,</h3>
              <p className="text-base text-white/90 leading-relaxed">
                Your all-in-one solution for seamless DevOps automation and deployment. Experience the future of software delivery with DeployDoctor, your trusted autonomous DevOps agent.
              </p>
            </div>

            <div className="pt-4 border-t border-white/10">
              <p className="text-sm text-white font-bold">
               &copy;{" "} Designed & Developed by Bit Brains, All Rights Reserved 
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="lg:p-8">
        <div className="mx-auto flex w-full flex-col justify-center space-y-2 sm:w-[350px]">
          <div className="flex flex-col space-y-2 text-left mb-4">
            <h1 className="text-2xl font-semibold tracking-tight">Login</h1>
            <p className="text-muted-foreground text-sm">
              Enter your email and password below <br />
              to log into your account
            </p>
          </div>
          <UserAuthForm />
          <p className="text-muted-foreground px-8 text-center text-sm mt-4">
            By clicking login, you agree to our{" "}
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
